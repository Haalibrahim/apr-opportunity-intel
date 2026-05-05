"""
APR Opportunity Intelligence Platform — Core Scanner Engine
============================================================
Loads wave configurations, searches via Anthropic API + web search,
uses prompt caching for multi-org matching, generates reports.

Usage:
    python scanner.py                    # Full scan, all waves, all orgs
    python scanner.py --wave wave4       # Single wave
    python scanner.py --org apr          # Single org report
"""

import os
import json
import re
import sys
import glob
import time
from datetime import datetime, date
from pathlib import Path

import anthropic

# ─── Configuration ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
WAVES_DIR = BASE_DIR / "waves"
ORGS_DIR = BASE_DIR / "orgs"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

TODAY = date.today().isoformat()
TODAY_PRETTY = datetime.now().strftime("%B %d, %Y")
MODEL = "claude-sonnet-4-6"
DEBUG = True  # Print raw model output for troubleshooting


# ─── Data Loading ─────────────────────────────────────────────────────────────

def load_waves(wave_filter=None):
    """Load wave configs from JSON files in waves/ directory."""
    waves = []
    for f in sorted(WAVES_DIR.glob("*.json")):
        with open(f) as fh:
            w = json.load(fh)
            if wave_filter and w["id"] != wave_filter:
                continue
            waves.append(w)
    return waves


def load_orgs(org_filter=None):
    """Load organization profiles from JSON files in orgs/ directory."""
    orgs = []
    for f in sorted(ORGS_DIR.glob("*.json")):
        with open(f) as fh:
            o = json.load(fh)
            if org_filter and o["id"] != org_filter:
                continue
            orgs.append(o)
    return orgs


# ─── Wave Scanner ─────────────────────────────────────────────────────────────

def build_wave_prompt(wave):
    """Build a SHORT, focused search prompt from a wave config."""

    # Only include top 6 sources to keep prompt short (rate limit friendly)
    top_sources = wave["sources"][:6]
    sources_text = ", ".join(s["name"] for s in top_sources)

    return f"""Search for SPECIFIC open grants, RFPs, and calls related to: {wave['name']}.

TODAY: {TODAY}. Only deadlines AFTER today. Include Rolling/Upcoming.

Focus: {wave['description'][:200]}

Key sources: {sources_text}

For each, provide JSON with: rfp_number, title, category (Grant/RFP/Contract/Abstract), requester, funding, deadline (YYYY-MM-DD or Rolling), submission_type (Full proposal/LOI then full/Two-stage/White paper then full), summary (2 sentences), source (direct URL), eligibility.

JSON ARRAY ONLY. No markdown. No backticks. []  if nothing."""


def scan_wave(client, wave):
    """Run a single wave scan using Anthropic API with web search."""
    print(f"  Scanning: {wave['name']} ({len(wave['sources'])} sources)...")

    prompt = build_wave_prompt(wave)

    # Retry up to 3 times with increasing delay for rate limits
    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2500,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{"role": "user", "content": prompt}],
            )
            break  # Success — exit retry loop
        except Exception as e:
            if "rate_limit" in str(e) or "429" in str(e):
                wait = 120 * (attempt + 1)
                print(f"    Rate limited — waiting {wait}s before retry ({attempt+1}/3)...")
                time.sleep(wait)
                if attempt == 2:
                    print(f"    Failed after 3 retries")
                    return []
            else:
                print(f"    Error: {e}")
                return []

    try:

        # Extract text from response
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)

        full_text = "\n".join(text_parts)

        # Debug: show what the model returned
        if DEBUG:
            print(f"    [DEBUG] Response length: {len(full_text)} chars")
            print(f"    [DEBUG] First 300 chars: {full_text[:300]}")

        # Parse JSON
        match = re.search(r"\[[\s\S]*\]", full_text)
        if not match:
            print(f"    No structured results found")
            if DEBUG:
                print(f"    [DEBUG] Full response: {full_text[:500]}")
            return []

        items = json.loads(match.group(0))
        if DEBUG:
            print(f"    [DEBUG] Parsed {len(items)} items from JSON")

        # Filter past deadlines
        valid = []
        for item in items:
            dl = item.get("deadline", "")
            if dl in ("Rolling", "Upcoming", "Upcoming — TBA", "Not specified", "Continuous", ""):
                valid.append(item)
                continue
            if "Upcoming" in dl:
                valid.append(item)
                continue
            try:
                d = datetime.strptime(dl, "%Y-%m-%d").date()
                if d >= date.today():
                    valid.append(item)
            except ValueError:
                valid.append(item)  # Keep if we can't parse

        # Tag with wave info
        for item in valid:
            item["wave_id"] = wave["id"]
            item["wave_name"] = wave["name"]
            item["wave_color"] = wave["color"]

        print(f"    Found {len(valid)} valid opportunities")
        return valid

    except Exception as e:
        print(f"    Error: {e}")
        return []


