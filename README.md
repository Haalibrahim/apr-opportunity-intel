# APR Opportunity Intelligence Platform

> **Multi-organization, wave-driven opportunity scanner with prompt-cached AI matching.**

Built by the [Alliance for Policy Research](https://allianceforpolicyresearch.org) — a policy research firm specializing in health systems, emergency management, defense analytics, and computational modeling.

---

## What it does

This platform automatically discovers funding opportunities (grants, RFPs, contracts, calls for abstracts) across federal agencies, major foundations, and international organizations — then matches them against each client organization's strengths, expertise, and eligibility constraints.

**Key features:**
- **Wave-driven architecture** — modular search configurations with sources, ranking rules, and scope definitions
- **Multi-organization matching** — one opportunity pool, personalized reports per client
- **Prompt caching** — searches opportunities once, matches cheaply across many orgs (~90% cost savings)
- **Specific RFPs** — returns exact NOFO/BAA numbers with direct application URLs
- **Submission guidance** — flags LOI vs. full proposal, eligibility constraints, and what you need to compete
- **Professional outputs** — HTML reports (printable to PDF), Excel trackers, JSON data, ICS calendars

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Wave Configurations                       │
│  wave1_health.json  │  wave4_computational.json  │  ...     │
│  14 sources         │  20 sources                │          │
│  Ranking rules      │  Raff's 70/30 sim/policy   │          │
└─────────┬───────────┴──────────┬─────────────────┴──────────┘
          │                      │
          ▼                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Claude Sonnet + Web Search                      │
│         Specific RFPs with numbers and URLs                  │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│           Cached Prompt (all opportunities)                  │
│                  cache_control: ephemeral                     │
│           Pay once to load → match N orgs cheaply            │
└───────┬─────────────┬──────────────┬────────────────────────┘
        │             │              │
        ▼             ▼              ▼
   ┌─────────┐  ┌──────────┐  ┌──────────┐
   │  APR    │  │ Client 2 │  │ Client N │
   │ Report  │  │  Report  │  │  Report  │
   │HTML+XLSX│  │ HTML+XLSX│  │ HTML+XLSX│
   └─────────┘  └──────────┘  └──────────┘
```

## Quick start

### Prerequisites

- Python 3.10+
- [Anthropic API key](https://console.anthropic.com)

### Installation

```bash
git clone https://github.com/YOUR_ORG/apr-opportunity-intel.git
cd apr-opportunity-intel
pip install -r requirements.txt
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Run a scan

```bash
# Full scan — all waves, all orgs
python scanner.py

# Single wave
python scanner.py --wave wave4_computational

# Single org
python scanner.py --org apr
```

### Run the web dashboard

```bash
python app.py
# Open http://localhost:5000
```

### Deploy on Replit

1. Create a new Python Replit
2. Upload project files
3. Add `ANTHROPIC_API_KEY` to Replit Secrets
4. Run `pip install -r requirements.txt`
5. Run `python app.py`

## Project structure

```
apr-opportunity-intel/
├── scanner.py              # Core scanning engine + prompt caching
├── app.py                  # Flask web dashboard
├── requirements.txt
├── waves/                  # Wave configurations (modular search modules)
│   ├── wave1_health.json           # Health Systems & Policy
│   └── wave4_computational.json    # Computational & Systems Analysis
├── orgs/                   # Organization profiles (clients)
│   └── apr.json                    # Alliance for Policy Research
├── reports/                # Generated reports (gitignored)
│   └── .gitkeep
├── docs/                   # Documentation
│   └── WAVE_TEMPLATE.md
└── LICENSE
```

## Adding a new wave

Waves are JSON config files in `waves/`. Use `wave4_computational.json` as the gold-standard template — it was designed by Raff and includes scope definitions, ranking rules, and source lists.

See [`docs/WAVE_TEMPLATE.md`](docs/WAVE_TEMPLATE.md) for the specification.

## Adding a new organization

Drop a JSON file in `orgs/`. The next scan will automatically generate a personalized report for the new org.

```json
{
  "id": "new_client",
  "name": "New Research Org",
  "short": "NRO",
  "type": "501(c)(3) nonprofit",
  "strengths": ["education policy", "program evaluation"],
  "eligibility_constraints": {
    "nih_eligible": "Yes — as lead PI"
  }
}
```

## Weekly automation

```bash
# crontab -e
0 8 * * 1 cd /path/to/project && ANTHROPIC_API_KEY=sk-ant-... python scanner.py
```

## Cost model

| Component | Cost per scan |
|-----------|--------------|
| Wave search (per wave) | ~$0.50–$2.00 |
| Full scan (2 waves) | ~$2–4 |
| Org matching (cached, per org) | ~$0.10–$0.50 |
| Full scan + 10 orgs | ~$5–9 |

Prompt caching reduces per-org matching costs by ~90% compared to independent calls.

## Roadmap

- [x] Core scanner engine with web search
- [x] Wave 1: Health Systems & Policy
- [x] Wave 4: Computational & Systems Analysis (Raff)
- [x] APR organization profile
- [x] Prompt-cached multi-org matching
- [x] HTML report generation
- [x] Excel tracker generation
- [x] Flask web dashboard
- [ ] Wave editor UI
- [ ] Multi-org dashboard
- [ ] Stripe billing (SaaS)
- [ ] Slack/Teams integration
- [ ] Google Calendar API push
- [ ] Competitor tracking (USASpending.gov)
- [ ] AI-generated proposal outlines

## Team

- **Hamad Al-Ibrahim** — Strategy, health wave, org profiles
- **Raff (Seebs)** — Architecture, prompt caching, Wave 4 specification
- **APR** — [allianceforpolicyresearch.org](https://allianceforpolicyresearch.org)

## License

Proprietary — Alliance for Policy Research LLC. All rights reserved.
