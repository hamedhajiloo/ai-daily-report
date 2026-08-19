#!/usr/bin/env python3
"""Collect planner items from Azure Boards, Gmail and Microsoft Graph (Outlook+Calendar).

Writes docs/planner/<date>.json for the Mini App Planner tab.
Every source is optional: missing credentials => status "skipped", never an error.

Credentials (in $LOCALAPPDATA/hermes/.env):
  PLANNER_ADO_ORG=https://dev.azure.com/<org>
  PLANNER_ADO_PROJECTS=MLK,Crystal,LandLogic
  PLANNER_ADO_PAT=<personal access token, Work Items (Read)>
  PLANNER_GMAIL_USER=you@gmail.com
  PLANNER_GMAIL_APP_PASSWORD=<app password>
Microsoft Graph: interactive device-code login the first time (no app registration
needed; uses the public Azure CLI client id). Refresh token stored in
scripts/.msgraph_token.json (gitignored).
"""
import base64
import email as email_lib
import imaplib
import json
import os
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, date

ROOT = pathlib.Path(__file__).resolve().parents[1]
TODAY = date.today().isoformat()
MS_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"  # Microsoft Graph CLI public client
MS_SCOPE = "offline_access Mail.Read Calendars.Read User.Read"
TOKEN_FILE = pathlib.Path(__file__).resolve().parent / ".msgraph_token.json"


