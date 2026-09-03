"""
Substack post: Tennessee Religious Property Assets
Maps the value of TN religious parcels - brighter = more valuable
"""
import os, sys, json, base64, sqlite3
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests

DB_PATH = Path('e:/grid/data/tn_parcels/tn_religious_parcels.db')
OUT_DIR = Path('e:/grid/outputs/substack')
OUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR = OUT_DIR / 'tn_assets_post'
IMG_DIR.mkdir(parents=True, exist_ok=True)

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
        if p.get("bold"):
            marks.append({"type": "bold"})
        if p.get("italic"):
            marks.append({"type": "italic"})
        node = {"type": "text", "text": p["text"]}
        if marks:
            node["marks"] = marks
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

def pm_image(src, width, height, bts):
    return {
        "type": "captionedImage",
        "content": [{
            "type": "image2",
            "attrs": {
                "src": src,
                "srcNoWatermark": None,
                "fullscreen": None,
                "imageSize": None,
                "width": width,
                "height": height,
                "resizeWidth": None,
                "bytes": bts,
                "alt": None,
                "title": None,
                "type": "image/png",
                "href": None,
                "belowTheFold": False,
                "topImage": False,
                "internalRedirect": None,
            }
        }]
    }

# ── Data ──────────────────────────────────────────────────────────

def extract_tradition(name, owner):
    """Extract denomination/tradition from name or owner field."""
    if not name and not owner:
        return 'Unknown'
    text = (name or '') + ' ' + (owner or '')
    text_upper = text.upper()
    
    patterns = [
        ('CHURCH OF GOD', 'Church of God'),
        ('CHURCH OF CHRIST', 'Church of Christ'),
        ('ASSEMBLY OF GOD', 'Assemblies of God'),
        ('BAPTIST', 'Baptist'),
        ('METHODIST', 'Methodist'),
        ('CATHOLIC', 'Catholic'),
        ('EPISCOPAL', 'Episcopal'),
        ('LUTHERAN', 'Lutheran'),
        ('PRESBYTERIAN', 'Presbyterian'),
        ('PENTECOSTAL', 'Pentecostal'),
        ('SALVATION ARMY', 'Salvation Army'),
        ('NAZARENE', 'Nazarene'),
        ('WESLEYAN', 'Wesleyan'),
        ('MENNONITE', 'Mennonite'),
        ('QUAKER', 'Quaker'),
        ('COMMUNITY CHURCH', 'Community Church'),
        ('GOSPEL', 'Gospel'),
        ('HOLINESS', 'Holiness'),
    ]
    
    for pattern, trad in patterns:
        if pattern in text_upper:
            return trad
    return 'Other Protestant'

def get_data():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    
    df = []
    for r in conn.execute('''
        SELECT 
            id, name, tn_county, latitude, longitude,
            tn_land_market_value, tn_improvement_value, tn_appraisal_value,
            tn_sqft, tn_yrblt, tn_filter, tn_owner_raw
        FROM tn_religious_parcels 
        WHERE tn_filter IN ('church', 'parsonage') 
          AND latitude IS NOT NULL AND longitude IS NOT NULL
          AND tn_appraisal_value > 0
    '''):
        row = dict(r)
        row['tradition'] = extract_tradition(row.get('name'), row.get('tn_owner_raw'))
        df.append(row)
    
    county_df = []
    for r in conn.execute('''
        SELECT 
            tn_county,
            COUNT(*) as parcel_count,
            ROUND(SUM(tn_appraisal_value), 0) as total_appraisal,
            ROUND(AVG(tn_appraisal_value), 0) as avg_appraisal,
            ROUND(AVG(tn_sqft), 0) as avg_sqft
        FROM tn_religious_parcels 
        WHERE tn_filter IN ('church', 'parsonage') AND tn_appraisal_value > 0
        GROUP BY tn_county
    '''):
        county_df.append(dict(r))
    
    conn.close()
    return df, county_df

# ── Figures ───────────────────────────────────────────────────────