# ─── Prompt-Cached Org Matching ───────────────────────────────────────────────

def match_opportunities_to_org(client, opportunities, org):
    """
    Use prompt caching to efficiently match opportunities against an org profile.

    Key insight from Seebs: load all opportunities into a cached prompt once,
    then append each org's profile cheaply.
    """
    if not opportunities:
        return []

    print(f"  Matching {len(opportunities)} opportunities to {org['short']}...")

    # Compact the opportunities JSON to save tokens
    opps_compact = json.dumps([{
        "rfp_number": o.get("rfp_number",""), "title": o.get("title",""),
        "category": o.get("category",""), "requester": o.get("requester",""),
        "funding": o.get("funding",""), "deadline": o.get("deadline",""),
        "eligibility": o.get("eligibility",""), "summary": o.get("summary","")[:100]
    } for o in opportunities])

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=2500,
                system=[
                    {
                        "type": "text",
                        "text": f"""Match these {len(opportunities)} opportunities to an org. For each, score fit.
Opportunities: {opps_compact}""",
                        "cache_control": {"type": "ephemeral"}
                    }
                ],
                messages=[{
                    "role": "user",
                    "content": f"""Org: {org['name']} ({org.get('type','')})
Strengths: {', '.join(org.get('strengths',[])[:8])}
Eligibility: {json.dumps(org.get('eligibility_constraints',{}))[:200]}

For EACH opportunity return JSON: rfp_number, title, priority (HIGH/MEDIUM/LOW/NOT ELIGIBLE), fit_score (1-10), eligibility_ok (true/false), eligibility_note, what_you_need, recommended_action (Apply as lead/Apply as partner/Find fiscal sponsor/Skip/Monitor).

JSON ARRAY ONLY. No markdown."""
                }],
            )
            break
        except Exception as e:
            if "rate_limit" in str(e) or "429" in str(e):
                wait = 120 * (attempt + 1)
                print(f"    Rate limited — waiting {wait}s ({attempt+1}/3)...")
                time.sleep(wait)
                if attempt == 2:
                    print(f"    Matching failed after retries")
                    return opportunities
            else:
                print(f"    Error: {e}")
                return opportunities

    try:
        text_parts = [b.text for b in response.content if hasattr(b, "text")]
        full_text = "\n".join(text_parts)

        match = re.search(r"\[[\s\S]*\]", full_text)
        if not match:
            print(f"    Matching failed — no structured output")
            return opportunities  # Return unmatched

        matches = json.loads(match.group(0))

        # Merge match data back into opportunities
        match_map = {m["rfp_number"]: m for m in matches}
        for opp in opportunities:
            rfp = opp.get("rfp_number", "")
            if rfp in match_map:
                m = match_map[rfp]
                opp["priority"] = m.get("priority", "MEDIUM")
                opp["fit_score"] = m.get("fit_score", 5)
                opp["eligibility_ok"] = m.get("eligibility_ok", True)
                opp["eligibility_note"] = m.get("eligibility_note", "")
                opp["what_you_need"] = m.get("what_you_need", "")
                opp["recommended_action"] = m.get("recommended_action", "")
            else:
                opp["priority"] = "MEDIUM"
                opp["fit_score"] = 5

        # Sort by priority then fit_score
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NOT ELIGIBLE": 3}
        opportunities.sort(key=lambda x: (
            priority_order.get(x.get("priority", "MEDIUM"), 1),
            -x.get("fit_score", 5)
        ))

        print(f"    Matched: {sum(1 for o in opportunities if o.get('priority') == 'HIGH')} HIGH, "
              f"{sum(1 for o in opportunities if o.get('priority') == 'MEDIUM')} MEDIUM, "
              f"{sum(1 for o in opportunities if o.get('priority') == 'LOW')} LOW")

        # Log cache performance
        if hasattr(response, 'usage'):
            u = response.usage
            cached = getattr(u, 'cache_read_input_tokens', 0)
            total_in = getattr(u, 'input_tokens', 0)
            if cached and total_in:
                pct = (cached / total_in) * 100
                print(f"    Cache hit: {pct:.0f}% ({cached:,} of {total_in:,} input tokens cached)")

        return opportunities

    except Exception as e:
        print(f"    Matching error: {e}")
        return opportunities