def load_env():
    env = {}
    p = os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", ".env")
    if os.path.exists(p):
        for line in open(p, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    env.update({k: v for k, v in os.environ.items() if k.startswith("PLANNER_")})
    return env


def http(url, data=None, headers=None, method=None, timeout=25):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace"), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), dict(e.headers)


# ---------------- Azure Boards (multi-org) ----------------

def ado_configs(env):
    """PLANNER_ADO<n>_URL (full org/project URL) + PLANNER_ADO<n>_PAT, n=1..9."""
    cfgs = []
    for i in range(1, 10):
        url, pat = env.get(f"PLANNER_ADO{i}_URL", ""), env.get(f"PLANNER_ADO{i}_PAT", "")
        if url and pat:
            cfgs.append((url.rstrip("/"), pat))
    org = env.get("PLANNER_ADO_ORG", "").rstrip("/")
    pat = env.get("PLANNER_ADO_PAT", "")
    if org and pat:  # legacy single-org form
        for proj in [p.strip() for p in env.get("PLANNER_ADO_PROJECTS", "").split(",") if p.strip()]:
            cfgs.append((f"{org}/{urllib.parse.quote(proj)}", pat))
    return cfgs


def parse_ado_url(url):
    m = re.match(r"https://dev\.azure\.com/([^/]+)/([^/?#]+)", url)
    if m:
        return f"https://dev.azure.com/{m.group(1)}", m.group(2)
    m = re.match(r"https://([^./]+)\.visualstudio\.com/([^/?#]+)", url)
    if m:
        return f"https://{m.group(1)}.visualstudio.com", m.group(2)
    return None, ""


def fetch_boards(env):
    cfgs = ado_configs(env)
    if not cfgs:
        return {"status": "skipped", "items": [], "note": "say \"connect boards\" in chat"}
    items, errs = [], []
    for url, pat in cfgs:
        org, proj = parse_ado_url(url)
        if not org:
            errs.append(f"bad URL {url}")
            continue
        try:
            auth = base64.b64encode((":" + pat).encode()).decode()
            headers = {"Authorization": "Basic " + auth, "Content-Type": "application/json"}
            wiql = json.dumps({
                "query": "SELECT [System.Id] FROM WorkItems WHERE [System.AssignedTo] = @Me "
                         "AND [System.State] NOT IN ('Closed','Done','Removed','Completed','Resolved') "
                         "ORDER BY [System.ChangedDate] DESC"
            }).encode()
            st, body, _ = http(f"{org}/{urllib.parse.quote(proj)}/_apis/wit/wiql?api-version=7.1",
                               data=wiql, headers=headers, method="POST")
            if st != 200:
                errs.append(f"{proj}: HTTP {st} {body[:80]}")
                continue
            ids = [w["id"] for w in json.loads(body).get("workItems", [])][:20]
            if ids:
                st, body, _ = http(f"{org}/_apis/wit/workitems?ids={','.join(map(str, ids))}"
                                   f"&api-version=7.1", headers=headers)
                if st != 200:
                    errs.append(f"{proj}: details HTTP {st}")
                    continue
                for wi in json.loads(body).get("value", []):
                    f = wi.get("fields", {})
                    items.append({
                        "project": proj,
                        "id": wi["id"],
                        "title": f.get("System.Title", "?"),
                        "type": f.get("System.WorkItemType", ""),
                        "state": f.get("System.State", ""),
                        "priority": f.get("Microsoft.VSTS.Common.Priority", ""),
                        "changed": (f.get("System.ChangedDate") or "")[:16].replace("T", " "),
                        "url": f"{org}/{urllib.parse.quote(proj)}/_workitems/edit/{wi['id']}",
                    })
        except Exception as e:
            errs.append(f"{proj}: {e}")
    if errs and not items:
        return {"status": "error", "items": [], "error": "; ".join(errs)[:200]}
    # dedupe (same org+id can appear via multiple project URLs, e.g. renamed projects)
    seen, uniq = set(), []
    for it in items:
        key = (it["url"].split("/_workitems")[0], it["id"])
        if key not in seen:
            seen.add(key)
            uniq.append(it)
    uniq.sort(key=lambda i: i.get("changed", ""), reverse=True)
    return {"status": "ok", "items": uniq[:30]}


# ---------------- Gmail ----------------

def fetch_gmail(env):
    user, pw = env.get("PLANNER_GMAIL_USER", ""), env.get("PLANNER_GMAIL_APP_PASSWORD", "")
    if not user or not pw:
        return {"status": "skipped", "items": [], "note": "set PLANNER_GMAIL_USER + PLANNER_GMAIL_APP_PASSWORD"}
    try:
        m = imaplib.IMAP4_SSL("imap.gmail.com")
        m.login(user, pw)
        m.select("INBOX", readonly=True)
        _, data = m.search(None, f'(UNSEEN SINCE {TODAY})')
        ids = data[0].split()
        items = []
        for i in reversed(ids[:15]):  # newest first
            _, msgdata = m.fetch(i, "(RFC822.HEADER)")
            msg = email_lib.message_from_bytes(msgdata[0][1])
            frm = email_lib.utils.parseaddr(msg.get("From", ""))[1]
            items.append({
                "subject": email_lib.header.decode_header(msg.get("Subject", ""))[0][0]
                if msg.get("Subject") else "(no subject)",
                "from": frm,
                "time": (msg.get("Date") or "")[:16],
            })
        m.logout()
        return {"status": "ok", "unread": len(ids), "items": items}
    except Exception as e:
        return {"status": "error", "items": [], "error": str(e)}


# ---------------- Microsoft Graph (Outlook + Calendar) ----------------

def graph_token(env, interactive=True):
    if TOKEN_FILE.exists():
        tok = json.loads(TOKEN_FILE.read_text())
        if tok.get("expires_at", 0) > time.time() + 60:
            return tok["access_token"]
        st, body, _ = http("https://login.microsoftonline.com/common/oauth2/v2.0/token",
                           data=urllib.parse.urlencode({
                               "client_id": MS_CLIENT_ID, "grant_type": "refresh_token",
                               "refresh_token": tok.get("refresh_token", ""), "scope": MS_SCOPE}).encode(),
                           headers={"Content-Type": "application/x-www-form-urlencoded"})
        if st == 200:
            t = json.loads(body)
            TOKEN_FILE.write_text(json.dumps({"access_token": t["access_token"],
                                              "refresh_token": t.get("refresh_token", tok.get("refresh_token")),
                                              "expires_at": time.time() + t.get("expires_in", 3600)}))
            return t["access_token"]
    if not interactive:
        return None
    st, body, _ = http("https://login.microsoftonline.com/common/oauth2/v2.0/devicecode",
                       data=urllib.parse.urlencode({"client_id": MS_CLIENT_ID, "scope": MS_SCOPE}).encode(),
                       headers={"Content-Type": "application/x-www-form-urlencoded"})
    if st != 200:
        return None
    d = json.loads(body)
    print(f"\n[graph] Open {d['verification_uri']} and enter code: {d['user_code']}\n", flush=True)
    for _ in range(int(d.get("expires_in", 900)) // int(d.get("interval", 5))):
        time.sleep(int(d.get("interval", 5)))
        st, body, _ = http("https://login.microsoftonline.com/common/oauth2/v2.0/token",
                           data=urllib.parse.urlencode({
                               "client_id": MS_CLIENT_ID, "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                               "device_code": d["device_code"]}).encode(),
                           headers={"Content-Type": "application/x-www-form-urlencoded"})
        r = json.loads(body)
        if st == 200 and "access_token" in r:
            TOKEN_FILE.write_text(json.dumps({"access_token": r["access_token"],
                                              "refresh_token": r.get("refresh_token", ""),
                                              "expires_at": time.time() + r.get("expires_in", 3600)}))
            return r["access_token"]
        if r.get("error") != "authorization_pending":
            print(f"[graph] {r.get('error')}: {r.get('error_description','')[:120]}")
            return None
    return None


def graph_get(token, path):
    st, body, _ = http("https://graph.microsoft.com/v1.0" + path,
                       headers={"Authorization": "Bearer " + token})
    return json.loads(body) if st == 200 else {"value": [], "_status": st, "_err": body[:200]}


def fetch_graph(env, interactive=True):
    tok = graph_token(env, interactive)
    if not tok:
        return None
    out = {}
    q = urllib.parse.quote
    ev = graph_get(tok, "/me/events?$select=subject,start,end,isAllDay,location&$orderby=start/dateTime&$filter="
                        + q(f"start/dateTime ge {TODAY}T00:00:00 and start/dateTime le {TODAY}T23:59:59"))
    out["calendar"] = {"status": "ok", "items": [{
        "title": e.get("subject", "(no title)"),
        "start": (e.get("start", {}).get("dateTime") or "")[11:16],
        "end": (e.get("end", {}).get("dateTime") or "")[11:16],
        "all_day": e.get("isAllDay", False),
        "location": (e.get("location") or {}).get("displayName", ""),
    } for e in ev.get("value", [])]}
    ms = graph_get(tok, "/me/messages?$filter=" + q("isRead eq false")
                   + "&$orderby=" + q("receivedDateTime desc")
                   + "&$top=12&$select=subject,from,receivedDateTime")
    out["outlook"] = {"status": "ok", "items": [{
        "subject": m.get("subject") or "(no subject)",
        "from": (m.get("from") or {}).get("emailAddress", {}).get("address", ""),
        "time": (m.get("receivedDateTime") or "")[:16].replace("T", " "),
    } for m in ms.get("value", [])]}
    return out


def main():
    env = load_env()
    interactive = "--no-login" not in sys.argv
    report = {"date": TODAY, "generated": datetime.now().isoformat(timespec="minutes"), "sources": {}}
    report["sources"]["boards"] = fetch_boards(env)
    report["sources"]["gmail"] = fetch_gmail(env)
    try:
        g = fetch_graph(env, interactive)
        if g:
            report["sources"].update(g)
        else:
            report["sources"]["calendar"] = {"status": "skipped", "items": [], "note": "run scripts/collect_planner.py once interactively to log in"}
            report["sources"]["outlook"] = {"status": "skipped", "items": [], "note": "same"}
    except Exception as e:
        report["sources"]["calendar"] = {"status": "error", "items": [], "error": str(e)}
        report["sources"]["outlook"] = {"status": "error", "items": [], "error": str(e)}
    out = ROOT / "docs" / "planner"
    out.mkdir(exist_ok=True)
    (out / f"{TODAY}.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    idx = {}
    idx_path = out / "index.json"
    if idx_path.exists():
        try:
            idx = json.loads(idx_path.read_text())
        except Exception:
            idx = {}
    idx[TODAY] = [k for k, v in report["sources"].items() if v.get("status") == "ok"]
    idx_path.write_text(json.dumps(idx, indent=1), encoding="utf-8")
    for k, v in report["sources"].items():
        print(f"[{k}] {v['status']} — {len(v.get('items', []))} items"
              + (f" (unread={v['unread']})" if "unread" in v else "")
              + (f" err={v.get('error') or v.get('note')}" if v["status"] != "ok" else ""))
    print(f"wrote docs/planner/{TODAY}.json")


if __name__ == "__main__":
    main()
