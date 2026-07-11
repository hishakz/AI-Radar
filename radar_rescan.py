#!/usr/bin/env python3
"""
AI Inspection Radar — Daily Auto-Rescan
Runs every morning at 09:30 KSA (UTC+3 = 06:30 UTC)

AUTO-REFRESH SCHEDULE:
  ✅ DAILY  → AI Global Signals (new news)
  ✅ DAILY  → Market Intel: Stock "why" context (13 stocks, 2 Haiku calls)
  ✅ DAILY  → Market Intel: Risk signals (5 items)
  ✅ WEEKLY → Market Intel: Opportunity vectors (6 themes, runs on Sunday KSA)
  ❌ MANUAL → Stock ratings (BUY/WATCH/CAUTION) — edit STOCK_WATCHLIST below
  ❌ MANUAL → INSPECT cards, VECTORS (editorial content)

SETUP:
  pip install anthropic schedule pytz requests

RUN ONCE:
  python radar_rescan.py --now

DEPLOY ON GITHUB ACTIONS (see radar_rescan.yml):
  Runs in the cloud — no local machine needed.
"""

import anthropic
import schedule
import time
import sys
import json
import re
import os
from datetime import datetime
import pytz

# ─── CONFIG ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_KEY_HERE")
DASHBOARD_PATH    = os.environ.get("DASHBOARD_PATH",    "./ai_radar_bilingual.html")
KSA_TZ            = pytz.timezone("Asia/Riyadh")
SCAN_TIME_KSA     = "09:30"
LOG_FILE          = "./radar_rescan.log"

# ─── DYNAMIC YEAR CONFIG ─────────────────────────────────────────────────────
_NOW         = datetime.now()
CURRENT_YEAR = _NOW.year
NEXT_YEAR    = _NOW.year + 1

# ─── NEWS SCAN DOMAINS (daily) ───────────────────────────────────────────────
SCAN_DOMAINS = [
    f"smart city AI inspection continuous monitoring autonomous {CURRENT_YEAR}",
    f"AI construction excavation inspection drones robots {CURRENT_YEAR}",
    f"AI food safety restaurant inspection automated {CURRENT_YEAR}",
    f"AI building housing inspection smart technology {CURRENT_YEAR}",
    f"AI inspection policy regulation government {CURRENT_YEAR}",
    f"AI model release Anthropic OpenAI Google {CURRENT_YEAR}",
    f"AI security cybersecurity vulnerability {CURRENT_YEAR}",
    f"AI investment funding IPO {CURRENT_YEAR}",
    f"AI predictions outlook {NEXT_YEAR} forecast trends inspection smart city",
]

# ─── MARKET INTEL CONFIG — EDITORIAL SECTION ─────────────────────────────────
# Edit STOCK_WATCHLIST to change tickers or ratings (BUY/WATCH/CAUTION/IPO)
# The "why" text is auto-generated daily — do NOT edit it here
STOCK_WATCHLIST = [
    # Infrastructure plays
    {"ticker": "NVDA",   "name": "NVIDIA",                  "signal": "buy",     "name_ar": "NVIDIA"},
    {"ticker": "MSFT",   "name": "Microsoft",               "signal": "buy",     "name_ar": "Microsoft"},
    {"ticker": "AVGO",   "name": "Broadcom",                "signal": "buy",     "name_ar": "Broadcom"},
    {"ticker": "AMD",    "name": "Advanced Micro Devices",  "signal": "buy",     "name_ar": "Advanced Micro Devices"},
    # Cybersecurity
    {"ticker": "CRWD",   "name": "CrowdStrike",             "signal": "buy",     "name_ar": "CrowdStrike"},
    {"ticker": "PANW",   "name": "Palo Alto Networks",      "signal": "buy",     "name_ar": "Palo Alto Networks"},
    # Cloud / Hyperscalers
    {"ticker": "GOOG",   "name": "Alphabet / Google",       "signal": "watch",   "name_ar": "Alphabet / Google"},
    {"ticker": "AMZN",   "name": "Amazon / AWS",            "signal": "watch",   "name_ar": "Amazon / AWS"},
    {"ticker": "CRWV",   "name": "CoreWeave",               "signal": "watch",   "name_ar": "CoreWeave"},
    {"ticker": "IBM",    "name": "IBM",                     "signal": "watch",   "name_ar": "IBM"},
    {"ticker": "META",   "name": "Meta Platforms",          "signal": "watch",   "name_ar": "Meta Platforms"},
    # Caution
    {"ticker": "TSLA",   "name": "Tesla",                   "signal": "caution", "name_ar": "Tesla"},
    # IPO Pipeline
    {"ticker": "SPCX",   "name": "SpaceX / xAI",           "signal": "ipo",     "name_ar": "SpaceX / xAI"},
    {"ticker": "OPENAI", "name": "OpenAI (Pre-IPO)",        "signal": "ipo",     "name_ar": "OpenAI (ما قبل الاكتتاب)"},
    {"ticker": "ANTH",   "name": "Anthropic (Pre-IPO)",     "signal": "ipo",     "name_ar": "Anthropic (ما قبل الاكتتاب)"},
]