# ─── Report Generation ────────────────────────────────────────────────────────

def generate_html_report(opportunities, org, waves_used):
    """Generate a professional HTML report."""

    # Group by wave
    by_wave = {}
    for opp in opportunities:
        wn = opp.get("wave_name", "Uncategorized")
        by_wave.setdefault(wn, []).append(opp)

    total = len(opportunities)
    high = sum(1 for o in opportunities if o.get("priority") == "HIGH")
    medium = sum(1 for o in opportunities if o.get("priority") == "MEDIUM")

    priority_colors = {"HIGH": "#1D9E75", "MEDIUM": "#BA7517", "LOW": "#999", "NOT ELIGIBLE": "#D85A30"}

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{org['short']} Opportunity Report — {TODAY_PRETTY}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600;700&family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
@media print{{@page{{margin:.5in .65in}}.no-print{{display:none!important}}.card{{page-break-inside:avoid}}}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'DM Sans',system-ui,sans-serif;color:#1a1a1a;background:#fff;line-height:1.5}}
.hdr{{background:linear-gradient(135deg,#0a1628,#1d3f66);color:#fff;padding:2.5rem 3rem}}
.hdr h1{{font-family:'Source Serif 4',serif;font-size:26px;font-weight:700}}
.hdr .sub{{font-size:13px;opacity:.6;margin-top:2px}}
.sts{{display:flex;gap:10px;margin-top:1.2rem;flex-wrap:wrap}}
.st{{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:8px;padding:10px 16px}}
.st b{{font-size:26px;font-weight:600;color:#68b5ff;display:block}}
.st span{{font-size:9px;text-transform:uppercase;letter-spacing:.8px;opacity:.5}}
.body{{padding:1.5rem 3rem 2rem;max-width:1040px}}
.sec-h{{font-family:'Source Serif 4',serif;font-size:19px;font-weight:600;color:#162a4a;border-bottom:3px solid;padding-bottom:6px;margin:24px 0 14px;display:flex;align-items:center;gap:10px}}
.badge{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.7px;padding:3px 10px;border-radius:4px;color:#fff}}
.card{{border:1px solid #e2e2e2;border-radius:8px;padding:14px 18px;margin-bottom:10px}}
.card.high{{border-left:4px solid #1D9E75}}
.card.medium{{border-left:4px solid #BA7517}}
.card.low{{border-left:4px solid #ddd}}
.rfp{{font-family:'JetBrains Mono';font-size:10px;color:#666;font-weight:500;background:#f0f0f0;padding:2px 8px;border-radius:3px}}
.card-t{{font-weight:600;font-size:14px;margin:4px 0}}
.card-m{{display:flex;flex-wrap:wrap;gap:12px;font-size:11.5px;color:#666;margin:5px 0}}
.card-m b{{color:#1a1a1a}}
.card-m .amt{{color:#1D9E75}}.card-m .dl{{color:#D85A30}}
.priority{{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;padding:2px 8px;border-radius:3px;color:#fff}}
.sub-type{{background:#e8f0fe;color:#185FA5;padding:2px 8px;border-radius:3px;font-size:10px;font-weight:600}}
.card-s{{font-size:12.5px;color:#444;line-height:1.55;margin-top:5px}}
.card-need{{font-size:11.5px;color:#162a4a;background:#f0f4f8;border:1px solid #dde4ed;border-radius:6px;padding:8px 12px;margin-top:8px;line-height:1.5}}
.card-need em{{color:#185FA5;font-style:normal;font-weight:700;font-size:10px;text-transform:uppercase;letter-spacing:.4px}}
.card-action{{font-size:11px;margin-top:6px;padding:6px 10px;background:#fffbe8;border:1px solid #f0e2a1;border-radius:5px;color:#5a4a00}}
.card-action b{{color:#85700e}}
.src{{font-size:11px;margin-top:6px}}.src a{{color:#378ADD;text-decoration:none}}
.ft{{text-align:center;font-size:10px;color:#999;border-top:1px solid #eee;padding:14px;margin-top:2rem}}
.pbtn{{position:fixed;bottom:20px;right:20px;background:#162a4a;color:#fff;border:none;padding:12px 24px;border-radius:8px;font-size:14px;cursor:pointer;box-shadow:0 2px 12px rgba(0,0,0,.25)}}
</style></head><body>
<button class="pbtn no-print" onclick="window.print()">Print / Save as PDF</button>
<div class="hdr">
<h1>{org['short']} — Opportunity Intelligence Report</h1>
<p class="sub">{org['name']} | Waves: {', '.join(w['name'] for w in waves_used)} | {TODAY_PRETTY}</p>
<div class="sts">
<div class="st"><b>{total}</b><span>Total RFPs</span></div>
<div class="st"><b>{high}</b><span>High priority</span></div>
<div class="st"><b>{medium}</b><span>Medium</span></div>
<div class="st"><b>{len(waves_used)}</b><span>Waves scanned</span></div>
</div></div>
<div class="body">"""

    for wave_name, items in by_wave.items():
        wave_color = items[0].get("wave_color", "#666") if items else "#666"
        html += f'<div class="sec-h" style="border-color:{wave_color}"><span class="badge" style="background:{wave_color}">{len(items)}</span>{wave_name}</div>'

        for opp in items:
            priority = opp.get("priority", "MEDIUM")
            pc = priority_colors.get(priority, "#999")
            card_class = priority.lower().replace(" ", "")
            if card_class == "noteligible":
                card_class = "low"

            html += f'<div class="card {card_class}">'
            html += f'<div style="display:flex;flex-wrap:wrap;gap:5px;align-items:center;margin-bottom:4px">'
            html += f'<span class="rfp">{opp.get("rfp_number", "N/A")}</span>'
            html += f'<span class="priority" style="background:{pc}">{priority}</span>'
            if opp.get("fit_score"):
                html += f'<span style="font-size:10px;color:#666">Fit: {opp["fit_score"]}/10</span>'
            html += f'<span class="badge" style="background:{wave_color};font-size:9px">{opp.get("category", "Grant")}</span>'
            if opp.get("submission_type"):
                html += f'<span class="sub-type">{opp["submission_type"]}</span>'
            html += '</div>'

            html += f'<div class="card-t">{opp.get("title", "Untitled")}</div>'
            html += '<div class="card-m">'
            if opp.get("requester"): html += f'<span>Funder: <b>{opp["requester"]}</b></span>'
            if opp.get("funding"): html += f'<span>Amount: <b class="amt">{opp["funding"]}</b></span>'
            if opp.get("deadline"): html += f'<span>Deadline: <b class="dl">{opp["deadline"]}</b></span>'
            if opp.get("eligibility"): html += f'<span>Eligibility: {opp["eligibility"]}</span>'
            html += '</div>'

            if opp.get("summary"):
                html += f'<div class="card-s">{opp["summary"]}</div>'
            if opp.get("what_you_need"):
                html += f'<div class="card-need"><em>What {org["short"]} needs: </em>{opp["what_you_need"]}</div>'
            if opp.get("recommended_action"):
                html += f'<div class="card-action"><b>Recommended action:</b> {opp["recommended_action"]}</div>'
            if opp.get("source"):
                html += f'<div class="src"><a href="{opp["source"]}" target="_blank">{opp["source"]}</a></div>'
            html += '</div>'

    html += f'<div class="ft">{org["name"]} | Generated by APR Opportunity Intelligence Platform | {TODAY_PRETTY}</div>'
    html += '</div></body></html>'
    return html


def generate_excel_report(opportunities, org, waves_used):
    """Generate Excel tracker with per-org matching data."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("  openpyxl not installed — skipping Excel. Run: pip install openpyxl")
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = f"{org['short']} Opportunities"

    navy = PatternFill(start_color="162A4A", end_color="162A4A", fill_type="solid")
    hfont = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    bfont = Font(name="Arial", size=10)
    mono = Font(name="Consolas", size=9, bold=True)
    wrap = Alignment(wrap_text=True, vertical="top")
    thin = Border(
        left=Side(style='thin', color='D0D4DC'), right=Side(style='thin', color='D0D4DC'),
        top=Side(style='thin', color='D0D4DC'), bottom=Side(style='thin', color='D0D4DC')
    )

    high_fill = PatternFill(start_color="E8F5E9", end_color="E8F5E9", fill_type="solid")
    med_fill = PatternFill(start_color="FFF8E1", end_color="FFF8E1", fill_type="solid")

    headers = ["Priority", "Fit", "RFP #", "Title", "Category", "Wave", "Funder",
               "Funding", "Deadline", "Submission Type", "Eligibility OK",
               "What You Need", "Recommended Action", "Direct Link"]
    widths = [12, 6, 22, 48, 10, 22, 28, 22, 18, 28, 12, 48, 24, 45]

    for i, h in enumerate(headers, 1):
        c = ws.cell(row=1, column=i, value=h)
        c.font = hfont; c.fill = navy; c.alignment = wrap; c.border = thin
        ws.column_dimensions[get_column_letter(i)].width = widths[i-1]

    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}1"
    ws.freeze_panes = "D2"

    for idx, opp in enumerate(opportunities, 2):
        priority = opp.get("priority", "MEDIUM")
        row = [
            priority,
            opp.get("fit_score", ""),
            opp.get("rfp_number", ""),
            opp.get("title", ""),
            opp.get("category", ""),
            opp.get("wave_name", ""),
            opp.get("requester", ""),
            opp.get("funding", ""),
            opp.get("deadline", ""),
            opp.get("submission_type", ""),
            "Yes" if opp.get("eligibility_ok", True) else "No",
            opp.get("what_you_need", ""),
            opp.get("recommended_action", ""),
            opp.get("source", ""),
        ]
        fill = high_fill if priority == "HIGH" else (med_fill if priority == "MEDIUM" else None)
        for i, val in enumerate(row, 1):
            c = ws.cell(row=idx, column=i, value=val)
            c.font = mono if i == 3 else bfont
            c.alignment = wrap; c.border = thin
            if fill: c.fill = fill
            if i == 14 and val:
                c.font = Font(name="Arial", size=10, color="378ADD", underline="single")
                c.hyperlink = val

    return wb


# ─── Main Pipeline ────────────────────────────────────────────────────────────

def run_scan(wave_filter=None, org_filter=None):
    """Run the full scan pipeline."""
    print("=" * 60)
    print(f"  APR Opportunity Intelligence Platform")
    print(f"  Scan date: {TODAY}")
    print("=" * 60)

    # Load configs
    waves = load_waves(wave_filter)
    orgs = load_orgs(org_filter)

    if not waves:
        print(f"\nNo waves found in {WAVES_DIR}. Check your wave config files.")
        return
    if not orgs:
        print(f"\nNo orgs found in {ORGS_DIR}. Check your org profile files.")
        return

    print(f"\n  Waves: {', '.join(w['name'] for w in waves)}")
    print(f"  Orgs:  {', '.join(o['short'] for o in orgs)}")

    # Initialize client
    client = anthropic.Anthropic()

    # Phase 1: Scan all waves
    print(f"\n[Phase 1] Scanning {len(waves)} waves...")
    all_opportunities = []
    for i, wave in enumerate(waves):
        results = scan_wave(client, wave)
        all_opportunities.extend(results)
        # Wait between waves to respect rate limits (30K tokens/min)
        if i < len(waves) - 1:
            print(f"    Waiting 180s before next wave (rate limit cooldown)...")
            time.sleep(180)

    # Deduplicate by RFP number
    seen = set()
    deduped = []
    for opp in all_opportunities:
        key = opp.get("rfp_number", opp.get("title", "")).lower().strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append(opp)
    all_opportunities = deduped

    print(f"\n  Total unique opportunities: {len(all_opportunities)}")

    if not all_opportunities:
        print("\nNo opportunities found. Check API key and network connectivity.")
        return

    # Phase 2: Match to each org (with prompt caching)
    print(f"\n  Waiting 180s before org matching (rate limit cooldown)...")
    time.sleep(180)
    print(f"\n[Phase 2] Matching to {len(orgs)} organization(s)...")
    for org in orgs:
        matched = match_opportunities_to_org(client, all_opportunities.copy(), org)

        # Phase 3: Generate reports
        print(f"\n[Phase 3] Generating reports for {org['short']}...")

        # HTML
        html = generate_html_report(matched, org, waves)
        html_path = REPORTS_DIR / f"{org['id']}_report_{TODAY}.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  HTML: {html_path}")

        # Excel
        wb = generate_excel_report(matched, org, waves)
        if wb:
            xlsx_path = REPORTS_DIR / f"{org['id']}_tracker_{TODAY}.xlsx"
            wb.save(str(xlsx_path))
            print(f"  Excel: {xlsx_path}")

        # JSON (raw data for downstream use)
        json_path = REPORTS_DIR / f"{org['id']}_data_{TODAY}.json"
        with open(json_path, "w") as f:
            json.dump(matched, f, indent=2)
        print(f"  JSON: {json_path}")

    print(f"\n{'=' * 60}")
    print(f"  Scan complete!")
    print(f"  Reports saved to: {REPORTS_DIR}")
    print(f"{'=' * 60}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="APR Opportunity Intelligence Scanner")
    parser.add_argument("--wave", help="Scan single wave by ID (e.g. wave4_computational)")
    parser.add_argument("--org", help="Generate report for single org by ID (e.g. apr)")
    args = parser.parse_args()

    run_scan(wave_filter=args.wave, org_filter=args.org)
