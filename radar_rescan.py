#!/usr/bin/env python3
"""
AI Inspection Radar — Daily Auto-Rescan  (v2, Sep 2026)
Runs every morning at 09:30 KSA (UTC+3 = 06:30 UTC)

WHAT IS AUTO-GENERATED (nothing news-like is hardcoded any more):
  ✅ DAILY  → AI Global Signals: new items, translated to Arabic, absolute dates, pruned after RETENTION_DAYS
  ✅ DAILY  → Market Intel: stock rating (buy/watch/caution/ipo) + "why" text, all tickers
  ✅ DAILY  → Market Intel: 5 risk signals
  ✅ WEEKLY → Market Intel: opportunity vectors — horizon, tickers, body (Sunday KSA)
  ✅ WEEKLY → INSPECT cards: 4 sectors × 4 cards, bilingual (Sunday KSA)
  ✅ FIRST RUN → everything above regenerates immediately while SEED_PENDING=true in the HTML
  ❌ MANUAL → VECTORS + decision table + roadmap (NCIM's own strategic positions, not news)

FIXES vs v1:
  • max_tokens raised 1000 → MAX_TOKENS (was truncating every bilingual JSON reply → silent "keeping existing")
  • JSON extracted by bracket-depth scan, not a non-greedy regex that stopped at the first "]"
  • On any failure the previous text is kept; the "Latest data loading..." placeholder is never written
  • Signal dates stored as absolute dates (no more frozen "2 hours ago")
  • Signals translated to Arabic instead of copying English into the ar block
  • "Investment data as of" label derived from invDataDate (no hardcoded date in the HTML)

SETUP:    pip install anthropic schedule pytz
RUN ONCE: python radar_rescan.py --now
"""

import anthropic
import schedule
import time
import sys
import json
import re
import os
from datetime import datetime, timedelta
import pytz

# ─── CONFIG ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "YOUR_KEY_HERE")
DASHBOARD_PATH    = os.environ.get("DASHBOARD_PATH", "./ai_radar_bilingual.html")
KSA_TZ            = pytz.timezone("Asia/Riyadh")
SCAN_TIME_KSA     = "09:30"
LOG_FILE          = "./radar_rescan.log"
MODEL             = "claude-haiku-4-5-20251001"
MAX_TOKENS        = 6000          # bilingual JSON needs headroom; 1000 was the root cause of stale panels
RETENTION_DAYS    = int(os.environ.get("RETENTION_DAYS", "90"))   # signals older than this are pruned
WEEKLY_DAY        = 6             # 6 = Sunday (Python weekday)

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

# ─── MARKET INTEL CONFIG (tickers only — ratings and text are generated) ─────
STOCK_WATCHLIST = [
    {"ticker": "NVDA",   "name": "NVIDIA",                 "name_ar": "NVIDIA"},
    {"ticker": "MSFT",   "name": "Microsoft",              "name_ar": "Microsoft"},
    {"ticker": "AVGO",   "name": "Broadcom",               "name_ar": "Broadcom"},
    {"ticker": "AMD",    "name": "Advanced Micro Devices", "name_ar": "Advanced Micro Devices"},
    {"ticker": "CRWD",   "name": "CrowdStrike",            "name_ar": "CrowdStrike"},
    {"ticker": "PANW",   "name": "Palo Alto Networks",     "name_ar": "Palo Alto Networks"},
    {"ticker": "GOOG",   "name": "Alphabet / Google",      "name_ar": "Alphabet / Google"},
    {"ticker": "AMZN",   "name": "Amazon / AWS",           "name_ar": "Amazon / AWS"},
    {"ticker": "CRWV",   "name": "CoreWeave",              "name_ar": "CoreWeave"},
    {"ticker": "IBM",    "name": "IBM",                    "name_ar": "IBM"},
    {"ticker": "META",   "name": "Meta Platforms",         "name_ar": "Meta Platforms"},
    {"ticker": "TSLA",   "name": "Tesla",                  "name_ar": "Tesla"},
    {"ticker": "SPCX",   "name": "SpaceX / xAI",           "name_ar": "SpaceX / xAI"},
    {"ticker": "OPENAI", "name": "OpenAI",                 "name_ar": "OpenAI"},
    {"ticker": "ANTH",   "name": "Anthropic",              "name_ar": "Anthropic"},
]
VALID_SIGNALS = {"buy", "watch", "caution", "ipo"}

