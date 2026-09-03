"""
GRID SALES DASHBOARD
====================
Generates an interactive HTML dashboard for pipeline tracking,
revenue forecasting, and campaign performance monitoring.

Usage:
    python scripts/outreach/sales_dashboard.py              # Generate dashboard
    python scripts/outreach/sales_dashboard.py --open       # Generate + open in browser
    python scripts/outreach/sales_dashboard.py --json       # Output JSON for external use

Author: Charles Prescott — GRID
Created: 2026-07-08
"""

import sqlite3
import json
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.outreach.sales_campaign_config import (
    PRODUCTS, PERSONAS, PIPELINE_STAGES, MONTHLY_TARGETS, LEAD_SOURCES
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = PROJECT_ROOT / "outputs" / "outreach"
CRM_DB = OUT_DIR / "sales_crm.db"
DASHBOARD_HTML = OUT_DIR / "sales_dashboard.html"

# ══════════════════════════════════════════════════════════════════════════

def get_crm_db() -> sqlite3.Connection:
    if not CRM_DB.exists():
        return None
    db = sqlite3.connect(str(CRM_DB))
    db.row_factory = sqlite3.Row
    return db

def get_pipeline_data(db: sqlite3.Connection) -> Dict:
    """Extract all pipeline data for dashboard."""
    data = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pipeline": {},
        "deals": [],
        "recent_activity": [],
        "monthly_progress": {},
        "persona_breakdown": {},
        "revenue_forecast": {}
    }

    if not db:
        return data

    # Pipeline by stage
    stages = db.execute("""
        SELECT pipeline_stage, COUNT(*) as cnt
        FROM leads WHERE is_active=1
        GROUP BY pipeline_stage
    """).fetchall()
    data["pipeline"] = {s["pipeline_stage"]: s["cnt"] for s in stages}
    data["total_leads"] = sum(data["pipeline"].values())

    # Deals
    deals = db.execute("""
        SELECT d.*, l.org_name, l.persona, l.pipeline_stage as lead_stage
        FROM deals d JOIN leads l ON d.lead_id=l.id
        ORDER BY d.deal_amount DESC
    """).fetchall()
    data["deals"] = [dict(d) for d in deals]
    data["total_pipeline_value"] = sum(d["deal_amount"] or 0 for d in deals if not d["is_won"])
    data["total_won_value"] = sum(d["deal_amount"] or 0 for d in deals if d["is_won"])

    # Recent activity (last 30 days)
    activity = db.execute("""
        SELECT tl.*, l.org_name
        FROM touch_log tl JOIN leads l ON tl.lead_id=l.id
        WHERE tl.sent_at >= date('now', '-30 days')
        ORDER BY tl.sent_at DESC LIMIT 50
    """).fetchall()
    data["recent_activity"] = [dict(a) for a in activity]

    # Monthly progress
    this_month = datetime.now().strftime("%Y-%m")
    monthly = db.execute("""
        SELECT
            COUNT(CASE WHEN sent_at >= date('now','start of month') THEN 1 END) as sent_mtd,
            COUNT(CASE WHEN replied=1 AND sent_at >= date('now','start of month') THEN 1 END) as replies_mtd,
            (SELECT COUNT(*) FROM deals WHERE is_won=1 AND closed_date >= date('now','start of month')) as won_mtd,
            (SELECT COALESCE(SUM(deal_amount),0) FROM deals WHERE is_won=1 AND closed_date >= date('now','start of month')) as revenue_mtd
        FROM touch_log
    """).fetchone()
    data["monthly_progress"] = dict(monthly) if monthly else {}

    # Persona breakdown
    personas = db.execute("""
        SELECT persona, pipeline_stage, COUNT(*) as cnt
        FROM leads WHERE is_active=1
        GROUP BY persona, pipeline_stage
    """).fetchall()
    pb = defaultdict(lambda: defaultdict(int))
    for p in personas:
        pb[p["persona"]][p["pipeline_stage"]] = p["cnt"]
    data["persona_breakdown"] = {k: dict(v) for k, v in pb.items()}

    # Revenue forecast (weighted pipeline)
    forecast_weight = {
        "engaged": 0.10, "sample_sent": 0.15, "proposal_sent": 0.25,
        "negotiating": 0.50, "sent": 0.02, "queued": 0.01
    }
    forecast = 0
    for d in deals:
        if not d["is_won"]:
            weight = forecast_weight.get(d.get("lead_stage", "sent"), 0.02)
            forecast += (d["deal_amount"] or 0) * weight
    data["revenue_forecast"] = {
        "weighted_forecast": round(forecast, 0),
        "best_case": round(data["total_pipeline_value"] * 0.3, 0),
        "worst_case": round(data["total_pipeline_value"] * 0.02, 0)
    }

    # Snapshots for trend
    snapshots = db.execute("""
        SELECT snapshot_date, total_value, lead_count
        FROM pipeline_snapshots
        WHERE stage='summary'
        ORDER BY snapshot_date DESC LIMIT 30
    """).fetchall()
    data["snapshot_trend"] = [dict(s) for s in snapshots]

    return data