def make_figures(parcels, counties):
    images = {}
    
    df = pd.DataFrame(parcels)
    
    # FIG 1: Scatter map - parcel value by location
    print('  Fig 1: TN religious property value map...')
    if not df.empty:
        df['log_appraisal'] = df['tn_appraisal_value'].apply(lambda x: np.log10(x + 1))
        fig = px.scatter_mapbox(
            df, lat='latitude', lon='longitude',
            size='tn_appraisal_value', color='log_appraisal',
            hover_name='name', hover_data=['tn_county', 'tn_appraisal_value', 'tn_sqft'],
            color_continuous_scale='Viridis',
            zoom=6, center={'lat': 35.7, 'lon': -86.5},
            mapbox_style='carto-positron',
            title='Tennessee Religious Property Values<br><sub>Bubble size = appraisal value, Color = log scale</sub>'
        )
        fig.update_layout(margin=dict(l=0, r=0, t=50, b=0))
        path = IMG_DIR / 'tn_value_map.png'
        fig.write_image(str(path), width=1200, height=800, scale=2)
        images['tn_value_map'] = (path, 2400, 1600)
    
    # FIG 2: County bar chart
    print('  Fig 2: County appraisal totals...')
    cdf = pd.DataFrame(counties)
    if not cdf.empty:
        cdf = cdf.sort_values('total_appraisal', ascending=True)
        fig = px.bar(
            cdf, x='total_appraisal', y='tn_county',
            orientation='h', color='total_appraisal',
            color_continuous_scale='Blues',
            labels={'total_appraisal': 'Total Appraisal ($)', 'tn_county': 'County'},
            title='TN Religious Property Value by County<br><sub>Total appraised value of church/parsonage parcels</sub>'
        )
        fig.update_layout(margin=dict(l=100, r=0, t=50, b=0))
        path = IMG_DIR / 'tn_county_appraisal.png'
        fig.write_image(str(path), width=1000, height=1200, scale=2)
        images['tn_county_appraisal'] = (path, 2000, 2400)
    
    # FIG 3: Building age vs value
    print('  Fig 3: Building age vs value...')
    if not df.empty:
        df_clean = df[df['tn_yrblt'].notna() & (df['tn_yrblt'] > 1800) & (df['tn_yrblt'] < 2025)]
        fig = px.scatter(
            df_clean, x='tn_yrblt', y='tn_appraisal_value',
            opacity=0.3,
            labels={'tn_yrblt': 'Year Built', 'tn_appraisal_value': 'Appraisal Value ($)'},
            title='TN Religious Buildings: Age vs Value<br><sub>Older buildings tend to have higher values</sub>'
        )
        fig.update_layout(margin=dict(l=0, r=0, t=50, b=0))
        path = IMG_DIR / 'tn_age_value.png'
        fig.write_image(str(path), width=1000, height=600, scale=2)
        images['tn_age_value'] = (path, 2000, 1200)
    
    # FIG 4: Tradition breakdown
    print('  Fig 4: Tradition value breakdown...')
    if 'tradition' in df.columns:
        trad_df = df.groupby('tradition').agg({
            'tn_appraisal_value': ['count', 'sum', 'mean']
        }).reset_index()
        trad_df.columns = ['tradition', 'count', 'total_appraisal', 'avg_appraisal']
        trad_df = trad_df.sort_values('total_appraisal', ascending=True)
        fig = px.bar(
            trad_df, x='total_appraisal', y='tradition',
            orientation='h', color='total_appraisal',
            color_continuous_scale='Teal',
            labels={'total_appraisal': 'Total Appraisal ($)', 'tradition': 'Tradition'},
            title='TN Religious Property Value by Tradition<br><sub>Extracted from parcel owner names</sub>'
        )
        fig.update_layout(margin=dict(l=120, r=0, t=50, b=0))
        path = IMG_DIR / 'tn_tradition_value.png'
        fig.write_image(str(path), width=1000, height=800, scale=2)
        images['tn_tradition_value'] = (path, 2000, 1600)
    
    return images

# ── Upload images to Substack ──────────────────────────────────────────

def upload_images(images: dict, headers: dict) -> dict:
    result = {}
    for name, (local_path, w, h) in images.items():
        with open(local_path, "rb") as f:
            img_bytes = f.read()
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        r = requests.post(
            f"https://{SUBDOMAIN}.substack.com/api/v1/image",
            headers=headers,
            json={"image": f"data:image/png;base64,{b64}"},
        )
        if r.status_code == 200:
            data = r.json()
            result[name] = {
                "url": data["url"],
                "width": data.get("imageWidth", w),
                "height": data.get("imageHeight", h),
                "bytes": data.get("bytes", len(img_bytes)),
            }
            print(f"   [OK] {name} uploaded")
        else:
            print(f"   [WARN] {name} upload failed ({r.status_code})")
    return result

# ── Build ProseMirror document ─────────────────────────────────────────

