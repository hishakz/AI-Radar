#!/usr/bin/env python3
"""
AI Inspection Radar — Daily Auto-Rescan
Runs every morning at 09:00 KSA (UTC+3 = 06:00 UTC)
Calls the Anthropic API, scans for new signals, updates the dashboard HTML.

SETUP (one-time):
  pip install anthropic schedule pytz requests

RUN ONCE (manual):
  python radar_rescan.py --now

RUN ON A SCHEDULE (keeps running, fires at 09:00 KSA daily):
  python radar_rescan.py

DEPLOY AS CRON (Linux / Mac — add to crontab with: crontab -e):
  0 6 * * * /usr/bin/python3 /path/to/radar_rescan.py --now >> /var/log/radar.log 2>&1

DEPLOY ON WINDOWS TASK SCHEDULER:
  Action: python C:\\path\\to\\radar_rescan.py --now
  Trigger: Daily at 09:00 (set timezone to Arabian Standard Time)

DEPLOY ON GITHUB ACTIONS (see radar_rescan.yml companion file):
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
SCAN_TIME_KSA     = "09:00"
LOG_FILE          = "./radar_rescan.log"

# ─── DYNAMIC YEAR CONFIG ─────────────────────────────────────────────────────
_NOW        = datetime.now()
CURRENT_YEAR = _NOW.year
NEXT_YEAR    = _NOW.year + 1

# Domains to scan — uses current and next year automatically
# Includes a predictions/outlook domain so 2027 signals surface before Jan 1
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

# ─── LOGGING ─────────────────────────────────────────────────────────────────
def log(msg):
    ts = datetime.now(KSA_TZ).strftime("%Y-%m-%d %H:%M:%S KSA")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# ─── SCAN ─────────────────────────────────────────────────────────────────────
def run_rescan():
    log("═══ DAILY RESCAN STARTED ═══")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    today = datetime.now(KSA_TZ).strftime("%B %d, %Y")
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
  d: use exact date like "{today}" or "2 days ago" or real date like "June 3, {CURRENT_YEAR}" — never hardcode a year

Return ONLY a valid JSON array. No markdown, no preamble."""
                }]
            )

            # Extract text content from response
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            # Parse JSON from response
            json_match = re.search(r'\[[\s\S]*?\]', text)
            if json_match:
                signals = json.loads(json_match.group())
                for sig in signals:
                    sig["query"] = domain_query
                all_signals.extend(signals)
                log(f"    ✓ {len(signals)} signals found")
            else:
                log(f"    ✗ No JSON found in response")

        except Exception as e:
            log(f"    ✗ Error: {e}")
        
        time.sleep(2)  # Rate limit courtesy pause

    log(f"  Total new signals: {len(all_signals)}")

    if all_signals:
        update_dashboard(all_signals, today)
        send_summary(all_signals, today)
    else:
        log("  No new signals found — updating scan timestamp only")
        update_scan_timestamp(today)

    log("═══ RESCAN COMPLETE ═══\n")

# ─── TIMESTAMP-ONLY UPDATE (when 0 new signals) ───────────────────────────────
def update_scan_timestamp(today):
    """Update only the scan date comment in the HTML — no signal injection."""
    try:
        with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
            html = f.read()
        # Inject a comment marker so the file changes (triggers git commit)
        marker = f"// Last rescan: {today} (0 new signals)"
        old_marker_pat = r"// Last rescan: [^\n]+"
        import re
        if re.search(old_marker_pat, html):
            html = re.sub(old_marker_pat, marker, html)
        else:
            html = html.replace("// ════════════════════════════════════════════════════════════════\n// STATE",
                                f"{marker}\n// ════════════════════════════════════════════════════════════════\n// STATE")
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