# Opportunity themes — titles/tickers are editorial; body text is auto-updated weekly
OPP_THEMES = [
    {
        "title_en": "AI Inference Infrastructure",
        "title_ar": "البنية التحتية للاستدلال بالذكاء الاصطناعي",
        "horizon_en": "12-24 months", "horizon_ar": "12-24 شهراً",
        "tickers": ["NVDA", "AVGO", "CRWV", "AMZN", "GOOG"],
    },
    {
        "title_en": "AI Cybersecurity & Vulnerability Remediation",
        "title_ar": "الأمن السيبراني بالذكاء الاصطناعي ومعالجة الثغرات",
        "horizon_en": "6-12 months", "horizon_ar": "6-12 شهراً",
        "tickers": ["CRWD", "PANW", "ZS", "IBM"],
    },
    {
        "title_en": "Agentic AI Platforms & Orchestration",
        "title_ar": "منصات الذكاء الاصطناعي الوكيلي والتنسيق",
        "horizon_en": "Now-12 months", "horizon_ar": "الآن-12 شهراً",
        "tickers": ["GOOG", "MSFT", "AMZN", "SFDC"],
    },
    {
        "title_en": "Smart City & AI Inspection Technology",
        "title_ar": "تقنية المدن الذكية والتفتيش بالذكاء الاصطناعي",
        "horizon_en": "2-4 years", "horizon_ar": "2-4 سنوات",
        "tickers": ["NVDA", "MSFT", "GOOG"],
    },
    {
        "title_en": "AI IPO Pipeline — 2026 Wave",
        "title_ar": "موجة اكتتابات الذكاء الاصطناعي 2026",
        "horizon_en": "3-9 months", "horizon_ar": "3-9 أشهر",
        "tickers": ["SPCX", "OPENAI", "ANTH"],
    },
    {
        "title_en": "EU AI Act Compliance Vendors",
        "title_ar": "موردو امتثال قانون EU AI Act",
        "horizon_en": "Now-3 months", "horizon_ar": "الآن-3 أشهر",
        "tickers": ["IBM", "MSFT", "ORCL"],
    },
]

# ─── LOGGING ─────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now(KSA_TZ).strftime("%Y-%m-%d %H:%M:%S KSA")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def _safe(text):
    """Escape single quotes and backticks for JS string insertion."""
    return text.replace("\\", "\\\\").replace("'", "\\'").replace("`", "'")

def _replace_marker(html, marker_name, new_content):
    """Replace content between // ══ MARKER-START ══ and // ══ MARKER-END ══"""
    pattern = rf'// ══ {re.escape(marker_name)}-START ══.*?// ══ {re.escape(marker_name)}-END ══'
    replacement = f'// ══ {marker_name}-START ══\n{new_content}\n// ══ {marker_name}-END ══'
    result = re.sub(pattern, replacement, html, flags=re.DOTALL)
    if result == html:
        log(f"  ⚠ Marker {marker_name} not found in dashboard")
    return result

def _call_haiku(client, prompt, today):
    """Single Haiku + web_search call. Returns response text or None."""
    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": prompt}]
        )
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text += block.text
        return text
    except Exception as e:
        log(f"  ✗ Haiku call failed: {e}")
        return None

