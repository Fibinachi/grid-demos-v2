#!/usr/bin/env python3
"""
GRID Substack Post: Healthcare Access for Rural Congregations
Generates charts & ProseMirror doc, then publishes via Substack API.

Usage:
    python scripts/outreach/publish_substack_healthcare.py --dry-run
    python scripts/outreach/publish_substack_healthcare.py --draft
    python scripts/outreach/publish_substack_healthcare.py --publish
"""
import os, sys, json, base64
from pathlib import Path
from datetime import datetime

import requests
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DB_PATH = Path(__file__).resolve().parents[2] / "churches.db"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "substack" / "healthcare"
SUBDOMAIN = "gridkeeper"

# ── ProseMirror builders ──────────────────────────────────────────────
def pm_doc(*content):
    return {"type": "doc", "content": list(content)}

def pm_heading(text, level=2):
    return {"type": "heading", "attrs": {"level": level},
            "content": [{"type": "text", "text": text}]}

def pm_para(text):
    return {"type": "paragraph", "attrs": {"textAlign": None},
            "content": [{"type": "text", "text": text}]}

def pm_para_rich(parts):
    content = []
    for p in parts:
        marks = []
        if p.get("bold"): marks.append({"type": "bold"})
        if p.get("italic"): marks.append({"type": "italic"})
        node = {"type": "text", "text": p["text"]}
        if marks: node["marks"] = marks
        content.append(node)
    return {"type": "paragraph", "attrs": {"textAlign": None}, "content": content}

def pm_hr():
    return {"type": "horizontal_rule"}

def pm_bullet_list(*items):
    list_items = []
    for item in items:
        para = pm_para_rich(item) if isinstance(item, list) else pm_para(item)
        list_items.append({"type": "list_item", "content": [para]})
    return {"type": "bullet_list", "content": list_items}

def pm_ordered_list(*items):
    list_items = []
    for item in items:
        para = pm_para_rich(item) if isinstance(item, list) else pm_para(item)
        list_items.append({"type": "list_item", "content": [para]})
    return {"type": "ordered_list", "content": list_items}

def pm_image(src, width, height, bts):
    return {"type": "captionedImage", "content": [{
        "type": "image2",
        "attrs": {"src": src, "srcNoWatermark": None, "fullscreen": None,
                  "imageSize": None, "width": width, "height": height,
                  "resizeWidth": None, "bytes": bts, "alt": None, "title": None,
                  "type": "image/png", "href": None, "belowTheFold": False,
                  "topImage": False, "internalRedirect": None}
    }]}


# ── Data (load from pre-computed JSON — instant) ──────────────────────

def load_stats() -> dict:
    """Load pre-computed healthcare stats from JSON files."""
    base = Path(__file__).resolve().parents[2] / "outputs" / "healthcare_access"

    s = {}

    with open(base / "full_summary.json") as f:
        full = json.load(f)

    s["rucc"] = full["rucc_breakdown"]

    # Override with clean versions
    with open(base / "state_rural_healthcare_clean.json") as f:
        raw_states = json.load(f)
    s["states"] = [st for st in raw_states if st["state"] != "PR"]

    with open(base / "county_hotspots_clean.json") as f:
        s["counties"] = json.load(f)

    with open(base / "faith_rural_healthcare_clean.json") as f:
        s["faiths"] = json.load(f)

    with open(base / "extreme_deserts_clean.json") as f:
        s["extreme"] = json.load(f)

    with open(base / "tradition_rural_healthcare.json") as f:
        s["traditions"] = json.load(f)

    # Build rural and metro aggregates
    rural = full["rural_aggregated"][0]
    metro = full["metro_comparison"][0]

    s["rural"] = {
        "total_rural": rural["total_rural_churches"],
        "avg_hosp": rural["avg_hospital_km"],
        "avg_clinic": rural["avg_clinic_km"],
        "avg_fire": rural["avg_fire_km"],
        "avg_police": rural["avg_police_km"],
        "over_15": rural["over_15km"],
        "over_30": rural["over_30km"],
        "over_50": rural["over_50km"],
        "over_100": rural["over_100km"],
    }

    # Override with clean
    with open(base / "state_rural_healthcare_clean.json") as f:
        all_states = json.load(f)
    # Recompute rural totals from clean state data (exclude PR)
    clean_states = [st for st in all_states if st["state"] != "PR"]
    s["rural"]["total_rural"] = sum(st["rural_churches"] for st in clean_states)
    s["rural"]["over_30"] = sum(st["over_30km"] for st in clean_states)
    s["rural"]["over_50"] = sum(st["over_50km"] for st in clean_states)
    s["rural"]["over_100"] = sum(st.get("over_100km", 0) for st in clean_states)

    s["metro"] = {
        "total_metro": metro["total_metro_churches"],
        "avg_hosp": metro["avg_hospital_km"],
        "avg_clinic": metro["avg_clinic_km"],
        "over_30": metro["over_30km"],
    }

    return s


