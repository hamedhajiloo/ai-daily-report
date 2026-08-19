#!/usr/bin/env python
"""Collect AI news from Google News RSS + official blogs. Keyless, cron-safe.

Usage: python collect_news.py <repo_root> [date YYYY-MM-DD]
Writes <repo_root>/docs/reports/<date>-raw.json with deduped items grouped by org.
"""
import json, sys, os, re, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape

REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATE = sys.argv[2] if len(sys.argv) > 2 else datetime.now(timezone(timedelta(hours=3, minutes=30))).strftime("%Y-%m-%d")
WINDOW_H = 36  # look-back window

# (org key, display org, Google News query, official RSS feeds[])
SOURCES = [
    ("openai",    "OpenAI",           "OpenAI when:2d",              ["https://openai.com/news/rss.xml"]),
    ("anthropic", "Anthropic (Claude)","Anthropic Claude when:2d",    []),
    ("google",    "Google DeepMind",  "Google DeepMind Gemini when:2d",["https://deepmind.google/blog/rss.xml"]),
    ("xai",       "xAI (Grok)",       "xAI Grok when:2d",            []),
    ("meta",      "Meta AI",          "Meta AI Llama when:2d",       []),
    ("microsoft", "Microsoft AI",     "Microsoft Copilot AI when:2d",[]),
    ("mistral",   "Mistral AI",       "Mistral AI when:2d",          []),
    ("nvidia",    "NVIDIA",           "NVIDIA AI when:2d",           ["https://blogs.nvidia.com/feed/"]),
    ("opensource","Open Source AI",   "open source AI model release when:2d", []),
    ("research",  "Research",         "AI research breakthrough when:2d", []),
    ("policy",    "Policy & Regulation","AI regulation law when:2d", []),
    ("industry",  "Industry",         "artificial intelligence industry funding when:2d", []),
]

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def fetch(url, timeout=25):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def parse_rss(xml_bytes):
    items = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        print(f"  [rss] parse error: {e}")
        return items
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        src = ""
        se = it.find("source")
        if se is not None:
            src = (se.text or "").strip()
        desc = re.sub(r"<[^>]+>", " ", it.findtext("description") or "")
        desc = unescape(re.sub(r"\s+", " ", desc)).strip()
        if not title or not link:
            continue
        when = None
        if pub:
            try:
                when = parsedate_to_datetime(pub)
            except Exception:
                pass
        items.append({"title": unescape(title), "url": link, "source": src,
                      "published": when.isoformat() if when else "", "desc": desc[:300]})
    return items

def gn_url(q):
    # the /rss/search/<path> form 302s badly from this network; ?q= form works.
    # colon in when:2d must stay literal.
    enc = urllib.request.quote(q, safe=":")
    return "https://news.google.com/rss/search?q=" + enc + "&hl=en-US&gl=US&ceid=US:en"

def bing_url(q):
    # qft interval="7" restricts to past-week stories (Bing defaults to relevance = stale)
    return ("https://www.bing.com/news/search?q=" + urllib.request.quote(q, safe="")
            + "&format=RSS&qft=interval%3d%227%22")

def unwrap_link(link):
    """Extract the real publisher URL from Bing/Google redirect wrappers."""
    try:
        if "bing.com/news/apiclick" in link or "bing.com/news/aclick" in link:
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(link).query)
            if qs.get("url"):
                return qs["url"][0]
        if "news.google.com" in link:
            from urllib.parse import urlparse, parse_qs
            qs = parse_qs(urlparse(link).query)
            if qs.get("url"):
                return qs["url"][0]
    except Exception:
        pass
    return link

