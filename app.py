"""
APR Opportunity Intelligence Platform — Web Interface
=====================================================
Simple Flask app for Replit. Serves dashboard and triggers scans.

Run: python app.py
Or on Replit: just click Run
"""

import os
import json
import glob
from pathlib import Path
from flask import Flask, render_template_string, jsonify, send_from_directory, request
from datetime import datetime

app = Flask(__name__)
BASE_DIR = Path(__file__).parent
WAVES_DIR = BASE_DIR / "waves"
ORGS_DIR = BASE_DIR / "orgs"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

DASHBOARD_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>APR Opportunity Intelligence Platform</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',system-ui,sans-serif;background:#f5f6f8;color:#1a1a1a;min-height:100vh}
.sidebar{position:fixed;left:0;top:0;width:240px;height:100vh;background:#0a1628;color:#fff;padding:24px 20px;overflow-y:auto}
.sidebar h1{font-size:15px;font-weight:700;margin-bottom:4px;letter-spacing:-.3px}
.sidebar .sub{font-size:11px;opacity:.5;margin-bottom:24px}
.sidebar .nav-item{display:block;padding:8px 12px;border-radius:6px;color:rgba(255,255,255,.7);text-decoration:none;font-size:13px;margin-bottom:2px;cursor:pointer;border:none;background:none;width:100%;text-align:left}
.sidebar .nav-item:hover,.sidebar .nav-item.active{background:rgba(255,255,255,.08);color:#fff}
.sidebar .section-title{font-size:10px;text-transform:uppercase;letter-spacing:1px;opacity:.35;margin:16px 0 6px 4px}
.main{margin-left:240px;padding:24px 32px}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}
.topbar h2{font-size:22px;font-weight:700;letter-spacing:-.5px}
.btn{padding:8px 18px;border-radius:8px;border:none;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit}
.btn-primary{background:#162a4a;color:#fff}.btn-primary:hover{background:#1d3f66}
.btn-outline{background:transparent;border:1px solid #d0d4dc;color:#333}.btn-outline:hover{background:#f0f0f0}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:24px}
.stat-card{background:#fff;border-radius:10px;padding:16px 20px;border:1px solid #e8eaef}
.stat-card .value{font-size:28px;font-weight:700;color:#162a4a}
.stat-card .label{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:.8px;margin-top:2px}
.card{background:#fff;border-radius:10px;border:1px solid #e8eaef;padding:20px 24px;margin-bottom:16px}
.card h3{font-size:15px;font-weight:600;margin-bottom:12px}
.wave-row{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid #f0f0f0}
.wave-row:last-child{border-bottom:none}
.wave-dot{width:10px;height:10px;border-radius:3px;flex-shrink:0}
.wave-name{flex:1;font-size:13px;font-weight:500}
.wave-sources{font-size:11px;color:#888}
.report-row{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid #f0f0f0}
.report-row:last-child{border-bottom:none}
.report-row a{color:#378ADD;text-decoration:none;font-size:13px;font-weight:500}
.report-row .date{font-size:11px;color:#888;margin-left:auto}
.empty{text-align:center;padding:40px;color:#888;font-size:14px}
#scan-status{display:none;background:#fffbe8;border:1px solid #f0e2a1;border-radius:8px;padding:12px 16px;margin-bottom:16px;font-size:13px;color:#5a4a00}
</style></head><body>
<div class="sidebar">
  <h1>APR Platform</h1>
  <p class="sub">Opportunity Intelligence</p>
  <button class="nav-item active" onclick="showSection('dashboard')">Dashboard</button>
  <button class="nav-item" onclick="showSection('waves')">Wave Configuration</button>
  <button class="nav-item" onclick="showSection('orgs')">Organizations</button>
  <button class="nav-item" onclick="showSection('reports')">Reports</button>
  <div class="section-title">System</div>
  <button class="nav-item" onclick="showSection('settings')">Settings</button>
</div>
<div class="main" id="content">
  <div class="topbar">
    <h2>Dashboard</h2>
    <div style="display:flex;gap:8px">
      <button class="btn btn-primary" onclick="runScan()">Run scan now</button>
      <button class="btn btn-outline" onclick="loadReports()">Refresh reports</button>
    </div>
  </div>
  <div id="scan-status"></div>
  <div class="stats" id="stats-row">
    <div class="stat-card"><div class="value" id="stat-waves">-</div><div class="label">Waves configured</div></div>
    <div class="stat-card"><div class="value" id="stat-sources">-</div><div class="label">Total sources</div></div>
    <div class="stat-card"><div class="value" id="stat-orgs">-</div><div class="label">Organizations</div></div>
    <div class="stat-card"><div class="value" id="stat-reports">-</div><div class="label">Reports generated</div></div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div class="card">
      <h3>Active waves</h3>
      <div id="waves-list"><div class="empty">Loading...</div></div>
    </div>
    <div class="card">
      <h3>Recent reports</h3>
      <div id="reports-list"><div class="empty">Loading...</div></div>
    </div>
  </div>
</div>
<script>
async function loadDashboard() {
  const [waves, orgs, reports] = await Promise.all([
    fetch('/api/waves').then(r => r.json()),
    fetch('/api/orgs').then(r => r.json()),
    fetch('/api/reports').then(r => r.json())
  ]);
  document.getElementById('stat-waves').textContent = waves.length;
  document.getElementById('stat-sources').textContent = waves.reduce((a, w) => a + (w.sources || []).length, 0);
  document.getElementById('stat-orgs').textContent = orgs.length;
  document.getElementById('stat-reports').textContent = reports.length;

  let wavesHtml = '';
  waves.forEach(w => {
    wavesHtml += `<div class="wave-row">
      <div class="wave-dot" style="background:${w.color||'#666'}"></div>
      <div class="wave-name">${w.name}</div>
      <div class="wave-sources">${(w.sources||[]).length} sources</div>
    </div>`;
  });
  document.getElementById('waves-list').innerHTML = wavesHtml || '<div class="empty">No waves configured</div>';

  let reportsHtml = '';
  reports.slice(0, 8).forEach(r => {
    reportsHtml += `<div class="report-row">
      <a href="/reports/${r.filename}" target="_blank">${r.filename}</a>
      <span class="date">${r.date || ''}</span>
    </div>`;
  });
  document.getElementById('reports-list').innerHTML = reportsHtml || '<div class="empty">No reports yet — run your first scan</div>';
}

async function runScan() {
  const status = document.getElementById('scan-status');
  status.style.display = 'block';
  status.textContent = 'Scan starting — this takes 2-5 minutes per wave. Check reports when complete.';
  try {
    const r = await fetch('/api/scan', {method: 'POST'});
    const data = await r.json();
    status.textContent = data.message || 'Scan complete! Refresh reports to see results.';
    loadDashboard();
  } catch(e) {
    status.textContent = 'Scan error: ' + e.message;
  }
}

function loadReports() { loadDashboard(); }
function showSection(s) {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  event.target.classList.add('active');
  // In production, each section would load different content
  if (s === 'dashboard') loadDashboard();
}

loadDashboard();
</script></body></html>"""


@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/api/waves")
def api_waves():
    waves = []
    for f in sorted(WAVES_DIR.glob("*.json")):
        with open(f) as fh:
            waves.append(json.load(fh))
    return jsonify(waves)


@app.route("/api/orgs")
def api_orgs():
    orgs = []
    for f in sorted(ORGS_DIR.glob("*.json")):
        with open(f) as fh:
            orgs.append(json.load(fh))
    return jsonify(orgs)


@app.route("/api/reports")
def api_reports():
    reports = []
    for f in sorted(REPORTS_DIR.glob("*"), reverse=True):
        if f.suffix in (".html", ".xlsx", ".json"):
            reports.append({
                "filename": f.name,
                "date": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                "size": f.stat().st_size,
                "type": f.suffix[1:],
            })
    return jsonify(reports[:20])


@app.route("/api/scan", methods=["POST"])
def api_scan():
    """Trigger a scan. In production, this should be async (background task)."""
    try:
        from scanner import run_scan
        run_scan()
        return jsonify({"status": "ok", "message": "Scan complete! Reports generated."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/reports/<path:filename>")
def serve_report(filename):
    return send_from_directory(str(REPORTS_DIR), filename)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