# Opportunity themes — only the theme names are fixed; horizon, tickers and body are generated
OPP_THEMES = [
    {"title_en": "AI Inference Infrastructure",
     "title_ar": "البنية التحتية للاستدلال بالذكاء الاصطناعي"},
    {"title_en": "AI Cybersecurity & Vulnerability Remediation",
     "title_ar": "الأمن السيبراني بالذكاء الاصطناعي ومعالجة الثغرات"},
    {"title_en": "Agentic AI Platforms & Orchestration",
     "title_ar": "منصات الذكاء الاصطناعي الوكيلي والتنسيق"},
    {"title_en": "Smart City & AI Inspection Technology",
     "title_ar": "تقنية المدن الذكية والتفتيش بالذكاء الاصطناعي"},
    {"title_en": "AI IPO Pipeline",
     "title_ar": "خط اكتتابات الذكاء الاصطناعي"},
    {"title_en": "AI Regulation & Compliance Vendors",
     "title_ar": "موردو الامتثال لتنظيمات الذكاء الاصطناعي"},
]

# INSPECT sectors — cards are generated weekly from web search
INSPECT_SECTORS = [
    {"sec": "city",         "clr": "teal",  "label_en": "Smart City",   "label_ar": "مدن ذكية",
     "domains": ["smart-city"],
     "query": "AI continuous monitoring smart city inspection deployments municipalities cameras sensors digital twin"},
    {"sec": "construction", "clr": "amber", "label_en": "Construction", "label_ar": "بناء",
     "domains": ["construction"],
     "query": "AI construction site excavation inspection drones robots computer vision safety compliance"},
    {"sec": "food",         "clr": "green", "label_en": "Food Safety",  "label_ar": "سلامة غذائية",
     "domains": ["food"],
     "query": "AI food safety restaurant inspection automated kitchen monitoring hygiene compliance regulator"},
    {"sec": "housing",      "clr": "blue",  "label_en": "Buildings",    "label_ar": "مباني",
     "domains": ["housing"],
     "query": "AI building inspection housing code compliance permits remote virtual inspection technology"},
]
CARDS_PER_SECTOR = 4

# ─── LOGGING ─────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now(KSA_TZ).strftime("%Y-%m-%d %H:%M:%S KSA")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def _safe(text):
    """Make a string safe for insertion inside a single-quoted JS literal."""
    if text is None:
        text = ""
    text = str(text).replace("\r", " ").replace("\n", " ").strip()
    text = re.sub(r"\s{2,}", " ", text)
    return text.replace("\\", "\\\\").replace("'", "\\'").replace("`", "'")

def _read_html():
    with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
        return f.read()

def _write_html(html):
    with open(DASHBOARD_PATH, "w", encoding="utf-8") as f:
        f.write(html)

def _replace_marker(html, marker_name, new_content):
    """Replace content between // ══ NAME-START ══ and // ══ NAME-END ══ (literal search, no regex)."""
    start = f"// ══ {marker_name}-START ══"
    end   = f"// ══ {marker_name}-END ══"
    i = html.find(start); j = html.find(end)
    if i < 0 or j < 0 or j < i:
        log(f"  ⚠ Marker {marker_name} not found in dashboard")
        return html
    return html[:i] + start + "\n" + new_content + "\n" + html[j:]

def _extract_json_array(text):
    """Return the first complete top-level JSON array in text, or None (bracket-depth scan, string-aware)."""
    if not text:
        return None
    start = text.find("[")
    while start >= 0:
        depth, in_str, esc = 0, False, False
        for k in range(start, len(text)):
            ch = text[k]
            if in_str:
                if esc: esc = False
                elif ch == "\\": esc = True
                elif ch == '"': in_str = False
                continue
            if ch == '"': in_str = True
            elif ch == "[": depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    try:
                        val = json.loads(text[start:k+1])
                        if isinstance(val, list):
                            return val
                    except Exception:
                        pass
                    break
        start = text.find("[", start + 1)
    return None

def _call_haiku(client, prompt, max_tokens=MAX_TOKENS, use_search=True):
    """Single Haiku (+ optional web_search) call. Returns response text or None."""
    try:
        kwargs = dict(model=MODEL, max_tokens=max_tokens,
                      system="You are a data extraction engine. Reply with the requested JSON only — no prose, no markdown fences, no citations.",
                      messages=[{"role": "user", "content": prompt}])
        if use_search:
            kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search"}]
        response = client.messages.create(**kwargs)
        if getattr(response, "stop_reason", "") == "max_tokens":
            log("  ⚠ Response hit max_tokens — JSON may be truncated")
        return "".join(getattr(b, "text", "") for b in response.content)
    except Exception as e:
        log(f"  ✗ Haiku call failed: {e}")
        return None

