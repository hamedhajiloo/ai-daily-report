#!/usr/bin/env python3
"""Curate 2026-09-04 raw items into the final report (one-time script)."""
import json, re
from datetime import datetime, timezone, timedelta

ROOT = "D:/ai-daily-report"
IRT = timezone(timedelta(hours=3, minutes=30))
now = datetime.now(IRT)

raw = json.load(open(f"{ROOT}/docs/reports/2026-09-04-raw.json", encoding="utf-8"))

def norm(t):
    return re.sub(r"[^a-z0-9]", "", t.lower())

# index raw items by normalized title
by_norm = {norm(i["title"]): i for i in raw["items"]}

def find_url(*frags):
    """Find first raw item whose normalized title contains a fragment; return its url+source+date."""
    for f in frags:
        nf = norm(f)
        for k, i in by_norm.items():
            if nf in k:
                return i["url"], i["source"], (i.get("published") or "")[:10]
    return None, None, None

def item(title, summary, url_frag=None, official=None, source_override=None, date="2026-09-03"):
    url, src, pub = (None, None, None)
    if official:
        url, src = official, source_override or "official"
    elif url_frag:
        url, src, pub = find_url(*url_frag) if isinstance(url_frag, list) else find_url(url_frag)
    if source_override:
        src = source_override
    if pub:
        date = pub
    return {"title": title, "summary": summary, "url": url or "", "source": src or "", "date": date}