# ── Figures ────────────────────────────────────────────────────────────

def make_figures(stats: dict, img_dir: Path) -> dict:
    images = {}

    # 1. RUCC bar chart
    df = pd.DataFrame(stats["rucc"])
    if not df.empty:
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        df_sorted = df.sort_values('rucc_code')
        fig.add_trace(go.Bar(x=df_sorted['rucc_label'], y=df_sorted['avg_hospital_km'],
            name='Avg Hospital (km)', marker_color='#e74c3c',
            text=df_sorted['avg_hospital_km'].round(0).astype(int), textposition='outside'),
            secondary_y=False)
        fig.add_trace(go.Scatter(x=df_sorted['rucc_label'],
            y=df_sorted['pct_over_30km'],
            name='% >30 km', mode='lines+markers',
            marker=dict(size=10, color='#2c3e50'), line=dict(width=3)),
            secondary_y=True)
        fig.update_layout(title='Hospital Distance & Healthcare Desert Rate by Rurality',
            height=500, template='plotly_white',
            legend=dict(orientation='h', y=1.15))
        fig.update_yaxes(title_text='Avg Distance (km)', secondary_y=False)
        fig.update_yaxes(title_text='% >30 km from Hospital', secondary_y=True)
        fig.update_xaxes(tickangle=25)
        path = img_dir / "rucc_hospital.png"
        fig.write_image(str(path), width=1200, height=600, scale=2)
        images["rucc"] = (path, 2400, 1200)

    # 2. Emergency services comparison (rural)
    rural = stats["rural"]
    fig = go.Figure()
    cats = ['Hospital', 'Clinic', 'Fire Station', 'Police Station']
    vals = [rural['avg_hosp'], rural['avg_clinic'], rural['avg_fire'], rural['avg_police']]
    colors = ['#e74c3c', '#e67e22', '#27ae60', '#2980b9']
    fig.add_trace(go.Bar(x=cats, y=vals, marker_color=colors,
        text=[f'{v:.1f} km' for v in vals], textposition='outside'))
    fig.update_layout(title='Rural Emergency Service Distances Compared',
        yaxis_title='Average Distance (km)', template='plotly_white', height=450)
    path = img_dir / "emergency_compare.png"
    fig.write_image(str(path), width=1000, height=500, scale=2)
    images["emergency"] = (path, 2000, 1000)

    # 3. State bar chart
    df_states = pd.DataFrame(stats["states"]).head(15)
    if not df_states.empty:
        fig = px.bar(df_states.sort_values('avg_hospital_km'), x='avg_hospital_km', y='state',
            orientation='h', color='avg_hospital_km', color_continuous_scale='Reds',
            title='Rural Hospital Distance by State (Top 15)',
            labels={'avg_hospital_km': 'Avg Distance to Nearest Hospital (km)', 'state': ''},
            text=df_states['avg_hospital_km'].round(0).astype(int))
        fig.update_traces(textposition='outside')
        fig.update_layout(height=500, template='plotly_white', coloraxis_showscale=False)
        path = img_dir / "states_hospital.png"
        fig.write_image(str(path), width=1000, height=550, scale=2)
        images["states"] = (path, 2000, 1100)

    # 4. Tradition desert rate
    df_trad = pd.DataFrame(stats["traditions"])
    if not df_trad.empty:
        df_trad['desert_rate'] = (df_trad['over_30km'] / df_trad['churches'] * 100).round(1)
        fig = px.bar(df_trad.sort_values('desert_rate'), x='desert_rate', y='tradition',
            orientation='h', color='desert_rate', color_continuous_scale='Reds',
            title='Healthcare Desert Rate by Tradition (>30 km)',
            labels={'desert_rate': '% Rural Churches >30 km from Hospital', 'tradition': ''},
            text=df_trad['desert_rate'].apply(lambda x: f'{x:.1f}%'))
        fig.update_traces(textposition='outside')
        fig.update_layout(height=450, template='plotly_white', coloraxis_showscale=False)
        path = img_dir / "tradition_desert.png"
        fig.write_image(str(path), width=1000, height=500, scale=2)
        images["tradition"] = (path, 2000, 1000)

    # 5. County hotspots (Lower 48)
    df_county = pd.DataFrame(stats["counties"])
    if not df_county.empty:
        df_county['label'] = df_county.apply(lambda r: f"{r['county']}, {r['state']}", axis=1)
        fig = px.bar(df_county.sort_values('avg_hospital_km'), x='avg_hospital_km', y='label',
            orientation='h', color='avg_hospital_km', color_continuous_scale='Reds',
            title='Worst Counties for Rural Healthcare Access (Lower 48)',
            labels={'avg_hospital_km': 'Avg Hospital Distance (km)', 'label': ''},
            text=df_county['avg_hospital_km'].round(0).astype(int))
        fig.update_traces(textposition='outside')
        fig.update_layout(height=450, template='plotly_white', coloraxis_showscale=False)
        path = img_dir / "counties_hospital.png"
        fig.write_image(str(path), width=1000, height=500, scale=2)
        images["counties"] = (path, 2000, 1000)

    return images