def _ask_json(client, prompt, min_len=1, **kw):
    """Call Haiku and return a JSON list with at least min_len items, else None."""
    text = _call_haiku(client, prompt, **kw)
    arr = _extract_json_array(text)
    if arr is None:
        log("  ✗ No JSON array in response")
        return None
    if len(arr) < min_len:
        log(f"  ✗ Only {len(arr)} items (need {min_len})")
        return None
    return arr

AR_MONTHS = {1:'يناير',2:'فبراير',3:'مارس',4:'أبريل',5:'مايو',6:'يونيو',
             7:'يوليو',8:'أغسطس',9:'سبتمبر',10:'أكتوبر',11:'نوفمبر',12:'ديسمبر'}
EN_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January","February","March","April","May","June","July","August",
     "September","October","November","December"], 1)}

def _month_num(word):
    word = word.lower().rstrip(".")
    if word in EN_MONTHS: return EN_MONTHS[word]
    for k, v in EN_MONTHS.items():
        if len(word) >= 3 and k.startswith(word[:3]) and k.startswith(word):
            return v
    return None

def fmt_en(dt): return f"{dt.strftime('%B')} {dt.day}, {dt.year}"
def fmt_ar(dt): return f"{dt.day} {AR_MONTHS[dt.month]} {dt.year}"

def to_absolute_date(d_str, ref):
    """Convert any date string (ISO, 'Sep 3, 2026', '2 days ago', 'today', ...) to a datetime, anchored on ref."""
    s = (d_str or "").strip().lower()
    s = re.sub(r"\s*(auto|تلقائي)$", "", s)
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try: return datetime(int(m[1]), int(m[2]), int(m[3]))
        except ValueError: pass
    m = re.search(r"([a-z]+)\.?\s+(\d{1,2}),?\s+(\d{4})", s)
    if m and _month_num(m[1]):
        try: return datetime(int(m[3]), _month_num(m[1]), int(m[2]))
        except ValueError: pass
    m = re.search(r"(\d{1,2})\s+([a-z]+)\.?\s+(\d{4})", s)
    if m and _month_num(m[2]):
        try: return datetime(int(m[3]), _month_num(m[2]), int(m[1]))
        except ValueError: pass
    m = re.search(r"([a-z]+)\s+(\d{4})", s)          # "January 2026"
    if m and _month_num(m[1]):
        return datetime(int(m[2]), _month_num(m[1]), 1)
    if "today" in s or "hour" in s or "minute" in s or "just now" in s:
        return ref
    if "yesterday" in s: return ref - timedelta(days=1)
    m = re.search(r"(\d+)\s*day", s)
    if m: return ref - timedelta(days=int(m[1]))
    m = re.search(r"(\d+)\s*week", s)
    if m: return ref - timedelta(weeks=int(m[1]))
    if "week ago" in s or "a week" in s: return ref - timedelta(weeks=1)
    m = re.search(r"(\d+)\s*month", s)
    if m: return ref - timedelta(days=30*int(m[1]))
    if "month ago" in s: return ref - timedelta(days=30)
    return ref   # unknown → treat as published on scan day

# ─── MAIN SCAN ────────────────────────────────────────────────────────────────
def run_rescan():
    log("═══ DAILY RESCAN STARTED ═══")
    client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    now_ksa = datetime.now(KSA_TZ)
    today   = now_ksa.strftime("%B %d, %Y")
    ref     = datetime(now_ksa.year, now_ksa.month, now_ksa.day)

    html = _read_html()
    seed_pending = "const SEED_PENDING=true;" in html
    weekly_due   = now_ksa.weekday() == WEEKLY_DAY or seed_pending
    if seed_pending:
        log("  SEED_PENDING=true → forcing a full regeneration of every generated section")

    # 1. NEWS SIGNALS (daily)
    all_signals = []
    for domain_query in SCAN_DOMAINS:
        log(f"  Scanning: {domain_query}")
        prompt = f"""Today is {today}. Search the web for the latest news on: {domain_query}

Return a JSON array of up to 3 NEW signals published in the last 7 days.
Each object must have these exact keys:
  t: title (string, max 120 chars)
  s: summary (string, max 300 chars — include specific numbers/dates/names)
  url: source URL (string)
  cat: one of: Release | Breakthrough | Policy | Research | Funding | Security
  d: publication date in ISO format YYYY-MM-DD (never relative words like "2 days ago")

Return ONLY a valid JSON array."""
        arr = _ask_json(client, prompt, min_len=0)
        if arr:
            for sig in arr:
                if isinstance(sig, dict):
                    sig["query"] = domain_query
                    all_signals.append(sig)
            log(f"    ✓ {len(arr)} signals found")
        time.sleep(2)

    log(f"  Total new signals: {len(all_signals)}")
    update_dashboard(client, all_signals, ref, today)
    prune_old_signals(ref)

    # 2–3. MARKET INTEL (daily)
    update_inv_risks(client, today)
    update_inv_stocks(client, today, now_ksa)

    # 4–5. WEEKLY sections
    if weekly_due:
        update_inv_opps(client, today)
        update_inspect_cards(client, today, ref)
    else:
        log("  Weekly sections (opportunities, INSPECT cards) run on Sunday KSA — skipped today")

    # 6. Clear the seed flag once no generated block carries a SEED tag any more
    html = _read_html()
    if "const SEED_PENDING=true;" in html and "// SEED" not in html:
        html = html.replace("const SEED_PENDING=true;", "const SEED_PENDING=false;")
        _write_html(html)
        log("  ✓ SEED_PENDING cleared — dashboard is now fully generated")
    log("═══ RESCAN COMPLETE ═══\n")