def generate_dashboard_html(data: Dict) -> str:
    """Generate interactive HTML dashboard."""
    pipeline = data.get("pipeline", {})
    total = data.get("total_leads", 0)
    deals = data.get("deals", [])
    monthly = data.get("monthly_progress", {})
    forecast = data.get("revenue_forecast", {})
    persona_breakdown = data.get("persona_breakdown", {})
    recent = data.get("recent_activity", [])[:20]
    snapshots = data.get("snapshot_trend", [])

    # Pipeline stage order
    stage_order = ["queued", "sent", "engaged", "sample_sent", "proposal_sent",
                   "negotiating", "won", "lost", "no_response", "unsubscribed", "bounced"]

    # Pipeline bar data
    pipeline_bars = ""
    for stage in stage_order:
        cnt = pipeline.get(stage, 0)
        pct = (cnt / total * 100) if total > 0 else 0
        colors = {
            "queued": "#94a3b8", "sent": "#60a5fa", "engaged": "#fbbf24",
            "sample_sent": "#f59e0b", "proposal_sent": "#f97316",
            "negotiating": "#ef4444", "won": "#22c55e",
            "lost": "#6b7280", "no_response": "#9ca3af",
            "unsubscribed": "#4b5563", "bounced": "#dc2626"
        }
        color = colors.get(stage, "#94a3b8")
        pipeline_bars += f"""
        <div class="pipeline-row">
            <span class="stage-label">{stage.replace('_',' ').title()}</span>
            <div class="bar-track">
                <div class="bar-fill" style="width:{pct}%;background:{color}"></div>
            </div>
            <span class="stage-count">{cnt}</span>
            <span class="stage-pct">{pct:.1f}%</span>
        </div>"""

    # Deal rows
    deal_rows = ""
    for i, d in enumerate(deals[:30]):
        stage_icon = {"proposal": "📝", "negotiating": "🤝", "won": "✅", "lost": "❌"}.get(d.get("stage", ""), "🔵")
        amount = d.get("deal_amount") or 0
        deal_rows += f"""
        <tr>
            <td>{stage_icon}</td>
            <td>{d.get('org_name','')[:40]}</td>
            <td>{d.get('product_id','')}</td>
            <td class="num">${amount:,.0f}</td>
            <td>{d.get('stage','')}</td>
            <td>{d.get('persona','')}</td>
        </tr>"""

    # Persona cards
    persona_cards = ""
    for persona, stages in sorted(persona_breakdown.items()):
        total_p = sum(stages.values())
        won = stages.get("won", 0)
        engaged = stages.get("engaged", 0) + stages.get("negotiating", 0)
        persona_cards += f"""
        <div class="persona-card">
            <div class="persona-name">{persona.replace('_',' ').title()}</div>
            <div class="persona-stats">
                <div><span class="stat-label">Total</span><span class="stat-val">{total_p}</span></div>
                <div><span class="stat-label">Won</span><span class="stat-val won">✅ {won}</span></div>
                <div><span class="stat-label">Active</span><span class="stat-val active">🔵 {engaged}</span></div>
            </div>
        </div>"""

    # Activity feed
    activity_rows = ""
    for a in recent:
        replied = "📩" if a.get("replied") else "📤"
        subj = (a.get("subject") or "No subject")[:60]
        activity_rows += f"""
        <div class="activity-item">
            <span class="activity-icon">{replied}</span>
            <span class="activity-org">{a.get('org_name','Unknown')[:25]}</span>
            <span class="activity-subject">{subj}</span>
            <span class="activity-date">{a.get('sent_at','')[:10]}</span>
        </div>"""

    # Trend data for JS
    trend_dates = json.dumps([s.get("snapshot_date", "") for s in reversed(snapshots)])
    trend_values = json.dumps([s.get("total_value", 0) for s in reversed(snapshots)])

    # Monthly targets
    mt = MONTHLY_TARGETS
    sent_mtd = monthly.get("sent_mtd", 0)
    replies_mtd = monthly.get("replies_mtd", 0)
    won_mtd = monthly.get("won_mtd", 0)
    revenue_mtd = monthly.get("revenue_mtd", 0)

    reply_rate = (replies_mtd / max(1, sent_mtd) * 100) if sent_mtd > 0 else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GRID Sales Dashboard</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0f172a; color: #e2e8f0; padding: 20px; }}