def resolve_gnews(url):
    """Best-effort: older /articles/ path sometimes still 302s to the publisher."""
    if "news.google.com/rss/articles/" not in url:
        return url
    aid = url.split("/articles/")[1].split("?")[0]
    final = url
    try:
        class NR(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        op = urllib.request.build_opener(NR)
        try:
            r = op.open(urllib.request.Request("https://news.google.com/articles/" + aid, headers=UA), timeout=8)
            loc = r.headers.get("Location")
            if loc and "news.google.com" not in loc:
                final = loc
        except urllib.error.HTTPError as e:
            loc = e.headers.get("Location")
            if loc and "news.google.com" not in loc and e.code in (301, 302, 303, 307, 308):
                final = loc
    except Exception:
        pass
    return final

def main():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=WINDOW_H + 12)
    all_items, failures = [], []
    for key, disp, query, feeds in SOURCES:
        bing_q = query.replace(" when:2d", "")  # when: operator is Google-only
        # feeds & bing first (direct publisher URLs); gnews last so its
        # redirect-wrapped duplicates lose the dedup race
        urls = [("feed", f) for f in feeds] + [("bing", bing_url(bing_q)), ("gnews", gn_url(query))]
        got = 0
        for kind, url in urls:
            try:
                raw = fetch(url)
                entries = parse_rss(raw)
            except Exception as e:
                failures.append(f"{kind}:{url} -> {type(e).__name__}: {e}")
                continue
            for e in entries:
                e["org_key"], e["org"] = key, disp
                e["origin"] = kind
                e["url"] = unwrap_link(e["url"])
                if kind == "feed":
                    if not e["source"]:
                        e["source"] = "official blog"
                else:
                    # Google News titles end with " - Source"
                    m = re.match(r"^(.*) - ([^-]{3,40})$", e["title"])
                    if m and not e["source"]:
                        e["source"] = m.group(2).strip()
                got += 1
            all_items.extend(entries)
        print(f"[{key}] {got} items")

    # keep recent, dedupe
    def within(e):
        if not e["published"]:
            return True  # keep undated; curator trims
        try:
            return datetime.fromisoformat(e["published"]) >= cutoff
        except Exception:
            return True

    def core_title(t):
        # strip trailing " - Source" that Google News appends, drop punctuation
        t = re.sub(r"\s+-\s+[^-]{3,45}$", "", t.strip())
        return re.sub(r"[^a-z0-9 ]", "", t.lower())[:90]

    seen, out = set(), []
    for e in all_items:
        if not within(e):
            continue
        norm = core_title(e["title"])
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(e)

    out.sort(key=lambda e: e.get("published") or "", reverse=True)
    # cap per org to keep reports readable
    cap, cnt = 14, {}
    final = []
    for e in out:
        cnt[e["org_key"]] = cnt.get(e["org_key"], 0) + 1
        if cnt[e["org_key"]] <= cap:
            final.append(e)

    # try to unwrap google redirect links concurrently (keeps wrapped link if it fails)
    from concurrent.futures import ThreadPoolExecutor
    wrapped = [(i, e) for i, e in enumerate(final) if "news.google.com/rss/articles/" in e["url"]]
    if wrapped:
        with ThreadPoolExecutor(max_workers=12) as ex:
            news = list(ex.map(lambda e: resolve_gnews(e["url"]), [e for _, e in wrapped]))
        done = 0
        for (i, e), new in zip(wrapped, news):
            if new != e["url"]:
                e["url"], done = new, done + 1
        print(f"[unwrap] resolved {done}/{len(wrapped)} google links")

    os.makedirs(os.path.join(REPO, "docs", "reports"), exist_ok=True)
    path = os.path.join(REPO, "docs", "reports", DATE + "-raw.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"date": DATE, "collected_at": datetime.now(timezone.utc).isoformat(),
                   "window_hours": WINDOW_H, "failures": failures,
                   "counts": cnt, "items": final}, f, ensure_ascii=False, indent=1)
    print(f"WROTE {path}: {len(final)} items, {len(failures)} source failures")
    if failures:
        print("FAILURES:", *failures[:8], sep="\n  ")

if __name__ == "__main__":
    main()