# ─── SIGNALS: TRANSLATE + INJECT ─────────────────────────────────────────────
def translate_signals(client, signals):
    """Translate title+summary of each signal to Arabic. Returns dict index→{t_ar,s_ar}."""
    if not signals:
        return {}
    items = [{"i": i, "t": s.get("t",""), "s": s.get("s","")} for i, s in enumerate(signals)]
    prompt = f"""Translate the title (t) and summary (s) of each item below into professional Modern Standard Arabic.
Keep company names, product names, tickers and numbers in Latin script. Do not summarise or add anything.
Return a JSON array with the same length and order, objects with keys: i, t_ar, s_ar.

{json.dumps(items, ensure_ascii=False)}"""
    arr = _ask_json(client, prompt, min_len=1, use_search=False, max_tokens=MAX_TOKENS * 2)
    out = {}
    for r in arr or []:
        if isinstance(r, dict) and "i" in r:
            try: out[int(r["i"])] = {"t_ar": r.get("t_ar",""), "s_ar": r.get("s_ar","")}
            except (TypeError, ValueError): pass
    log(f"  ✓ Translated {len(out)}/{len(signals)} signals to Arabic")
    return out

CAT_AR = {"Release":"إطلاق","Breakthrough":"اختراق","Policy":"سياسة","Research":"بحث","Funding":"تمويل","Security":"أمن"}

def update_dashboard(client, signals, ref, today):
    log("  Updating AI Global Signals...")
    try:
        html = _read_html()
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

        fresh = [s for s in signals if not is_duplicate(s)]
        skipped = len(signals) - len(fresh)
        seen, uniq = set(), []                     # de-dupe within the batch too
        for s in fresh:
            k = (s.get("url","") or s.get("t","")).strip()
            if k and k not in seen:
                seen.add(k); uniq.append(s)
        fresh = uniq
        if skipped:
            log(f"  ↩ {skipped} duplicate(s) skipped")
        if not fresh:
            log("  All signals already exist — nothing new to inject")
            update_scan_timestamp(today)
            return
        log(f"  ✚ {len(fresh)} new signals to inject")

        ar = translate_signals(client, fresh)

        new_js = []
        for i, sig in enumerate(fresh):
            url   = _safe(sig.get("url", ""))
            cat   = sig.get("cat", "Research") if sig.get("cat") in CAT_AR else "Research"
            dt    = to_absolute_date(sig.get("d", ""), ref)
            if dt > ref: dt = ref
            t_en  = _safe(sig.get("t", "")); s_en = _safe(sig.get("s", ""))
            t_ar  = _safe(ar.get(i, {}).get("t_ar") or sig.get("t", ""))
            s_ar  = _safe(ar.get(i, {}).get("s_ar") or sig.get("s", ""))
            doms  = json.dumps(map_domains(sig.get("query", "")))
            new_js.append(
                f"  {{domains:{doms},url:'{url}',\n"
                f"   en:{{t:'{t_en}',cat:'{cat}',d:'{fmt_en(dt)}',s:'{s_en}'}},\n"
                f"   ar:{{t:'{t_ar}',cat:'{CAT_AR[cat]}',d:'{fmt_ar(dt)}',s:'{s_ar}'}}}},")

        block  = "\n  // ══ AUTO-RESCAN " + today.upper() + " ══\n" + "\n".join(new_js) + "\n"
        html   = html.replace("const AI_SIGNALS=[", "const AI_SIGNALS=[\n" + block, 1)
        html   = re.sub(r"// Last rescan: [^\n]+", f"// Last rescan: {today} ({len(fresh)} new signals)", html)
        _write_html(html)
        log(f"  ✓ {len(fresh)} added, {skipped} skipped")
    except Exception as e:
        log(f"  ✗ Dashboard update failed: {e}")