# ── Upload ─────────────────────────────────────────────────────────────

def upload_images(images: dict, headers: dict) -> dict:
    result = {}
    for name, (local_path, w, h) in images.items():
        with open(local_path, "rb") as f:
            img_bytes = f.read()
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        r = requests.post(
            f"https://{SUBDOMAIN}.substack.com/api/v1/image",
            headers=headers,
            json={"image": f"data:image/png;base64,{b64}"})
        if r.status_code == 200:
            data = r.json()
            result[name] = {
                "url": data["url"],
                "width": data.get("imageWidth", w),
                "height": data.get("imageHeight", h),
                "bytes": data.get("bytes", len(img_bytes))}
            print(f"   [OK] {name} uploaded")
        else:
            print(f"   [WARN] {name} upload failed ({r.status_code})")
    return result


# ── Build ProseMirror doc ──────────────────────────────────────────────

def build_doc(stats: dict, imgs: dict) -> list:
    today = datetime.now().strftime("%B %d, %Y")
    rural = stats["rural"]
    metro = stats["metro"]
    ratio = round(rural['avg_hosp'] / metro['avg_hosp'], 1)
    desert_pct = round(rural['over_30'] / rural['total_rural'] * 100, 1)

    def img(name):
        if name in imgs:
            i = imgs[name]
            return pm_image(i["url"], i["width"], i["height"], i["bytes"])
        return pm_para(f"[Image: {name}]")

    # Build top state list text
    top_states = stats["states"][:5]
    state_lines = []
    for st in top_states:
        pct = round(st['over_30km'] / st['rural_churches'] * 100, 1) if st['rural_churches'] else 0
        state_lines.append(
            [{"text": f"{st['state']}: ", "bold": True},
             {"text": f"{st['rural_churches']:,} rural churches, avg {st['avg_hospital_km']} km to hospital, {pct}% in healthcare desert"}])

    # Build county lines
    county_lines = []
    for co in stats["counties"][:7]:
        county_lines.append(
            [{"text": f"{co['county']}, {co['state']}: ", "bold": True},
             {"text": f"{co['churches']} churches, avg {co['avg_hospital_km']} km"}])

    doc = [
        pm_heading("How Far Is the Nearest Hospital? — Healthcare Access for Rural Congregations", 1),
        pm_para_rich([{"text": today, "italic": True},
                      {"text": " · Charles Prescott · GRID Project", "italic": True}]),
        pm_hr(),

        pm_heading("The Rural Healthcare Gap"),
        pm_para(f"When disaster strikes a rural community — a tornado, a flash flood, a farming accident — the nearest hospital may be 30, 50, or even 100 kilometers away. Rural congregations are often the first gathering point in a crisis, but how close are they to actual medical care?"),
        pm_para(f"Using the GRID database of {rural['total_rural']:,} rural American congregations (in USDA RUCC category 8–9 counties), combined with OpenStreetMap data on 7,541 hospitals and 23,352 clinics nationwide, we now have an answer."),
        pm_para_rich([
            {"text": f"Rural congregations are {ratio}× farther from hospitals than their metro counterparts.", "bold": True}]),
        pm_para_rich([
            {"text": f"Rural: {rural['avg_hosp']} km average. Metro: {metro['avg_hosp']} km average.", "italic": True}]),

        pm_heading("By the Numbers"),
        pm_bullet_list(
            [{"text": "Rural congregations analyzed: ", "bold": True}, {"text": f"{rural['total_rural']:,}"}],
            [{"text": "Average distance to nearest hospital: ", "bold": True}, {"text": f"{rural['avg_hosp']} km"}],
            [{"text": "Average distance to nearest clinic: ", "bold": True}, {"text": f"{rural['avg_clinic']} km (farther than hospitals!)"}],
            [{"text": "Healthcare deserts (>30 km): ", "bold": True}, {"text": f"{rural['over_30']:,} congregations ({desert_pct}%)"}],
            [{"text": "Severe deserts (>50 km): ", "bold": True}, {"text": f"{rural['over_50']:,} congregations"}],
            [{"text": "Extreme deserts (>100 km): ", "bold": True}, {"text": f"{rural['over_100']:,} congregations, 85% in Alaska"}],
        ),

        img("rucc"),
        pm_para("The gradient is stark. In the most urban counties (RUCC 1), only 0.4% of congregations are more than 30 km from a hospital. In the most rural (RUCC 9), that jumps to 17.7%. Rural RUCC 8 counties — those adjacent to metro areas — actually have the highest desert rate at 27.9%, because the single county-seat hospital leaves outlying communities stranded."),

        pm_heading("Emergency Services: Who Gets There First?"),
        pm_para("A surprising finding: in rural areas, fire stations and police stations are consistently closer than hospitals. But clinics — which in metro areas are slightly closer than hospitals — are actually farther away in the countryside."),
        img("emergency"),
        pm_para("This means rural healthcare is hospital-centric. Clinics cluster near the same county-seat hospitals rather than distributing into smaller communities. Fire and EMS, designed for rapid response, have better rural coverage — making rural fire stations and the churches near them natural partners for emergency medical response."),

        pm_heading("Which States Are Worst?"),
        img("states"),
        pm_para(f"Alaska is in a category of its own — {top_states[0]['rural_churches']:,} rural congregations average {top_states[0]['avg_hospital_km']} km from a hospital. But in the Lower 48, New Mexico ({stats['states'][1]['avg_hospital_km']} km), Nevada ({stats['states'][2]['avg_hospital_km']} km), and Utah ({stats['states'][3]['avg_hospital_km']} km) lead the list. These are states with large federal lands, sparse populations, and hospital systems concentrated in a few cities."),
        pm_para_rich([{"text": "Note: Puerto Rico is excluded from these rankings because OpenStreetMap has zero hospitals mapped on the island. Real hospitals exist — they're just not in OSM.", "italic": True}]),

        pm_heading("Which Traditions Are Most Affected?"),
        img("tradition"),
        pm_para("Methodist churches stand out dramatically — 95.3% of rural Methodist congregations are more than 30 km from a hospital. This reflects the Methodist circuit-rider heritage: churches were deliberately planted in remote communities served by traveling preachers. Latter-day Saint congregations (49.3%) and Seventh-day Adventist congregations (31.1%) also show elevated healthcare desert rates."),
        pm_para("Protestant (22.6%) and Baptist (15.9%) congregations make up the largest absolute numbers simply because they're the most numerous in rural America."),

        pm_heading("County-Level Hotspots"),
        img("counties"),
        pm_para("The worst counties in the Lower 48 are in the Nebraska Sand Hills and the High Plains. Hooker County, Nebraska (8 churches, 99 km average) and Thomas County, Nebraska (8 churches, 88 km) top the list. These are counties with fewer than 1,000 people, where the nearest hospital may be two counties away."),

        pm_heading("What This Means"),
        pm_para(f"{rural['over_30']:,} rural congregations are more than 30 kilometers from a hospital. In a medical emergency, that's a 30+ minute drive — potentially life-threatening for stroke, heart attack, or severe trauma."),
        pm_para("But these same congregations have assets that matter in a crisis: parking lots for helicopter evacuation, kitchens for feeding operations, large indoor spaces for sheltering, and trusted community relationships."),
        pm_para("Rural fire stations average just 11.4 km from these churches. That proximity — combined with the fact that many rural fire departments are volunteer-staffed and community-based — suggests a natural partnership. Churches could serve as designated first-aid points, evacuation assembly areas, or temporary triage sites in coordination with local fire/EMS."),
        pm_para("The data shows where the gaps are. The next step is figuring out how to close them."),

        pm_hr(),
        pm_heading("Data & Methodology"),
        pm_bullet_list(
            [{"text": "Congregation data: ", "bold": True}, {"text": "GRID churches.db (3.29M records, 1.02M US)"}],
            [{"text": "Rural classification: ", "bold": True}, {"text": "USDA RUCC 2023, 3,233 counties"}],
            [{"text": "Healthcare facilities: ", "bold": True}, {"text": "OpenStreetMap Overpass API (7,541 hospitals + 23,352 clinics, extracted 2026-07-10)"}],
            [{"text": "Emergency stations: ", "bold": True}, {"text": "34,888 fire + 13,933 police from OSM"}],
            [{"text": "Distance calculation: ", "bold": True}, {"text": "Haversine formula via scipy cKDTree, 3D cartesian coordinates"}],
            [{"text": "Data quality: ", "bold": True}, {"text": "1,684 churches with GPS outside US bounds excluded; PR excluded (0 OSM hospitals)"}],
        ),
        pm_hr(),
        pm_para("GRID (Global Religious Infrastructure Database) maps every house of worship on Earth. The full database is available on BigQuery at american-rel-infra.American_Religious_Infrastructure. Contact: charles.prescott@gridproject.org. Support this work at buymeacoffee.com/CharlesPrescott."),
    ]
    return doc


