Inspection Intelligence — AI Radar Dashboard
A purpose-built intelligence platform for innovation directors and decision-makers in regulatory inspection authorities. Tracks 130+ AI and emerging technology signals across 10 domains and translates them into inspection-domain strategy — not just news.
What it does

Daily rescan of global AI signals relevant to smart city inspection, construction, food safety, housing, infrastructure, and regulatory policy
Bilingual — full English and Arabic RTL versions with instant toggle; all content, UI labels, and feasibility matrices translated
Domain filters — 10 filter categories (Smart City, Construction, Food Safety, Housing, Policy, Security, AI Models, Research, Funding) across all tabs
Date sort — newest-first or editorial priority, across all cards
Innovation Applications tab — 5 strategic vectors with visual feasibility matrices (Technical Complexity, Investment, HR, Time to Value, Change Management), Go/No-Go verdicts, Key Risk and Key Enabler for each, and a decision summary table
Investment Intelligence panel — hidden, revealed on demand; maps current scan signals to stock impact ratings, investment opportunity vectors with time horizons, and risk signals to watch
Auto-rescan engine — standalone HTML artifact that calls the Claude API with live web search and renders results in real-time, with domain selection and JSON export

Domains covered
Smart City Continuous Inspection · Construction & Excavation · Restaurant & Food Safety · Group Housing & Buildings · Policy & Governance · Cybersecurity · AI Models & Releases · Research · Funding & IPO
Automation
Scheduled daily at 09:00 KSA via GitHub Actions (06:00 UTC), Google Calendar .ics reminder, or local Python cron using the Anthropic API with web search.
Stack
Vanilla HTML/CSS/JS · No framework · No build step · RTL-native · Dark mode · Claude API (web search) · 185KB single file