def prune_old_signals(ref):
    """Drop signal entries whose en date is older than RETENTION_DAYS so the file stops growing forever."""
    try:
        html = _read_html()
        start = html.find("const AI_SIGNALS=[")
        end   = html.find("\n];", start)
        if start < 0 or end < 0:
            return
        body   = html[start:end]
        cutoff = ref - timedelta(days=RETENTION_DAYS)
        entry_re = re.compile(r"\n  \{domains:.*?\n   ar:\{.*?\}\},", re.DOTALL)
        dropped = 0
        def keep(m):
            nonlocal dropped
            dm = re.search(r"en:\{t:'(?:[^'\\]|\\.)*',cat:'[^']*',d:'([^']*)'", m.group(0))
            dt = to_absolute_date(dm.group(1), ref) if dm else ref
            if dt < cutoff:
                dropped += 1
                return ""
            return m.group(0)
        body2 = entry_re.sub(keep, body)
        body2 = re.sub(r"\n  // ══ AUTO-RESCAN [^\n]+ ══\n(?=\s*(// ══|$))", "\n", body2)  # drop empty day headers
        if dropped:
            _write_html(html[:start] + body2 + html[end:])
            log(f"  🧹 Pruned {dropped} signals older than {RETENTION_DAYS} days")
    except Exception as e:
        log(f"  ✗ Prune failed: {e}")

def update_scan_timestamp(today):
    try:
        html = _read_html()
        marker = f"// Last rescan: {today} (0 new signals)"
        if re.search(r"// Last rescan: [^\n]+", html):
            html = re.sub(r"// Last rescan: [^\n]+", marker, html)
        else:
            html = html.replace("const AI_SIGNALS=[", f"{marker}\nconst AI_SIGNALS=[", 1)
        _write_html(html)
    except Exception as e:
        log(f"  ✗ Timestamp update failed: {e}")

# ─── MARKET INTEL 1: RISK SIGNALS (daily) ────────────────────────────────────
def update_inv_risks(client, today):
    log("  [Market Intel] Updating risk signals...")
    prompt = f"""Today is {today}. Search for the top 5 current investment risk signals for AI sector stocks THIS WEEK.
Focus on: regulatory deadlines, pricing/competition, capex/valuation concerns, geopolitical risks, legal proceedings.
Everything must be current as of {today} — do not describe events as upcoming if they have already happened.

Return a JSON array of exactly 5 objects:
  icon: one emoji
  title: short risk title in English (max 60 chars)
  title_ar: same title in Arabic (max 60 chars)
  body: 2-sentence explanation in English (max 200 chars, include specific numbers/dates)
  body_ar: Arabic translation of body (max 220 chars)

Return ONLY valid JSON."""
    risks = _ask_json(client, prompt, min_len=3)
    if not risks:
        log("  ✗ Keeping existing risk signals")
        return
    en, ar = [], []
    for r in risks[:5]:
        if not isinstance(r, dict): continue
        icon = _safe(r.get("icon", "⚠️"))
        en.append(f"  {{ icon:'{icon}', title:'{_safe(r.get('title',''))}', body:'{_safe(r.get('body',''))}' }}")
        ar.append(f"  {{ icon:'{icon}', title:'{_safe(r.get('title_ar') or r.get('title',''))}', body:'{_safe(r.get('body_ar') or r.get('body',''))}' }}")
    html = _read_html()
    html = _replace_marker(html, "INV-RISKS-EN", "let INV_RISKS_EN = [\n" + ",\n".join(en) + "\n];")
    html = _replace_marker(html, "INV-RISKS-AR", "let INV_RISKS_AR = [\n" + ",\n".join(ar) + "\n];")
    _write_html(html)
    log(f"  ✓ Risk signals updated ({len(en)} items)")

# ─── MARKET INTEL 2: STOCK RATING + WHY (daily) ──────────────────────────────
def _existing_stocks(html):
    """Read current ticker → {signal, why_en, why_ar} from the HTML so failures keep old text."""
    out = {}
    for lang in ("EN", "AR"):
        blk = re.search(rf"// ══ INV-STOCKS-{lang}-START ══(.*?)// ══ INV-STOCKS-{lang}-END ══", html, re.DOTALL)
        if not blk: continue
        for m in re.finditer(r"ticker:'([^']+)'.*?signal:'([^']+)'.*?why:'((?:[^'\\]|\\.)*)'", blk.group(1)):
            d = out.setdefault(m[1], {})
            d["signal"] = m[2]
            d["why_" + lang.lower()] = m[3].replace("\\'", "'")
    return out