# ── Main ───────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    if not any([args.dry_run, args.draft, args.publish]):
        print("Specify --dry-run, --draft, or --publish")
        sys.exit(1)

    print("[1/4] Querying database...")
    stats = load_stats()
    print(f"   {stats['rural']['total_rural']:,} rural churches, avg {stats['rural']['avg_hosp']} km to hospital")

    print("\n[2/4] Generating visualizations...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img_dir = OUTPUT_DIR / f"charts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    img_dir.mkdir(parents=True, exist_ok=True)
    images = make_figures(stats, img_dir)

    if args.dry_run:
        imgs = {name: {"url": str(path), "width": w, "height": h, "bytes": 0}
                for name, (path, w, h) in images.items()}
        doc = build_doc(stats, imgs)
        pm_json = json.dumps(pm_doc(*doc))
        pm_path = img_dir / "prosemirror_doc.json"
        pm_path.write_text(pm_json, encoding="utf-8")
        print(f"\n[DONE] ProseMirror doc saved to: {pm_path}")
        print(f"   Charts in: {img_dir}")
        return

    print("\n[3/4] Connecting to Substack...")
    cookie = os.environ.get("SUBSTACK_COOKIE", "")
    if not cookie:
        print("ERROR: SUBSTACK_COOKIE env var not set.")
        sys.exit(1)

    cookie_str = f"connect.sid={cookie}; substack.sid={cookie}"
    headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json"}

    r = requests.get("https://substack.com/api/v1/user/profile/self", headers=headers)
    if r.status_code != 200:
        print(f"   Auth failed ({r.status_code}): {r.text[:200]}")
        sys.exit(1)
    profile = r.json()
    pub_user = next((pu for pu in profile.get("publicationUsers", [])
                     if pu["publication"]["subdomain"] == SUBDOMAIN), None)
    if not pub_user:
        print(f"   No publication found: {SUBDOMAIN}")
        sys.exit(1)
    print(f"   Authenticated as {profile.get('handle')}")

    print("   Uploading images...")
    imgs = upload_images(images, headers)

    print("\n[4/4] Creating draft...")
    doc = build_doc(stats, imgs)
    pm_json = json.dumps(pm_doc(*doc))

    rural = stats["rural"]
    metro = stats["metro"]
    ratio = round(rural['avg_hosp'] / metro['avg_hosp'], 1)
    desert_pct = round(rural['over_30'] / rural['total_rural'] * 100, 1)

    draft_body = {
        "draft_title": "How Far Is the Nearest Hospital? — Healthcare Access for Rural Congregations",
        "draft_subtitle": f"Rural churches are {ratio}× farther from hospitals than metro churches. {desert_pct}% sit in healthcare deserts.",
        "draft_body": pm_json,
        "type": "newsletter",
        "draft_bylines": [{"id": profile["id"], "publicationUserId": pub_user["id"]}]}

    r = requests.post(f"https://{SUBDOMAIN}.substack.com/api/v1/drafts",
                      headers=headers, json=draft_body)
    if r.status_code != 200:
        print(f"   ERROR ({r.status_code}): {r.text[:300]}")
        sys.exit(1)
    draft = r.json()
    draft_id = draft["id"]
    print(f"   Draft created (id={draft_id})")

    if args.draft:
        print(f"\n[DONE] https://{SUBDOMAIN}.substack.com/publish/post/{draft_id}")
        return

    if args.publish:
        print("   Publishing...")
        r = requests.put(
            f"https://{SUBDOMAIN}.substack.com/api/v1/drafts/{draft_id}/publish",
            headers=headers,
            json={"send": True, "share_automatically": False})
        if r.status_code == 200:
            slug = r.json().get("slug", draft_id)
            print(f"\n[DONE] Published! https://{SUBDOMAIN}.substack.com/p/{slug}")
        else:
            print(f"   ERROR ({r.status_code}): {r.text[:200]}")


if __name__ == "__main__":
    main()
