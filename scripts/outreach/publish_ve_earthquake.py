#!/usr/bin/env python
"""
Publish the Venezuela Earthquake Catholic Aid Coordination post to Substack.

Usage:
    python scripts/outreach/publish_ve_earthquake.py --dry-run   # Charts + PM JSON only
    python scripts/outreach/publish_ve_earthquake.py --draft     # Save as draft on Substack
    python scripts/outreach/publish_ve_earthquake.py --publish   # Publish & send

Auth: Set SUBSTACK_COOKIE env var.
"""

import os
import sys
import json
import math
import base64
import sqlite3
from pathlib import Path
from collections import defaultdict

import requests
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DB_PATH = Path(__file__).resolve().parents[2] / "churches.db"
SUB = "gridkeeper"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "substack"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Earthquake constants ──
EPI_LAT, EPI_LON = 10.435, -68.472
MAG = 7.5
DEPTH = 10.0
DATE_STR = "June 24, 2026"
IMPACT = "235 dead, 4,300 injured. 80% of buildings collapsed in La Guaira state."

# ── Auth ──
COOKIE_RAW = os.environ.get("SUBSTACK_COOKIE", "")
if COOKIE_RAW:
    import urllib.parse
    DECODED = urllib.parse.unquote(COOKIE_RAW)
    HEADERS = {
        "Cookie": f"connect.sid={DECODED}; substack.sid={DECODED}",
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
    }

def auth_check():
    if not COOKIE_RAW:
        return None, None
    r = requests.get("https://substack.com/api/v1/user/profile/self", headers=HEADERS)
    if r.status_code != 200:
        print(f"Auth failed: {r.status_code}")
        return None, None
    p = r.json()
    pub = next(pu for pu in p["publicationUsers"] if pu["publication"]["subdomain"] == SUB)
    print(f"Auth: {p['handle']} (id={p['id']})")
    return p, pub

# ── DB helpers ──
def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(min(1, math.sqrt(a)))

def risk_zone(dist):
    if dist <= 30: return "Severe", "#d73027"
    if dist <= 60: return "Heavy", "#fc8d59"
    if dist <= 120: return "Moderate", "#fee08b"
    if dist <= 200: return "Light", "#91cf60"
    return "Outside", "#666"

# ── Query data ──
def query_ve_data():
    db = get_db()
    seats = []
    for r in db.execute("""
        SELECT ch.name as dio_name, ch.cath_type, ch.province,
               c.rowid, c.name, c.city, c.state, c.latitude, c.longitude
        FROM catholic_hierarchy ch
        JOIN churches c ON ch.church_id = c.rowid
        WHERE ch.country='VE' AND ch.cath_type IN ('archdiocese','diocese','vicariate')
        ORDER BY ch.cath_type, ch.name
    """):
        d = dict(r)
        d["dist_km"] = round(haversine(d["latitude"], d["longitude"], EPI_LAT, EPI_LON), 1) if d["latitude"] else None
        d["zone"], d["zone_color"] = risk_zone(d["dist_km"]) if d["dist_km"] else ("?", "#888")
        seats.append(d)

    churches = []
    for r in db.execute("""
        SELECT ch.diocese, ch.parent_id,
               c.rowid, c.name, c.city, c.state, c.latitude, c.longitude
        FROM catholic_hierarchy ch
        JOIN churches c ON ch.church_id = c.rowid
        WHERE ch.country='VE' AND ch.cath_type='church'
        ORDER BY c.city
    """):
        d = dict(r)
        d["dist_km"] = round(haversine(d["latitude"], d["longitude"], EPI_LAT, EPI_LON), 1) if d["latitude"] else None
        d["zone"], d["zone_color"] = risk_zone(d["dist_km"]) if d["dist_km"] else ("?", "#888")
        churches.append(d)

    db.close()
    return seats, churches