def update_inv_stocks(client, today, now_ksa):
    log("  [Market Intel] Updating stock signals...")
    html = _read_html()
    existing = _existing_stocks(html)
    new = {}
    for bi in range(0, len(STOCK_WATCHLIST), 5):
        batch = STOCK_WATCHLIST[bi:bi+5]
        tickers_str = ", ".join(f"{s['ticker']} ({s['name']})" for s in batch)
        prompt = f"""Today is {today}. Search for this week's latest news on these AI-sector companies: {tickers_str}
(Private companies: treat as pre-IPO and report funding/IPO status.)

For each, return an object:
  ticker: exact ticker from the input
  signal: one of buy | watch | caution | ipo  (ipo only for private/pre-IPO companies; base the call on current news and valuation)
  why_en: 1-2 sentences in English, max 130 chars, specific to this week's news with a number or date
  why_ar: Arabic translation of why_en, max 150 chars

Return ONLY a JSON array with one object per company."""
        arr = _ask_json(client, prompt, min_len=1)
        for item in arr or []:
            if isinstance(item, dict) and item.get("ticker"):
                t = str(item["ticker"]).upper().strip()
                sig = str(item.get("signal", "")).lower().strip()
                new[t] = {"signal": sig if sig in VALID_SIGNALS else None,
                          "why_en": item.get("why_en", ""), "why_ar": item.get("why_ar", "")}
        time.sleep(2)

    if not new:
        log("  ✗ No stock data retrieved — keeping existing")
        return

    en, ar, kept = [], [], 0
    for s in STOCK_WATCHLIST:
        t = s["ticker"]; old = existing.get(t, {}); nw = new.get(t, {})
        signal = nw.get("signal") or old.get("signal") or ("ipo" if t in ("SPCX","OPENAI","ANTH") else "watch")
        why_en = (nw.get("why_en") or "").strip() or old.get("why_en", "")
        why_ar = (nw.get("why_ar") or "").strip() or old.get("why_ar", "") or why_en
        if not (nw.get("why_en") or "").strip(): kept += 1
        en.append(f"  {{ ticker:'{t}', name:'{_safe(s['name'])}', signal:'{signal}', why:'{_safe(why_en)}' }}")
        ar.append(f"  {{ ticker:'{t}', name:'{_safe(s['name_ar'])}', signal:'{signal}', why:'{_safe(why_ar)}' }}")

    html = _replace_marker(html, "INV-STOCKS-EN", "let INV_STOCKS_EN = [\n" + ",\n".join(en) + "\n];")
    html = _replace_marker(html, "INV-STOCKS-AR", "let INV_STOCKS_AR = [\n" + ",\n".join(ar) + "\n];")
    today_num = int(now_ksa.strftime("%Y%m%d"))
    html = re.sub(r"const invDataDate=\d+;", f"const invDataDate={today_num};", html)
    _write_html(html)
    log(f"  ✓ Stock signals updated ({len(new)} refreshed, {kept} kept from previous run, invDataDate → {today_num})")