.dashboard {{ max-width: 1400px; margin:0 auto; }}
.header {{ text-align:center; padding: 20px 0 30px; }}
.header h1 {{ font-size: 28px; color: #f8fafc; }}
.header .subtitle {{ color: #94a3b8; font-size: 14px; margin-top: 4px; }}
.header .payment-link {{ margin-top: 12px; }}
.header .payment-link a {{ color: #fbbf24; text-decoration: none; font-size: 15px;
    background: #1e293b; padding: 6px 16px; border-radius: 6px; }}
.header .payment-link a:hover {{ background: #334155; }}

.grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }}
.card {{ background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; }}
.card h2 {{ font-size: 16px; color: #94a3b8; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px; }}
.metric {{ font-size: 36px; font-weight: 700; color: #f8fafc; }}
.metric-label {{ font-size: 13px; color: #64748b; }}

.pipeline-row {{ display:flex; align-items:center; gap:8px; margin-bottom:6px; }}
.stage-label {{ width:130px; font-size:12px; color:#94a3b8; text-align:right; }}
.bar-track {{ flex:1; height:18px; background:#0f172a; border-radius:9px; overflow:hidden; }}
.bar-fill {{ height:100%; border-radius:9px; transition: width 0.3s; }}
.stage-count {{ width:36px; text-align:right; font-size:12px; font-weight:600; }}
.stage-pct {{ width:42px; text-align:right; font-size:11px; color:#64748b; }}

.persona-cards {{ display:flex; flex-wrap:wrap; gap:10px; }}
.persona-card {{ background:#0f172a; border-radius:8px; padding:12px; min-width:150px; }}
.persona-name {{ font-size:13px; color:#f8fafc; font-weight:600; margin-bottom:8px; }}
.persona-stats {{ display:flex; gap:12px; }}
.stat-label {{ font-size:10px; color:#64748b; display:block; }}
.stat-val {{ font-size:16px; font-weight:700; }}
.stat-val.won {{ color:#22c55e; }}
.stat-val.active {{ color:#3b82f6; }}

table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ text-align:left; padding:8px; border-bottom:2px solid #334155; color:#94a3b8;
      font-size:11px; text-transform:uppercase; }}
td {{ padding:8px; border-bottom:1px solid #1e293b; }}
.num {{ text-align:right; font-variant-numeric:tabular-nums; }}

.activity-feed {{ max-height:400px; overflow-y:auto; }}
.activity-item {{ display:flex; align-items:center; gap:8px; padding:4px 0;
                   border-bottom:1px solid #1e293b; font-size:12px; }}
.activity-icon {{ width:24px; }}
.activity-org {{ color:#f8fafc; min-width:120px; }}
.activity-subject {{ color:#94a3b8; flex:1; }}
.activity-date {{ color:#64748b; }}

.progress-ring {{ position:relative; width:120px; height:120px; margin:0 auto; }}
.ring-bg {{ fill:none; stroke:#1e293b; stroke-width:8; }}
.ring-fg {{ fill:none; stroke:#22c55e; stroke-width:8; stroke-linecap:round;
            transform:rotate(-90deg); transform-origin:center; transition:stroke-dashoffset 0.5s; }}
.ring-text {{ position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
              font-size:24px; font-weight:700; }}

.chart-container {{ width:100%; height:200px; position:relative; }}

.footer {{ text-align:center; padding:30px 0 10px; color:#475569; font-size:12px; }}

@media (max-width: 768px) {{
    .grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<div class="dashboard">

<div class="header">
    <h1>📊 GRID Sales Pipeline Dashboard</h1>
    <div class="subtitle">Generated {data['generated_at']} | Global Religious Infrastructure Database</div>
    <div class="payment-link">
        💰 Payment: <a href="https://buymeacoffee.com/CharlesPrescott" target="_blank">buymeacoffee.com/CharlesPrescott</a>
    </div>
</div>

<!-- KPI Cards -->
<div class="grid">
    <div class="card">
        <h2>Total Pipeline Value</h2>
        <div class="metric">${data.get('total_pipeline_value', 0):,.0f}</div>
        <div class="metric-label">Open deals (not yet won)</div>
    </div>
    <div class="card">
        <h2>Won Revenue</h2>
        <div class="metric" style="color:#22c55e">${data.get('total_won_value', 0):,.0f}</div>
        <div class="metric-label">Closed-won deals</div>
    </div>
    <div class="card">
        <h2>Weighted Forecast</h2>
        <div class="metric" style="color:#fbbf24">${forecast.get('weighted_forecast', 0):,.0f}</div>
        <div class="metric-label">Best: ${forecast.get('best_case', 0):,.0f} | Worst: ${forecast.get('worst_case', 0):,.0f}</div>
    </div>
    <div class="card">
        <h2>Active Leads</h2>
        <div class="metric">{total}</div>
        <div class="metric-label">Across {len(pipeline)} pipeline stages</div>
    </div>
</div>

<br>

<!-- Pipeline Funnel + Monthly Progress -->
<div class="grid">
    <div class="card" style="grid-column: span 2;">
        <h2>Pipeline Funnel</h2>
        {pipeline_bars}
    </div>
    <div class="card">
        <h2>Monthly Progress</h2>
        <table>
            <tr><th>Metric</th><th>Current</th><th>Target</th><th>%</th></tr>
            <tr>
                <td>Emails Sent</td>
                <td class="num">{sent_mtd:,}</td>
                <td class="num">{mt['emails_sent']:,}</td>
                <td class="num">{sent_mtd/max(1,mt['emails_sent'])*100:.0f}%</td>
            </tr>
            <tr>
                <td>Reply Rate</td>
                <td class="num">{reply_rate:.1f}%</td>
                <td class="num">{mt['response_rate_target']*100:.0f}%</td>
                <td class="num">{reply_rate/max(0.1,mt['response_rate_target']*100)*100:.0f}%</td>
            </tr>
            <tr>
                <td>Deals Won</td>
                <td class="num">{won_mtd}</td>
                <td class="num">{mt['deals_closed']}</td>
                <td class="num">{won_mtd/max(1,mt['deals_closed'])*100:.0f}%</td>
            </tr>
            <tr>
                <td>Revenue</td>
                <td class="num">${revenue_mtd:,.0f}</td>
                <td class="num">${mt['revenue_target']:,}</td>
                <td class="num">{revenue_mtd/max(1,mt['revenue_target'])*100:.0f}%</td>
            </tr>
        </table>
    </div>
</div>

<br>

<!-- Persona Breakdown + Deals -->
<div class="grid">
    <div class="card">
        <h2>Persona Breakdown</h2>
        <div class="persona-cards">{persona_cards}</div>
    </div>
    <div class="card" style="grid-column: span 2;">
        <h2>Deals ({len(deals)} total)</h2>
        <div style="max-height:400px;overflow-y:auto;">
        <table>
            <tr><th></th><th>Organization</th><th>Product</th><th>Amount</th><th>Stage</th><th>Persona</th></tr>
            {deal_rows}
        </table>
        </div>
    </div>
</div>

<br>

<!-- Recent Activity -->
<div class="grid">
    <div class="card" style="grid-column: span 2;">
        <h2>Recent Activity (30 days)</h2>
        <div class="activity-feed">{activity_rows}</div>
    </div>
</div>

<div class="footer">
    GRID — Global Religious Infrastructure Database | Charles Prescott |
    <a href="https://buymeacoffee.com/CharlesPrescott" style="color:#fbbf24">Buy Me a Coffee</a>
</div>

</div>
</body>
</html>"""

    return html

def generate_json_report(data: Dict) -> str:
    """Generate JSON report."""
    return json.dumps(data, indent=2, default=str)

# ══════════════════════════════════════════════════════════════════════════
# CLI
# ══════════════════════════════════════════════════════════════════════════

def main():
    db = get_crm_db()
    if not db:
        print("⚠️ No CRM database found. Run sales_campaign_manager.py --build first.")
        print(f"   Expected at: {CRM_DB}")
        return

    data = get_pipeline_data(db)
    db.close()

    if len(sys.argv) > 1 and sys.argv[1] == "--json":
        # JSON output
        print(generate_json_report(data))
        return

    # Generate HTML
    html = generate_dashboard_html(data)
    DASHBOARD_HTML.write_text(html, encoding='utf-8')
    print(f"✅ Dashboard saved to: {DASHBOARD_HTML}")

    # Print text summary
    print(f"\n📊 GRID SALES DASHBOARD — {data['generated_at']}")
    print(f"   Pipeline: ${data.get('total_pipeline_value', 0):,.0f} | Won: ${data.get('total_won_value', 0):,.0f}")
    print(f"   Leads: {data.get('total_leads', 0)} | Deals: {len(data.get('deals', []))}")
    print(f"   Payment: https://buymeacoffee.com/CharlesPrescott")

    if "--open" in sys.argv:
        import webbrowser
        webbrowser.open(str(DASHBOARD_HTML))

if __name__ == "__main__":
    main()