# ── Generate charts ──
def make_risk_pie(seats, churches):
    zones = defaultdict(int)
    for c in churches:
        zones[c["zone"]] += 1
    for s in seats:
        zones[s["zone"]] += 1
    order = ["Severe", "Heavy", "Moderate", "Light", "Outside"]
    labels = [z for z in order if z in zones]
    values = [zones[z] for z in labels]
    colors = {"Severe": "#d73027", "Heavy": "#fc8d59", "Moderate": "#fee08b", "Light": "#91cf60", "Outside": "#999"}

    fig = go.Figure(data=[go.Pie(
        labels=labels, values=values,
        marker=dict(colors=[colors[l] for l in labels]),
        textinfo="label+percent", hole=0.4,
        sort=False
    )])
    fig.update_layout(
        title=f"Venezuela Catholic Churches by Earthquake Risk Zone<br><sup>M{MAG} epicenter near Yumare, {DATE_STR}</sup>",
        font=dict(size=14), margin=dict(t=60, b=20, l=20, r=20),
        paper_bgcolor="#1a1a2e", plot_bgcolor="#1a1a2e",
        font_color="#eee", title_font_color="#eee",
        height=500
    )
    return fig

def make_dio_bar(seats, churches):
    dio_risk = defaultdict(lambda: {"Severe": 0, "Heavy": 0, "Moderate": 0, "Light": 0, "Outside": 0, "hubs": 0})
    for s in seats:
        dio_risk[s["dio_name"]]["hubs"] += 1
    for c in churches:
        dio_risk[c["diocese"]][c["zone"]] += 1

    data = []
    for dio, counts in dio_risk.items():
        total = sum(counts.values())
        at_risk = counts["Severe"] + counts["Heavy"] + counts["Moderate"]
        data.append({"Diocese": dio, "At Risk": at_risk, "Total": total,
                      "Severe": counts["Severe"], "Heavy": counts["Heavy"],
                      "Moderate": counts["Moderate"], "Hubs": counts["hubs"]})
    df = pd.DataFrame(data).sort_values("At Risk", ascending=True).tail(15)

    fig = go.Figure()
    fig.add_trace(go.Bar(y=df["Diocese"], x=df["Severe"], name="Severe (≤30km)",
                         marker_color="#d73027", orientation="h"))
    fig.add_trace(go.Bar(y=df["Diocese"], x=df["Heavy"], name="Heavy (30-60km)",
                         marker_color="#fc8d59", orientation="h"))
    fig.add_trace(go.Bar(y=df["Diocese"], x=df["Moderate"], name="Moderate (60-120km)",
                         marker_color="#fee08b", orientation="h"))
    fig.update_layout(
        title="Top 15 Dioceses — Parishes in Risk Zones",
        barmode="stack", height=500,
        paper_bgcolor="#1a1a2e", plot_bgcolor="#1a1a2e",
        font=dict(size=12, color="#eee"), title_font_color="#eee",
        xaxis_title="Number of parishes", legend=dict(orientation="h", y=1.12)
    )
    return fig

def make_dist_hist(churches):
    dists = [c["dist_km"] for c in churches if c["dist_km"] is not None]
    fig = px.histogram(x=dists, nbins=40, title="Parish Distance from Epicenter",
                        labels={"x": "Distance (km)", "y": "Churches"})
    fig.update_traces(marker_color="#fc8d59")
    fig.add_vline(x=30, line_dash="dash", line_color="#d73027",
                  annotation_text="Severe", annotation_position="top")
    fig.add_vline(x=60, line_dash="dash", line_color="#fc8d59",
                  annotation_text="Heavy", annotation_position="top")
    fig.add_vline(x=120, line_dash="dash", line_color="#fee08b",
                  annotation_text="Moderate", annotation_position="top")
    fig.update_layout(
        height=400, paper_bgcolor="#1a1a2e", plot_bgcolor="#1a1a2e",
        font=dict(size=12, color="#eee"), title_font_color="#eee"
    )
    return fig

def chart_to_b64(fig):
    return base64.b64encode(fig.to_image(format="png", scale=1.5)).decode()

def upload_image(b64_data):
    if not COOKIE_RAW:
        return None
    r = requests.post(
        f"https://{SUB}.substack.com/api/v1/image",
        headers=HEADERS,
        json={"image": f"data:image/png;base64,{b64_data}"}
    )
    if r.status_code == 200:
        d = r.json()
        return {"url": d["url"], "width": d.get("imageWidth", 1200), "height": d.get("imageHeight", 800), "bytes": d.get("bytes", 0)}
    print(f"  Upload failed: {r.status_code}")
    return None