# ─── MARKET INTEL 3: OPPORTUNITY VECTORS (weekly) ────────────────────────────
def update_inv_opps(client, today):
    log("  [Market Intel] Updating opportunity vectors (weekly)...")
    themes_str = "\n".join(f"{i+1}. {t['title_en']}" for i, t in enumerate(OPP_THEMES))
    prompt = f"""Today is {today}. Search for the latest developments relevant to these 6 AI investment opportunity themes:

{themes_str}

For each theme (in order) return an object:
  theme_num: 1-6
  horizon_en: investment horizon such as "6-12 months" or "Now-9 months"
  horizon_ar: Arabic version of horizon (e.g. "6-12 شهراً", "الآن-9 أشهر")
  tickers: array of 3-5 relevant public tickers or well-known pre-IPO names
  body_en: 2-3 sentences in English (max 250 chars) with specific recent data points, company names, numbers, dates
  body_ar: Arabic translation (max 280 chars)

Return ONLY a JSON array of exactly 6 objects."""
    results = _ask_json(client, prompt, min_len=4)
    if not results:
        log("  ✗ Keeping existing opportunity vectors")
        return
    rmap = {}
    for i, r in enumerate(results):
        if isinstance(r, dict):
            try: rmap[int(r.get("theme_num", i+1))] = r
            except (TypeError, ValueError): rmap[i+1] = r
    en, ar = [], []
    for i, th in enumerate(OPP_THEMES):
        r = rmap.get(i+1)
        if not r:
            continue
        tickers = json.dumps([str(x) for x in r.get("tickers", [])][:5])
        en.append(f"  {{ title:'{_safe(th['title_en'])}', horizon:'{_safe(r.get('horizon_en',''))}', tickers:{tickers}, body:'{_safe(r.get('body_en',''))}' }}")
        ar.append(f"  {{ title:'{_safe(th['title_ar'])}', horizon:'{_safe(r.get('horizon_ar') or r.get('horizon_en',''))}', tickers:{tickers}, body:'{_safe(r.get('body_ar') or r.get('body_en',''))}' }}")
    html = _read_html()
    html = _replace_marker(html, "INV-OPPS-EN", "let INV_OPPS_EN = [\n" + ",\n".join(en) + "\n];")
    html = _replace_marker(html, "INV-OPPS-AR", "let INV_OPPS_AR = [\n" + ",\n".join(ar) + "\n];")
    _write_html(html)
    log(f"  ✓ Opportunity vectors updated ({len(en)} themes)")

# ─── INSPECT CARDS (weekly) ───────────────────────────────────────────────────
def _js_str_array(items, n=4):
    return "[" + ",".join(f"'{_safe(t)}'" for t in items[:n]) + "]"

def update_inspect_cards(client, today, ref):
    log("  [INSPECT] Regenerating sector cards (weekly)...")
    all_cards = []
    for sec in INSPECT_SECTORS:
        log(f"    Sector: {sec['sec']}")
        prompt = f"""Today is {today}. Search the web for the {CARDS_PER_SECTOR} most significant developments from the last 60 days on:
{sec['query']}

Audience: a government inspection & monitoring authority evaluating AI for its own inspection operations.
For each development return an object with keys:
  title_en: headline (max 110 chars) stating what happened and why it matters for inspection
  title_ar: Arabic translation
  org_en: "Organisation · Country/Region" (max 60 chars)
  org_ar: Arabic version
  body_en: what happened, with dates, numbers, names (max 380 chars)
  body_ar: Arabic translation
  inno_en: what an inspection authority can do with this / why it matters (max 300 chars)
  inno_ar: Arabic translation
  tags_en: array of 3-4 short tags
  tags_ar: Arabic tags, same order
  date: publication date YYYY-MM-DD
  url: source URL
  domains: array of 1-2 from: smart-city, construction, food, housing, policy, security, ai-models, research, funding

Return ONLY a JSON array of {CARDS_PER_SECTOR} objects, newest first."""
        arr = _ask_json(client, prompt, min_len=2)
        if not arr:
            log(f"    ✗ Sector {sec['sec']} failed — keeping previous cards for the whole tab")
            return
        for k, c in enumerate(arr[:CARDS_PER_SECTOR]):
            if not isinstance(c, dict): continue
            dt = to_absolute_date(c.get("date", ""), ref)
            if dt > ref: dt = ref
            age = (ref - dt).days
            p = "pnew" if age <= 14 else ("p1" if k == 0 else "p2")
            doms = [d for d in c.get("domains", []) if isinstance(d, str)]
            for d in sec["domains"]:
                if d not in doms: doms.insert(0, d)
            b_en = ([["teal", "NEW"]] if age <= 14 else []) + [[sec["clr"], sec["label_en"]], ["teal", "Inspect"]]
            b_ar = ([["teal", "جديد"]] if age <= 14 else []) + [[sec["clr"], sec["label_ar"]], ["teal", "تفتيش"]]
            all_cards.append(
                f"  {{sec:'{sec['sec']}',p:'{p}',domains:{json.dumps(doms[:2])},\n"
                f"   url:'{_safe(c.get('url',''))}',\n"
                f"   en:{{badges:{json.dumps(b_en)},title:'{_safe(c.get('title_en',''))}',org:'{_safe(c.get('org_en',''))}',\n"
                f"    body:'{_safe(c.get('body_en',''))}',\n"
                f"    inno:'{_safe(c.get('inno_en',''))}',\n"
                f"    tags:{_js_str_array(c.get('tags_en', []))},date:'{fmt_en(dt)}'}},\n"
                f"   ar:{{badges:{json.dumps(b_ar, ensure_ascii=False)},title:'{_safe(c.get('title_ar') or c.get('title_en',''))}',org:'{_safe(c.get('org_ar') or c.get('org_en',''))}',\n"
                f"    body:'{_safe(c.get('body_ar') or c.get('body_en',''))}',\n"
                f"    inno:'{_safe(c.get('inno_ar') or c.get('inno_en',''))}',\n"
                f"    tags:{_js_str_array(c.get('tags_ar') or c.get('tags_en', []))},date:'{fmt_ar(dt)}'}}}},")
        time.sleep(2)
    if len(all_cards) < 6:
        log("  ✗ Too few cards generated — keeping previous")
        return
    html = _read_html()
    html = _replace_marker(html, "INSPECT",
        f"// Generated {today} — {len(all_cards)} cards\nconst INSPECT=[\n" + "\n".join(all_cards) + "\n];")
    _write_html(html)
    log(f"  ✓ INSPECT cards regenerated ({len(all_cards)} cards)")