# ─── MAIN SCAN ────────────────────────────────────────────────────────────────
def run_rescan():
    log("═══ DAILY RESCAN STARTED ═══")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    today  = datetime.now(KSA_TZ).strftime("%B %d, %Y")
    now_ksa = datetime.now(KSA_TZ)

    # ── 1. NEWS SIGNALS (daily) ──────────────────────────────────────────────
    all_signals = []
    for domain_query in SCAN_DOMAINS:
        log(f"  Scanning: {domain_query}")
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1000,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{
                    "role": "user",
                    "content": f"""Today is {today}. Search the web for the latest news on: {domain_query}

Return a JSON array of up to 3 NEW signals published in the last 7 days.
Each object must have these exact keys:
  t: title (string, max 120 chars)
  s: summary (string, max 300 chars — include specific numbers/dates/names)
  url: source URL (string)
  cat: one of: Release | Breakthrough | Policy | Research | Funding | Security
  d: exact date like "{today}" or "2 days ago" or "June 3, {CURRENT_YEAR}" — never hardcode a year

Return ONLY a valid JSON array. No markdown, no preamble."""
                }]
            )
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
            json_match = re.search(r'\[[\s\S]*?\]', text)
            if json_match:
                signals = json.loads(json_match.group())
                for sig in signals:
                    sig["query"] = domain_query
                all_signals.extend(signals)
                log(f"    ✓ {len(signals)} signals found")
            else:
                log(f"    ✗ No JSON found")
        except Exception as e:
            log(f"    ✗ Error: {e}")
        time.sleep(2)

    log(f"  Total new signals: {len(all_signals)}")
    if all_signals:
        update_dashboard(all_signals, today)
        send_summary(all_signals, today)
    else:
        log("  No new signals — updating timestamp only")
        update_scan_timestamp(today)

    # ── 2. MARKET INTEL: RISK SIGNALS (daily) ────────────────────────────────
    update_inv_risks(client, today)

    # ── 3. MARKET INTEL: STOCK "WHY" TEXT (daily) ────────────────────────────
    update_inv_stocks(client, today)

    # ── 4. MARKET INTEL: OPPORTUNITY VECTORS (weekly — Sunday KSA) ───────────
    if now_ksa.weekday() == 6:   # 6 = Sunday
        log("  Sunday: running weekly opportunity vector update...")
        update_inv_opps(client, today)
    else:
        day_names = {0:'Mon',1:'Tue',2:'Wed',3:'Thu',4:'Fri',5:'Sat',6:'Sun'}
        log(f"  Today is {day_names[now_ksa.weekday()]} — opportunity update runs on Sunday only")

    log("═══ RESCAN COMPLETE ═══\n")

# ─── MARKET INTEL UPDATER 1: RISK SIGNALS (daily) ────────────────────────────
def update_inv_risks(client, today):
    log("  [Market Intel] Updating risk signals...")
    prompt = f"""Today is {today}. Search for the top 5 current investment risk signals for AI sector stocks.
Focus on: regulatory deadlines, pricing/competition, capex/valuation concerns, geopolitical risks, legal proceedings.

Return a JSON array of exactly 5 objects:
  icon: one emoji
  title: short risk title in English (max 60 chars)
  title_ar: same title in Arabic (max 60 chars)
  body: 2-sentence explanation in English (max 200 chars, include specific numbers/dates)
  body_ar: Arabic translation of body (max 220 chars)

Return ONLY valid JSON. No markdown, no preamble."""

    text = _call_haiku(client, prompt, today)
    if not text:
        return

    json_match = re.search(r'\[[\s\S]*?\]', text)
    if not json_match:
        log("  ✗ No JSON in risk response — keeping existing")
        return
    try:
        risks = json.loads(json_match.group())
        if len(risks) < 3:
            log(f"  ✗ Only {len(risks)} risks — keeping existing")
            return
    except Exception as e:
        log(f"  ✗ JSON parse error: {e}")
        return

    en_items, ar_items = [], []
    for r in risks[:5]:
        icon     = _safe(r.get("icon", "⚠️"))
        title    = _safe(r.get("title", ""))
        title_ar = _safe(r.get("title_ar", r.get("title", "")))
        body     = _safe(r.get("body", ""))
        body_ar  = _safe(r.get("body_ar", r.get("body", "")))
        en_items.append(f"  {{ icon:'{icon}', title:'{title}', body:'{body}' }}")
        ar_items.append(f"  {{ icon:'{icon}', title:'{title_ar}', body:'{body_ar}' }}")

    with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    html = _replace_marker(html, "INV-RISKS-EN", f"let INV_RISKS_EN = [\n" + ",\n".join(en_items) + "\n];")
    html = _replace_marker(html, "INV-RISKS-AR", f"let INV_RISKS_AR = [\n" + ",\n".join(ar_items) + "\n];")

    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"  ✓ Risk signals updated ({len(risks[:5])} items)")