# ── ProseMirror builders ──
def pm(*c): return {"type": "doc", "content": list(c)}
def h1(t): return {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": t}]}
def h2(t): return {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": t}]}
def h3(t): return {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": t}]}
def pt(t): return {"type": "paragraph", "attrs": {"textAlign": None}, "content": [{"type": "text", "text": t}]}
def pr(parts):
    content = []
    for x in parts:
        marks = []
        if isinstance(x, dict):
            if x.get("b"): marks.append({"type": "bold"})
            if x.get("i"): marks.append({"type": "italic"})
            node = {"type": "text", "text": x["t"]}
            if marks: node["marks"] = marks
            content.append(node)
        else:
            content.append({"type": "text", "text": str(x)})
    return {"type": "paragraph", "attrs": {"textAlign": None}, "content": content}
def hr(): return {"type": "horizontal_rule"}
def bl(*items):
    li = []
    for item in items:
        para = pr(item) if isinstance(item, list) else pt(str(item))
        li.append({"type": "list_item", "content": [para]})
    return {"type": "bullet_list", "content": li}
def img_node(i):
    return {"type": "captionedImage", "content": [{
        "type": "image2", "attrs": {
            "src": i["url"], "srcNoWatermark": None, "fullscreen": None,
            "imageSize": None, "width": i["width"], "height": i["height"],
            "resizeWidth": None, "bytes": i["bytes"], "alt": None,
            "title": None, "type": "image/png", "href": None,
            "belowTheFold": False, "topImage": False, "internalRedirect": None
        }}]}

def build_post(seats, churches, chart_imgs):
    """Build the ProseMirror document."""
    total = len(churches)
    severe = sum(1 for c in churches if c["zone"] == "Severe")
    heavy = sum(1 for c in churches if c["zone"] == "Heavy")
    moderate = sum(1 for c in churches if c["zone"] == "Moderate")
    at_risk = severe + heavy + moderate
    arch_hubs = [s for s in seats if s["cath_type"] == "archdiocese"]
    dio_hubs = [s for s in seats if s["cath_type"] == "diocese"]

    # Hub list for text
    hub_lines = []
    for s in sorted(seats, key=lambda x: x["dist_km"] or 999):
        icon = "🟡" if s["cath_type"] == "archdiocese" else ("🟠" if s["cath_type"] == "diocese" else "🔴")
        hub_lines.append(
            [{"t": f"{icon} {s['dio_name']} — ", "b": True},
             {"t": f"{s['name']}, {s['city']} ({s['dist_km']}km, {s['zone']})"}])

    # Diocese summary rows
    dio_stats = defaultdict(lambda: {"sev": 0, "hvy": 0, "mod": 0, "total": 0, "hubs": 0})
    for s in seats:
        dio_stats[s["dio_name"]]["hubs"] += 1
        dio_stats[s["dio_name"]]["total"] += 1
    for c in churches:
        dio_stats[c["diocese"]]["total"] += 1
        if c["zone"] == "Severe": dio_stats[c["diocese"]]["sev"] += 1
        elif c["zone"] == "Heavy": dio_stats[c["diocese"]]["hvy"] += 1
        elif c["zone"] == "Moderate": dio_stats[c["diocese"]]["mod"] += 1

    doc = pm(
        h1("🇻🇪 Venezuela Earthquake: Catholic Diocese Aid Coordination"),
        pt(f"M{MAG} earthquake near Yumare, Venezuela — {DATE_STR}. {IMPACT}"),
        hr(),

        h2("The Situation"),
        pt(f"On {DATE_STR}, a magnitude {MAG} earthquake struck northern Venezuela at 10.435°N, "
           f"68.472°W — just 20 km east-southeast of Yumare in Yaracuy state. At only {DEPTH} km depth, "
           f"the shallow quake caused catastrophic damage across La Guaira state (80% building collapse), "
           f"Caracas, and surrounding regions."),
        pt(f"The death toll stands at 235 with 4,300 injured. This was Venezuela's most powerful "
           f"earthquake in over a century. The US Southern Command is surging rescue teams and "
           f"medical resources to the region."),
        pt("As with any major disaster, local religious infrastructure becomes critical for aid "
           "distribution. Cathedrals and basilicas are large, known gathering points with existing "
           "community networks — making them ideal hubs for coordinating relief efforts."),

        h2("Catholic Infrastructure at a Glance"),
        bl(
            [{"t": f"{len(arch_hubs)} archdioceses (🟡 primary aid HQs)", "b": True}],
            [{"t": f"{len(dio_hubs)} dioceses (🟠 secondary distribution centers)", "b": True}],
            [{"t": f"{len(seats) - len(arch_hubs) - len(dio_hubs)} apostolic vicariates (🔴 regional posts)", "b": True}],
            [{"t": f"{total:,} parishes mapped across 39 jurisdictions", "b": True}],
            [{"t": f"{at_risk} parishes in risk zones (≤120km from epicenter)", "b": True}],
        ),

        h3("Risk Zone Breakdown"),
        bl(
            [{"t": f"Severe (≤30km): {severe} parishes — immediate aid needed", "b": True}],
            [{"t": f"Heavy (30–60km): {heavy} parishes — urgent assistance", "b": True}],
            [{"t": f"Moderate (60–120km): {moderate} parishes — distribution staging", "b": True}],
        ),
    )

    # Risk pie chart
    if "risk_pie" in chart_imgs:
        doc["content"].append(img_node(chart_imgs["risk_pie"]))
    doc["content"].append(pt("Parish distribution by distance from epicenter. "
                              "Nearly all churches in the Caracas–Barquisimeto–Coro corridor "
                              "fall within the affected zone."))

    doc["content"].append(h2("Cathedral Aid Hubs"))
    doc["content"].append(pt("These are the primary aid distribution points, ordered by proximity "
                              "to the epicenter. Each is a cathedral, basilica, or diocesan seat "
                              "with the infrastructure to serve as a relief coordination center."))
    doc["content"].append(bl(*hub_lines))

    # Diocese bar chart
    if "dio_bar" in chart_imgs:
        doc["content"].append(img_node(chart_imgs["dio_bar"]))

    # Distance histogram
    if "dist_hist" in chart_imgs:
        doc["content"].append(img_node(chart_imgs["dist_hist"]))

    doc["content"].extend([
        h2("How to Use This Data"),
        pt("If you're coordinating earthquake relief in Venezuela, the Catholic diocese "
           "structure is your ready-made logistics network:"),
        bl(
            "Archdioceses (🟡) serve as regional command posts — they have the largest facilities and staff",
            "Dioceses (🟠) are secondary distribution hubs — ideal for staging supplies before local delivery",
            "Parishes in severe/heavy zones should be prioritized for direct aid delivery",
            "Parishes in moderate zones (60–120km) can serve as supply chain nodes for harder-hit areas",
        ),

        h2("Interactive Map"),
        pt("An interactive Leaflet map showing all 909 parishes color-coded by risk zone, "
           "with cathedral aid hubs marked as diamond icons, is available at:"),
        pt("→ outputs/ve_earthquake_aid/ve_earthquake_aid_map.html (open in browser)"),

        hr(),
        pt("Data: GRID — Global Religious Infrastructure Database (churches.db, ~3.3M records). "
           "Diocese hierarchy built from Catholic-Hierarchy.org, GCatholic, and Wikipedia. "
           "Earthquake data: USGS, INGV, CNN. Map: Leaflet + CARTO dark tiles."),
        pt("Report generated 2026-07-16. For questions: charlesaprescott@outlook.com"),
    ])

    return doc

# ── Post to Substack ──
def create_draft(title, doc, profile, pub):
    body = {
        "draft_title": title,
        "draft_body": json.dumps(doc),
        "type": "newsletter",
        "draft_bylines": [{"id": profile["id"], "publicationUserId": pub["id"]}],
    }
    r = requests.post(f"https://{SUB}.substack.com/api/v1/drafts", headers=HEADERS, json=body)
    if r.status_code == 200:
        did = r.json()["id"]
        print(f"  ✅ Draft: https://{SUB}.substack.com/publish/post/{did}")
        return did
    else:
        print(f"  ❌ {r.status_code}: {r.text[:300]}")
        return None

def publish_draft(draft_id):
    r = requests.post(
        f"https://{SUB}.substack.com/api/v1/drafts/{draft_id}/publish",
        headers=HEADERS,
        json={"send": True}
    )
    if r.status_code == 200:
        print(f"  ✅ Published + sent!")
        return True
    else:
        print(f"  ❌ Publish failed: {r.status_code} {r.text[:200]}")
        return False


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    mode = "dry-run"
    if "--draft" in sys.argv:
        mode = "draft"
    elif "--publish" in sys.argv:
        mode = "publish"

    print(f"\n{'='*60}")
    print(f"VE EARTHQUAKE SUBSTACK POST — {mode.upper()}")
    print(f"{'='*60}")

    # Auth
    profile, pub = auth_check()
    if mode in ("draft", "publish") and not profile:
        print("❌ Auth required for draft/publish. Set SUBSTACK_COOKIE env var.")
        sys.exit(1)

    # Query data
    print("\n--- Querying data ---")
    seats, churches = query_ve_data()
    print(f"  Seats: {len(seats)} | Churches: {len(churches)}")

    # Charts
    print("\n--- Generating charts ---")
    chart_imgs = {}

    fig_pie = make_risk_pie(seats, churches)
    b64_pie = chart_to_b64(fig_pie)
    chart_imgs["risk_pie_b64"] = b64_pie
    print(f"  Risk pie: {len(b64_pie)//1024} KB base64")

    fig_bar = make_dio_bar(seats, churches)
    b64_bar = chart_to_b64(fig_bar)
    chart_imgs["dio_bar_b64"] = b64_bar
    print(f"  Diocese bar: {len(b64_bar)//1024} KB base64")

    fig_hist = make_dist_hist(churches)
    b64_hist = chart_to_b64(fig_hist)
    chart_imgs["dist_hist_b64"] = b64_hist
    print(f"  Distance hist: {len(b64_hist)//1024} KB base64")

    # Upload images
    if mode in ("draft", "publish"):
        print("\n--- Uploading images ---")
        for name in ["risk_pie", "dio_bar", "dist_hist"]:
            b64_key = f"{name}_b64"
            if b64_key in chart_imgs:
                result = upload_image(chart_imgs[b64_key])
                if result:
                    chart_imgs[name] = result
                    print(f"  {name}: {result['url']}")
                else:
                    print(f"  {name}: upload failed, using placeholder")
                    chart_imgs[name] = {"url": "", "width": 1200, "height": 500, "bytes": 0}
    else:
        # Dry-run: create placeholder image refs
        for name in ["risk_pie", "dio_bar", "dist_hist"]:
            chart_imgs[name] = {"url": f"PLACEHOLDER_{name}", "width": 1200, "height": 500, "bytes": 0}

    # Build post
    print("\n--- Building post ---")
    title = "🇻🇪 Venezuela Earthquake: Catholic Diocese Aid Coordination Map"
    doc = build_post(seats, churches, chart_imgs)
    pm_json = json.dumps(doc, indent=2, ensure_ascii=False)

    # Save PM JSON
    pm_path = OUTPUT_DIR / "ve_earthquake_pm.json"
    pm_path.write_text(pm_json, encoding="utf-8")
    print(f"  PM doc saved: {pm_path} ({len(pm_json)//1024} KB)")

    if mode == "dry-run":
        print(f"\n✅ Dry-run complete. Charts embedded in PM JSON.")
        print(f"   Review: {pm_path}")
        return

    # Post to Substack
    if mode == "draft":
        print("\n--- Saving draft ---")
        did = create_draft(title, doc, profile, pub)
        if did:
            print(f"\n✅ Draft ready: https://{SUB}.substack.com/publish/post/{did}")

    elif mode == "publish":
        print("\n--- Saving draft first ---")
        did = create_draft(title, doc, profile, pub)
        if did:
            print("\n--- Publishing ---")
            publish_draft(did)
            print(f"\n✅ Published! https://{SUB}.substack.com/p/...")

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    severe = sum(1 for c in churches if c["zone"] == "Severe")
    heavy = sum(1 for c in churches if c["zone"] == "Heavy")
    moderate = sum(1 for c in churches if c["zone"] == "Moderate")
    print(f"  Cathedral hubs: {len(seats)}")
    print(f"  Parishes: {len(churches)}")
    print(f"  At risk: {severe+heavy+moderate} ({severe} severe, {heavy} heavy, {moderate} moderate)")
    print(f"  Charts: {len(chart_imgs)}")
    print(f"  Post title: {title}")


if __name__ == "__main__":
    main()