# ─── DOMAIN MAPPER ───────────────────────────────────────────────────────────
def map_domains(query):
    q = query.lower(); domains = []
    if "smart city" in q or "continuous monitoring" in q: domains.append("smart-city")
    if "construction" in q or "excavation" in q or "drones" in q: domains.append("construction")
    if "food" in q or "restaurant" in q: domains.append("food")
    if "building" in q or "housing" in q: domains.append("housing")
    if "policy" in q or "regulation" in q or "government" in q: domains.append("policy")
    if "security" in q or "cyber" in q: domains.append("security")
    if "model" in q or "anthropic" in q or "openai" in q or "google" in q: domains.append("ai-models")
    if "investment" in q or "funding" in q or "ipo" in q: domains.append("funding")
    if "research" in q or "predictions" in q or "outlook" in q: domains.append("research")
    return domains if domains else ["ai-models"]

# ─── ONE-OFF: TRANSLATE BACKLOG ──────────────────────────────────────────────
def translate_backlog():
    """python radar_rescan.py --translate-backlog
    Translates the ar block of every existing signal whose Arabic text is still an English copy."""
    log("═══ TRANSLATE BACKLOG ═══")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    html = _read_html()
    entry_re = re.compile(r"   en:\{t:'((?:[^'\\]|\\.)*)',cat:'[^']*',d:'[^']*',s:'((?:[^'\\]|\\.)*)'\},\n   ar:\{t:'((?:[^'\\]|\\.)*)',(cat:'[^']*',d:'[^']*'),s:'((?:[^'\\]|\\.)*)'\}")
    todo = [m for m in entry_re.finditer(html) if m[1] == m[3]]
    log(f"  {len(todo)} signals still have English in the ar block")
    unesc = lambda x: x.replace("\\'", "'").replace("\\\\", "\\")
    for bi in range(0, len(todo), 25):
        batch = todo[bi:bi+25]
        fake = [{"t": unesc(m[1]), "s": unesc(m[2])} for m in batch]
        tr = translate_signals(client, fake)
        for k, m in enumerate(batch):
            if k not in tr or not tr[k].get("t_ar"):
                continue
            new = f"   ar:{{t:'{_safe(tr[k]['t_ar'])}',{m[4]},s:'{_safe(tr[k].get('s_ar') or unesc(m[2]))}'}}"
            old = m.group(0)[m.group(0).index("   ar:{"):]
            html = html.replace(old, new, 1)
        _write_html(html)
        log(f"  ✓ batch {bi//25+1} written")
        time.sleep(2)
    log("═══ BACKLOG DONE ═══")


# ─── SCHEDULER ────────────────────────────────────────────────────────────────
def scheduled_job():
    log(f"Scheduler triggered at {datetime.now(KSA_TZ).strftime('%H:%M KSA')}")
    run_rescan()

if __name__ == "__main__":
    if "--translate-backlog" in sys.argv:
        translate_backlog()
    elif "--now" in sys.argv:
        log("Manual run triggered (--now flag)")
        run_rescan()
    else:
        log(f"Scheduler started — will rescan daily at {SCAN_TIME_KSA} KSA")
        log(f"Dashboard: {DASHBOARD_PATH}")
        schedule.every().day.at("06:30").do(scheduled_job)
        last_run_file = ".last_rescan"
        today_str = datetime.now(KSA_TZ).strftime("%Y-%m-%d")
        if not os.path.exists(last_run_file) or open(last_run_file).read().strip() != today_str:
            log("No scan yet today — running initial scan...")
            run_rescan()
            with open(last_run_file, "w") as f:
                f.write(today_str)
        while True:
            schedule.run_pending()
            time.sleep(60)