# ─── MARKET INTEL UPDATER 2: STOCK "WHY" TEXT (daily) ────────────────────────
def update_inv_stocks(client, today):
    log("  [Market Intel] Updating stock signals...")

    # Split into 2 batches to stay within 1000 token limit
    batch1 = STOCK_WATCHLIST[:8]
    batch2 = STOCK_WATCHLIST[8:]
    why_map = {}  # ticker → {why_en, why_ar}

    for batch_num, batch in enumerate([batch1, batch2], 1):
        tickers_str = ", ".join(f"{s['ticker']} ({s['name']})" for s in batch)
        prompt = f"""Today is {today}. Search for today's latest news on these AI sector stocks: {tickers_str}

For each stock, provide current investment context based on today's news.
Return a JSON array — one object per stock:
  ticker: string (exact ticker from input)
  why_en: 1-2 sentences in English, max 130 chars, specific to latest news
  why_ar: Arabic translation of why_en, max 150 chars

Return ONLY valid JSON array. No markdown, no preamble."""

        text = _call_haiku(client, prompt, today)
        if not text:
            log(f"  ✗ Batch {batch_num} failed — skipping")
            continue

        json_match = re.search(r'\[[\s\S]*?\]', text)
        if not json_match:
            log(f"  ✗ No JSON in batch {batch_num}")
            continue
        try:
            results = json.loads(json_match.group())
            for item in results:
                t = item.get("ticker", "").upper()
                if t:
                    why_map[t] = {
                        "why_en": item.get("why_en", ""),
                        "why_ar": item.get("why_ar", item.get("why_en", "")),
                    }
            log(f"  ✓ Batch {batch_num}: {len(results)} stocks updated")
        except Exception as e:
            log(f"  ✗ Batch {batch_num} parse error: {e}")

        time.sleep(2)

    if not why_map:
        log("  ✗ No stock data retrieved — keeping existing")
        return

    # Build JS arrays using static ratings + dynamic why text
    en_items, ar_items = [], []
    for s in STOCK_WATCHLIST:
        ticker = s["ticker"]
        name   = _safe(s["name"])
        signal = s["signal"]
        name_ar = _safe(s["name_ar"])
        w = why_map.get(ticker, {})
        why_en = _safe(w.get("why_en", "Latest data loading..."))
        why_ar = _safe(w.get("why_ar", "جارٍ تحميل البيانات..."))
        en_items.append(f"  {{ ticker:'{ticker}', name:'{name}', signal:'{signal}', why:'{why_en}' }}")
        ar_items.append(f"  {{ ticker:'{ticker}', name:'{name_ar}', signal:'{signal}', why:'{why_ar}' }}")

    with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    html = _replace_marker(html, "INV-STOCKS-EN", f"let INV_STOCKS_EN = [\n" + ",\n".join(en_items) + "\n];")
    html = _replace_marker(html, "INV-STOCKS-AR", f"let INV_STOCKS_AR = [\n" + ",\n".join(ar_items) + "\n];")

    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"  ✓ Stock signals updated ({len(why_map)} tickers refreshed)")