report = {
  "date": "2026-09-04",
  "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
  "highlights": [
    "OpenAI released GPT-6 Astra — first model rated Critical for cybersecurity: 100% on ExploitBench with PoC exploit requests blocked, computer-use, same-day in Azure AI Foundry. Skeptics push back on viral ARC-AGI-3 numbers.",
    "NVIDIA is buying Hugging Face for ~$13B — the home of open-weight models changes owners ('open and neutral,' NVIDIA vows); OpenAI separately subpoenaed over the earlier HF attack.",
    "Google shipped Gemini 3.8 Flash + Flash Cyber (coding/agentic fast tier) and WeatherNext 3 (hourly satellite forecasts, 50% better precipitation).",
    "Anthropic: Claude Fable 5.1 lands up to 45% cheaper + restricted Mythos 5.1; AMD confirms $5B investment; OpenAI's president admits Anthropic leads in ARR.",
    "ChatGPT, Claude and Grok suffered an unprecedented simultaneous outage; SpaceXAI apologized for Grok's 'compute partners' disruption.",
    "Open-source momentum: MBZUAI/IFM K2 Horizon fleet (6 models 0.9B–375B with training data), Tencent Hy4 preview, Google's Mantis vuln-discovery framework, NVIDIA local-AI push at IFA."
  ],
  "sections": [
    {"org": "OpenAI", "items": [
      item("GPT-6 Astra released — first model rated Critical for cybersecurity",
           "New frontier model with computer use ('sits down at your computer'), 100% on ExploitBench while blocking PoC exploit requests at inference. Official safety overview + Path-to-Astra published; live in ChatGPT and Azure AI Foundry day one. Caveat: viral 98.6% ARC-AGI-3 claims drew independent scrutiny.",
           official="https://openai.com/index/safety-overview-gpt-6-astra", source_override="OpenAI (official)", date="2026-09-03"),
      item("Daybreak for Frontline Defenders: $1B cybersecurity program",
           "OpenAI commits $1B to defend essential services and defenders without enterprise budgets — cyber focus is clearly Astra's launch theme.",
           official="https://openai.com/index/daybreak-for-frontline-defenders", source_override="OpenAI (official)", date="2026-09-03"),
      item("OpenAI subpoenaed over Hugging Face attack",
           "Federal subpoena tied to the earlier Hugging Face incident breach — security scrutiny of the supply chain continues.",
           url_frag=["OpenAI Subpoenaed Over Hugging Face Attack"], source_override="WSJ", date="2026-09-03"),
      item("OpenAI president: Anthropic surpasses OpenAI in ARR and valuation",
           "A notable competitive admission from OpenAI's own president — the enterprise coding-agent market has shifted under ChatGPT.",
           url_frag=["Anthropic surpasses OpenAI in ARR and valuation"], source_override="TradingView", date="2026-09-04")
    ]},
    {"org": "Anthropic (Claude)", "items": [
      item("Claude Fable 5.1: smarter, faster, up to 45% cheaper",
           "Fable line refresh with anti-distillation protections; up to 45% cheaper than Fable 5 — a direct pricing attack aimed at high-volume coding workloads.",
           url_frag=["Claude Fable 5.1 vs Fable 5"], source_override="Memeburn", date="2026-09-03"),
      item("Mythos 5.1 (restricted) for advanced research",
           "Restricted-access variant; coverage says most bugs it found had 'never been checked by a human' — explaining the tight gating.",
           url_frag=["restricted Mythos 5.1 for advanced research"], source_override="EdTech Innovation Hub", date="2026-09-03"),
      item("AMD invests $5B in Anthropic; Claude headed to Disney Cruise ships",
           "Confirmed investment pairs AMD silicon with Claude distribution in consumer venues.",
           url_frag=["AMD Invests $5B In Anthropic"], source_override="Mshale", date="2026-09-04"),
      item("Amadeus brings travel tech into Claude Code and Cowork",
           "Travel-industry APIs land inside Claude's developer surfaces — another vertical integration for Claude Code.",
           url_frag=["Amadeus Brings Travel Tech Into Claude Code"], source_override="Skift", date="2026-09-03")
    ]},
    {"org": "Google DeepMind", "items": [
      item("Gemini 3.8 Flash and 3.8 Flash Cyber released",
           "New fast tier aimed at coding and agentic tasks, plus a security-tuned Cyber variant — goes straight at the same workloads as Claude Fable 5.1 and GPT-6 Astra-lite.",
           official="https://deepmind.google/blog/introducing-gemini-3-8-flash-and-38-flash-cyber/", source_override="Google DeepMind (official)", date="2026-09-02"),
      item("WeatherNext 3: most advanced global weather AI model",
           "Hourly forecasts driven by live satellite data; 50% more accurate precipitation; already live in Search and Gemini.",
           official="https://blog.google/innovation-and-ai/models-and-research/google-deepmind/introducing-weathernext-3/", source_override="Google (official)", date="2026-09-03"),
      item("Mantis: Google open-sources vulnerability-discovery framework",
           "Framework automating vulnerability discovery, released with full details — a security sibling to its Cyber model push (which shaved 7% off Palantir).",
           url_frag=["Mantis, an open-source framework"], source_override="GIGAZINE", date="2026-09-04")
    ]},
    {"org": "Meta AI", "items": [
      item("Muse Spark 1.3 claims parity with Claude and OpenAI flagships",
           "Meta says its newest model matches Anthropic/OpenAI flagships with coding and agentic gains; stock rose 4% on the claim. Parity is vendor-claimed — await independent benchmarks.",
           url_frag=["Muse Spark 1.3 Claims Parity"], source_override="247wallst", date="2026-09-03"),
      item("Zuckerberg tells Trump a national AI regulator is a flawed idea",
           "Meta's CEO pushes back against a US national AI regulator in a direct pitch to the White House.",
           url_frag=["Opposes National AI Regulatory Agency"], source_override="ababnews", date="2026-09-03")
    ]},
    {"org": "Microsoft AI", "items": [
      item("GPT-6 Astra available day one in Microsoft Foundry",
           "Nadella says Azure customers are already using Astra — the OpenAI partnership keeps delivering first to Azure.",
           url_frag=["now available in Microsoft Foundry"], source_override="Microsoft Azure (official)", date="2026-09-03"),
      item("Microsoft restructures reporting into two segments; Azure revenue quarterly",
           "From FY27 Microsoft reports in two segments and discloses Azure quarterly — a transparency reset as AI reshapes the company (fiscal-year revenue surprise: $101.9B quarter).",
           url_frag=["restructures reporting into two segments"], source_override="Tech Observer Magazine", date="2026-09-03")
    ]},
    {"org": "xAI (Grok)", "items": [
      item("Grok Bot for enterprises, with free trial",
           "xAI launches persistent enterprise agents (design post: 'a world of persistent agents') with a free-trial offer.",
           url_frag=["Designing Grok Bot for a world of persistent agents"], source_override="X.ai (official)", date="2026-09-03"),
      item("SpaceXAI apologizes for outage that hit Grok and 'compute partners'",
           "The Grok compute operator apologized for the multi-platform outage; Musk vowed corrective action.",
           url_frag=["SpaceXAI Apologizes For Outage"], source_override="Engadget", date="2026-09-03")
    ]},
    {"org": "Mistral AI", "items": [
      item("Côte d'Ivoire partners with Mistral AI for national digital transformation",
           "A second African state deal for Mistral — sovereign-AI positioning outside the US/China duopoly.",
           url_frag=["Côte d'Ivoire Partners with Mistral AI"], source_override="TechAfrica News", date="2026-09-03")
    ]},
    {"org": "NVIDIA", "items": [
      item("NVIDIA to acquire Hugging Face for ~$13B",
           "The de-facto home of open-weight models changes owners. NVIDIA vows it stays 'open and neutral'; antitrust questions are immediate; Reuters frames it as a $13B bet on open AI. The three HF founders become billionaires.",
           official="https://blogs.nvidia.com/blog/nvidia-to-acquire-hugging-face/", source_override="NVIDIA (official) + Reuters", date="2026-09-03"),
      item("Vera — NVIDIA's first CPU built for agents — is shipping",
           "Agent-era CPU now shipping, anchoring Vera Rubin NVL72 systems (up-to-30x perf/watt claims for agent inference).",
           url_frag=["Delivering Vera"], source_override="NVIDIA blog (official)", date="2026-08-27"),
      item("RTX Spark PCs and local-AI tooling at IFA 2026",
           "Local AI push: RTX Spark PCs plus a simplified local-inference stack for 24GB+ GPUs, with vLLM/llama.cpp optimizations — relevant if you run models on your own box.",
           url_frag=["Sparks Fly: NVIDIA Accelerates Local AI at IFA 2026"], source_override="NVIDIA blog (official)", date="2026-09-03"),
      item("NVIDIA plans $2.5B investment in Thinking Machines Lab",
           "Part of an expanded AI investment map that now includes Hugging Face and Thinking Machines Lab.",
           url_frag=["$2.5 Billion Investment in Thinking Machines Lab"], source_override="TradingKey", date="2026-09-04")
    ]},
    {"org": "Incidents & Outages", "items": [
      item("ChatGPT, Claude and Grok hit by unprecedented simultaneous outage",
           "Near-simultaneous outages across frontier chatbots (some reports include Gemini), amid a broader Microsoft 365 disruption. First event of its kind at this scale — a reminder to keep fallback providers configured.",
           url_frag=["Widespread AI outage underway"], source_override="Axios + multiple outlets", date="2026-09-03")
    ]},
    {"org": "Open Source AI", "items": [
      item("K2 Horizon: six fully open models from 0.9B to 375B, training data included",
           "MBZUAI's Institute of Foundation Models launches the largest fully open-source fleet to date — weights AND training data, spanning laptop-class to frontier scale.",
           url_frag=["Largest Fully Open-Source Fleet of AI Models"], source_override="PR Newswire", date="2026-09-03"),
      item("Tencent opens Hy4 preview in an open-source AI push",
           "Tencent's next open model line enters preview — the Chinese open-weights cadence continues.",
           url_frag=["Tencent opens Hy4 preview"], source_override="CFOtech Asia", date="2026-09-03")
    ]},
    {"org": "Industry & Funding", "items": [
      item("Moonshot AI files confidentially for Hong Kong IPO (~$50B cited)",
           "The Kimi K3 maker files for a HK listing — a major Chinese AI liquidity event; valuation talk around $50B.",
           url_frag=["Moonshot AI files confidential for Hong Kong IPO"], source_override="디지털투데이 / Economic Times", date="2026-09-04"),
      item("Crusoe valued at $30B after new funding",
           "The AI-cloud/data-center operator's round marks another step up in private AI infra valuations.",
           url_frag=["Crusoe valued at $30 billion"], source_override="Economic Times", date="2026-09-04"),
      item("Thinking Machines eyes $1B at $40B valuation",
           "Mira Murati's lab raising at a ~5x step-up — watch for what ships to justify it.",
           url_frag=["Thinking Machines Eyes $1 Billion Funding"], source_override="Whalesbook", date="2026-09-03"),
      item("Broadcom's AI chip revenue triples to $16.7B — custom silicon undercuts NVIDIA",
           "Hyperscaler custom silicon is now a real NVIDIA counterweight; Q4 guidance still disappointed the street.",
           url_frag=["Broadcom's AI chip revenue triples"], source_override="Martin Cid Magazine", date="2026-09-04")
    ]},
    {"org": "Policy & Regulation", "items": [
      item("Rare US-China consensus at G20 gives AI 'an easier run'",
           "G20 language reflects an unexpected US–China alignment on AI development — dampening some fragmentation scenarios.",
           url_frag=["rare US-China consensus at G20"], source_override="CNBC TV18", date="2026-09-04"),
      item("Sanders bill would ban artificial superintelligence — 20-year jail terms",
           "A fringe-but-headline bill to ban ASI development introduced in the Senate; near-zero passage odds but signals escalating safety politics. Single-outlet coverage — signal, not confirmed momentum.",
           url_frag=["Bill to Ban Artificial Superintelligence"], source_override="pasqualepillitteri.it", date="2026-09-03")
    ]}
  ]
}

# verify every item got a URL; flag misses
missing = [(s["org"], i["title"]) for s in report["sections"] for i in s["items"] if not i["url"]]
if missing:
    print("MISSING URLS:")
    for m in missing: print("  -", m)

out = f"{ROOT}/docs/reports/2026-09-04.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=1)
n_items = sum(len(s["items"]) for s in report["sections"])
print(f"wrote {out}: {len(report['sections'])} sections, {n_items} items")

# update reports index.json
idx_path = f"{ROOT}/docs/reports/index.json"
idx = json.load(open(idx_path, encoding="utf-8"))
print("index type:", type(idx).__name__, json.dumps(idx)[:200])