# ─── DASHBOARD UPDATER ────────────────────────────────────────────────────────
def update_dashboard(signals, today):
    log("  Updating dashboard HTML...")
    try:
        with open(DASHBOARD_PATH, "r", encoding="utf-8") as f:
            html = f.read()

        # ── DEDUPLICATION: skip signals already in the file ────────────
        existing_urls   = set(re.findall(r"url:'([^']{10,})'", html))
        existing_titles = [t.lower() for t in re.findall(r"en:\{t:'([^']{10,80})'", html)]

        def is_duplicate(sig):
            url   = sig.get("url", "").strip()
            title = sig.get("t", "").strip().lower()
            if url and url in existing_urls:
                return True
            # Check 6-word phrase overlap with existing titles
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
            log(f"  ↩ {skipped} duplicate(s) skipped — already in dashboard")
        if not fresh:
            log("  All signals already exist — nothing new to inject")
            update_scan_timestamp(today)
            return
        log(f"  ✚ {len(fresh)} genuinely new signals to inject")

        # Build new signal JS objects
        new_js_signals = []
        for sig in fresh:
            url     = sig.get("url", "")
            cat     = sig.get("cat", "Research")
            d_str   = sig.get("d", "Today")
            title   = sig.get("t", "").replace("'", "\\'").replace("`", "'")
            summary = sig.get("s", "").replace("'", "\\'").replace("`", "'")
            doms    = json.dumps(map_domains(sig.get("query", "")))
            js = (f"  {{domains:{doms},url:\'{url}\',"
                  f"\n   en:{{t:\'{title}\',cat:\'{cat}\',d:\'{d_str} AUTO\',s:\'{summary}\'}},"
                  f"\n   ar:{{t:\'{title}\',cat:\'{cat}\',d:\'{d_str} تلقائي\',s:\'{summary}\'}}}},")
            new_js_signals.append(js)

        # Prepend to AI_SIGNALS — ALL previous signals preserved below
        block = "\n  // ══ AUTO-RESCAN " + today.upper() + " ══\n"
        block += "\n".join(new_js_signals) + "\n"
        html = html.replace("const AI_SIGNALS=[", "const AI_SIGNALS=[\n" + block)

        # Update scan date
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
        log(f"  ✓ Done — {len(fresh)} added, {skipped} duplicates skipped, {count} total signals")

    except Exception as e:
        log(f"  ✗ Dashboard update failed: {e}")

def get_ar_month(m):
    months = {1:'يناير',2:'فبراير',3:'مارس',4:'أبريل',5:'مايو',
              6:'يونيو',7:'يوليو',8:'أغسطس',9:'سبتمبر',10:'أكتوبر',
              11:'نوفمبر',12:'ديسمبر'}
    return months.get(m, '')

# ─── SUMMARY PRINTER ─────────────────────────────────────────────────────────
def send_summary(signals, today):
    log(f"\n  ┌─── SCAN SUMMARY — {today} ───")
    for i, sig in enumerate(signals, 1):
        log(f"  │ {i:02d}. [{sig.get('cat','?')}] {sig.get('t','')[:80]}")
    log(f"  └─── {len(signals)} total signals ───\n")

# ─── SCHEDULER ────────────────────────────────────────────────────────────────
def scheduled_job():
    """Wrapper that converts UTC schedule trigger to KSA check."""
    now_ksa = datetime.now(KSA_TZ)
    log(f"Scheduler triggered at {now_ksa.strftime('%H:%M KSA')}")
    run_rescan()

if __name__ == "__main__":
    if "--now" in sys.argv:
        # Run immediately (used by cron / GitHub Actions / manual test)
        log("Manual run triggered (--now flag)")
        run_rescan()
    else:
        # Keep-alive scheduler — fires at 09:00 KSA every day
        # Since schedule works in local time, we use UTC 06:00 equivalent
        log(f"Scheduler started — will rescan daily at {SCAN_TIME_KSA} KSA")
        log(f"Dashboard: {DASHBOARD_PATH}")
        log(f"Ctrl+C to stop\n")

        # Schedule at 06:00 UTC (= 09:00 KSA)
        schedule.every().day.at("06:00").do(scheduled_job)

        # Also run once on startup if not yet scanned today
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