# ─── MARKET INTEL UPDATER 3: OPPORTUNITY VECTORS (weekly) ────────────────────
def update_inv_opps(client, today):
    log("  [Market Intel] Updating opportunity vectors (weekly)...")

    themes_str = "\n".join(
        f"{i+1}. {t['title_en']} [{', '.join(t['tickers'])}]"
        for i, t in enumerate(OPP_THEMES)
    )

    prompt = f"""Today is {today}. Search for the latest developments relevant to these 6 AI investment opportunity themes:

{themes_str}

For each theme (in order), provide:
  body_en: 2-3 sentences in English (max 250 chars) with specific recent data points, company names, numbers
  body_ar: Arabic translation (max 280 chars)

Return a JSON array of exactly 6 objects with keys: theme_num (1-6), body_en, body_ar
Return ONLY valid JSON. No markdown, no preamble."""

    text = _call_haiku(client, prompt, today)
    if not text:
        return

    json_match = re.search(r'\[[\s\S]*?\]', text)
    if not json_match:
        log("  ✗ No JSON in opps response — keeping existing")
        return
    try:
        results = json.loads(json_match.group())
        if len(results) < 4:
            log(f"  ✗ Only {len(results)} opp themes — keeping existing")
            return
    except Exception as e:
        log(f"  ✗ Opps parse error: {e}")
        return

    # Build JS arrays preserving static titles/tickers, updating body only
    result_map = {r.get("theme_num", i+1): r for i, r in enumerate(results)}

    en_items, ar_items = [], []
    for i, theme in enumerate(OPP_THEMES):
        r = result_map.get(i + 1, {})
        title_en  = _safe(theme["title_en"])
        title_ar  = _safe(theme["title_ar"])
        horizon_en = _safe(theme["horizon_en"])
        horizon_ar = _safe(theme["horizon_ar"])
        tickers   = json.dumps(theme["tickers"])
        body_en   = _safe(r.get("body_en", "Latest data loading..."))
        body_ar   = _safe(r.get("body_ar", "جارٍ تحميل البيانات..."))
        en_items.append(
            f"  {{ title:'{title_en}', horizon:'{horizon_en}', tickers:{tickers}, body:'{body_en}' }}"
        )
        ar_items.append(
            f"  {{ title:'{title_ar}', horizon:'{horizon_ar}', tickers:{tickers}, body:'{body_ar}' }}"
        )

    with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    html = _replace_marker(html, "INV-OPPS-EN", f"let INV_OPPS_EN = [\n" + ",\n".join(en_items) + "\n];")
    html = _replace_marker(html, "INV-OPPS-AR", f"let INV_OPPS_AR = [\n" + ",\n".join(ar_items) + "\n];")

    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    log(f"  ✓ Opportunity vectors updated ({len(OPP_THEMES)} themes)")

# ─── TIMESTAMP-ONLY UPDATE ────────────────────────────────────────────────────
def update_scan_timestamp(today):
    try:
        with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
            html = f.read()
        marker   = f"// Last rescan: {today} (0 new signals)"
        old_pat  = r"// Last rescan: [^\n]+"
        if re.search(old_pat, html):
            html = re.sub(old_pat, marker, html)
        else:
            html = html.replace(
                "// ════════════════════════════════════════════════════════════════\n// STATE",
                f"{marker}\n// ════════════════════════════════════════════════════════════════\n// STATE"
            )
        with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
            f.write(html)
        log(f"  ✓ Timestamp updated: {today}")
    except Exception as e:
        log(f"  ✗ Timestamp update failed: {e}")

# ─── DOMAIN MAPPER ───────────────────────────────────────────────────────────
def map_domains(query):
    q = query.lower()
    domains = []
    if "smart city" in q or "continuous monitoring" in q:
        domains.append("smart-city")
    if "construction" in q or "excavation" in q or "drones" in q:
        domains.append("construction")
    if "food" in q or "restaurant" in q:
        domains.append("food")
    if "building" in q or "housing" in q:
        domains.append("housing")
    if "policy" in q or "regulation" in q or "government" in q:
        domains.append("policy")
    if "security" in q or "cyber" in q or "glasswing" in q:
        domains.append("security")
    if "model" in q or "anthropic" in q or "openai" in q or "google" in q:
        domains.append("ai-models")
    if "investment" in q or "funding" in q or "ipo" in q:
        domains.append("funding")
    if "research" in q:
        domains.append("research")
    return domains if domains else ["ai-models"]