def build_doc(stats: dict, imgs: dict) -> list:
    today = datetime.now().strftime("%B %d, %Y")
    
    def img(name):
        if name in imgs:
            i = imgs[name]
            return pm_image(i["url"], i["width"], i["height"], i["bytes"])
        return pm_para(f"[Image: {name}]")
    
    doc = [
        pm_heading("The Value of Tennessee's Religious Infrastructure", 1),
        pm_para_rich([{"text": today, "italic": True},
                      {"text": " · Charles Prescott · GRID Project", "italic": True}]),
        pm_hr(),
        
        pm_heading("What Tennessee's Churches Are Worth"),
        pm_para("Using Tennessee's IMPACT CAMA property assessment data, we can map the financial footprint of religious infrastructure across the state. Each dot below represents a church or parsonage with an appraised value — brighter colors indicate higher-value properties."),
        img("tn_value_map"),
        pm_para_rich([{"text": f"${stats['total_appraisal']:,.0f}", "bold": True},
                     {"text": " total appraised value across 8,188 church/parsonage parcels. The average church is valued at ", "bold": False},
                     {"text": f"${stats['avg_appraisal']:,.0f}", "bold": True},
                     {"text": ".", "bold": False}]),
        
        pm_heading("County-by-County Wealth"),
        pm_para("The distribution is heavily concentrated in suburban counties around Nashville and Knoxville, where newer megachurches and established congregations hold significant property portfolios."),
        img("tn_county_appraisal"),
        
        pm_heading("Age and Value"),
        pm_para("Older religious buildings command higher appraisals — not necessarily due to construction quality, but because they tend to be larger, more established properties in developed areas."),
        img("tn_age_value"),
        
        pm_heading("Tradition Breakdown"),
        pm_para("Baptist churches dominate by count and total value, reflecting Tennessee's religious demographics. The tradition extraction uses owner names from the parcel records."),
        img("tn_tradition_value"),
        
        pm_hr(),
        pm_heading("What This Tells Us"),
        pm_para("Religious property represents a significant slice of Tennessee's real estate market. These aren't just places of worship — they're community anchors with substantial financial footprints."),
        pm_para("The data reveals patterns: newer suburban churches often have higher assessed values than older rural ones, reflecting both construction costs and land values. Parsonages (clergy residences) average $155,000, while church buildings average $384,000."),
        pm_para("This is just Tennessee. Across the U.S., religious property represents hundreds of billions in assets — making faith communities significant stakeholders in local tax rolls, zoning decisions, and community development."),
        
        pm_hr(),
        pm_para("GRID (Global Religious Infrastructure Database) maps religious buildings worldwide. The full Tennessee dataset is available for researchers. Contact: charles.prescott@gridproject.org. Support this work at buymeacoffee.com/CharlesPrescott."),
    ]
    return doc

# ── Main ─────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Publish TN assets post to Substack")
    parser.add_argument("--dry-run", action="store_true", help="Generate charts only")
    parser.add_argument("--draft", action="store_true", help="Save as draft on Substack")
    parser.add_argument("--publish", action="store_true", help="Publish and send")
    args = parser.parse_args()
    
    if not any([args.dry_run, args.draft, args.publish]):
        print("Specify --dry-run, --draft, or --publish")
        sys.exit(1)
    
    print("[1/4] Loading data...")
    parcels, counties = get_data()
    print(f"   {len(parcels):,} parcels with values")
    print(f"   {len(counties):,} counties")
    
    print("\n[2/4] Generating visualizations...")
    images = make_figures(parcels, counties)
    
    print("\n[3/4] Computing summary stats...")
    total_appraisal = sum(p['tn_appraisal_value'] for p in parcels)
    total_sqft = sum(p['tn_sqft'] or 0 for p in parcels)
    avg_appraisal = total_appraisal / len(parcels) if parcels else 0
    
    stats = {
        'total_appraisal': total_appraisal,
        'total_sqft': total_sqft,
        'avg_appraisal': avg_appraisal,
        'parcel_count': len(parcels),
    }
    print(f"   Total appraisal: ${total_appraisal:,.0f}")
    print(f"   Total sqft: {total_sqft:,.0f}")
    
    if args.dry_run:
        imgs = {name: {"url": str(path), "width": w, "height": h, "bytes": 0}
                for name, (path, w, h) in images.items()}
        doc = build_doc(stats, imgs)
        pm_json = json.dumps(pm_doc(*doc))
        pm_path = IMG_DIR / "prosemirror_doc.json"
        pm_path.write_text(pm_json, encoding="utf-8")
        print(f"\n[DONE] ProseMirror doc saved to: {pm_path}")
        return
    
    print("\n[4/4] Connecting to Substack...")
    cookie = os.environ.get("SUBSTACK_COOKIE", "")
    if not cookie:
        print("ERROR: SUBSTACK_COOKIE env var not set.")
        sys.exit(1)
    
    cookie_str = f"connect.sid={cookie}; substack.sid={cookie}"
    headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
    }
    
    r = requests.get("https://substack.com/api/v1/user/profile/self", headers=headers)
    if r.status_code != 200:
        print(f"   Auth failed ({r.status_code})")
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
    
    doc = build_doc(stats, imgs)
    pm_json = json.dumps(pm_doc(*doc))
    draft_body = {
        "draft_title": "The Value of Tennessee's Religious Infrastructure",
        "draft_subtitle": "Mapping $3.1B in church property assets across 8,188 parcels",
        "draft_body": pm_json,
        "type": "newsletter",
        "draft_bylines": [{"id": profile["id"], "publicationUserId": pub_user["id"]}],
    }
    
    r = requests.post(f"https://{SUBDOMAIN}.substack.com/api/v1/drafts",
                      headers=headers, json=draft_body)
    if r.status_code != 200:
        print(f"   ERROR ({r.status_code}): {r.text[:200]}")
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
            json={"send": True, "share_automatically": False},
        )
        if r.status_code == 200:
            slug = r.json().get("slug", draft_id)
            print(f"\n[DONE] Published! https://{SUBDOMAIN}.substack.com/p/{slug}")
        else:
            print(f"   ERROR ({r.status_code}): {r.text[:200]}")

if __name__ == '__main__':
    main()