# ─── DASHBOARD SIGNAL UPDATER ─────────────────────────────────────────────────
def update_dashboard(signals, today):
    log("  Updating dashboard HTML...")
    try:
        with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
            html = f.read()

        existing_urls   = set(re.findall(r"url:'([^']{10,})'", html))
        existing_titles = [t.lower() for t in re.findall(r"en:\{t:'([^']{10,80})'", html)]

        def is_duplicate(sig):
            url   = sig.get("url", "").strip()
            title = sig.get("t", "").strip().lower()
            if url and url in existing_urls:
                return True
            words = title.split()
            for i in range(max(0, len(words) - 5)):
                phrase = " ".join(words[i:i+6])
                if any(phrase in et for et in existing_titles):
                    return True
            return False

        fresh, skipped = [], 0
        for sig in signals:
            if is_duplicate(sig):
                skipped += 1
            else:
                fresh.append(sig)

        if skipped:
            log(f"  ↩ {skipped} duplicate(s) skipped")
        if not fresh:
            log("  All signals already exist — nothing new to inject")
            update_scan_timestamp(today)
            return
        log(f"  ✚ {len(fresh)} new signals to inject")

        new_js_signals = []
        for sig in fresh:
            url     = sig.get("url", "")
            cat     = sig.get("cat", "Research")
            d_str   = sig.get("d", "Today")
            title   = _safe(sig.get("t", ""))
            summary = _safe(sig.get("s", ""))
            doms    = json.dumps(map_domains(sig.get("query", "")))
            js = (f"  {{domains:{doms},url:\'{url}\',"
                  f"\n   en:{{t:\'{title}\',cat:\'{cat}\',d:\'{d_str} AUTO\',s:\'{summary}\'}},"
                  f"\n   ar:{{t:\'{title}\',cat:\'{cat}\',d:\'{d_str} تلقائي\',s:\'{summary}\'}}}},")
            new_js_signals.append(js)

        block  = "\n  // ══ AUTO-RESCAN " + today.upper() + " ══\n"
        block += "\n".join(new_js_signals) + "\n"
        html   = html.replace("const AI_SIGNALS=[", "const AI_SIGNALS=[\n" + block)

        now        = datetime.now(KSA_TZ)
        date_short = now.strftime("%b %-d, %Y")
        date_ar    = f"{now.day} {get_ar_month(now.month)} {now.year}"
        count      = html.count("en:{t:'")
        html = re.sub(r"scanDate:'[^']+', sigCount:'[^']+ signals'",
                      f"scanDate:\'{date_short}\', sigCount:\'{count} signals\'", html)
        html = re.sub(r"scanDate:'[^']+', sigCount:'[^']+ إشارة'",
                      f"scanDate:\'{date_ar}\', sigCount:\'{count} إشارة\'", html)

        with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
            f.write(html)
        log(f"  ✓ {len(fresh)} added, {skipped} skipped, {count} total signals")

    except Exception as e:
        log(f"  ✗ Dashboard update failed: {e}")

def get_ar_month(m):
    return {1:'يناير',2:'فبراير',3:'مارس',4:'أبريل',5:'مايو',
            6:'يونيو',7:'يوليو',8:'أغسطس',9:'سبتمبر',10:'أكتوبر',
            11:'نوفمبر',12:'ديسمبر'}.get(m, '')

# ─── SUMMARY PRINTER ─────────────────────────────────────────────────────────
def send_summary(signals, today):
    log(f"\n  ┌─── SCAN SUMMARY — {today} ───")
    for i, sig in enumerate(signals, 1):
        log(f"  │ {i:02d}. [{sig.get('cat','?')}] {sig.get('t','')[:80]}")
    log(f"  └─── {len(signals)} total signals ───\n")

# ─── SCHEDULER ────────────────────────────────────────────────────────────────
def scheduled_job():
    now_ksa = datetime.now(KSA_TZ)
    log(f"Scheduler triggered at {now_ksa.strftime('%H:%M KSA')}")
    run_rescan()

if __name__ == "__main__":
    if "--now" in sys.argv:
        log("Manual run triggered (--now flag)")
        run_rescan()
    else:
        log(f"Scheduler started — will rescan daily at {SCAN_TIME_KSA} KSA")
        log(f"Dashboard: {DASHBOARD_PATH}")
        log("Ctrl+C to stop\n")
        schedule.every().day.at("06:30").do(scheduled_job)
        last_run_file = ".last_rescan"
        today_str = datetime.now(KSA_TZ).strftime("%Y-%m-%d")
        if not os.path.exists(last_run_file) or \
           open(last_run_file).read().strip() != today_str:
            log("No scan yet today — running initial scan...")
            run_rescan()
            with open(last_run_file, "w") as f:
                f.write(today_str)
        while True:
            schedule.run_pending()
            time.sleep(60)
