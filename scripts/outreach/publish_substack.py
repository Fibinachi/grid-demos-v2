#!/usr/bin/env python
"""
GRID Substack Post Publisher
Generates a data-rich Substack post with Plotly maps/charts and publishes it
using Substack's ProseMirror-based draft API.

Usage:
    python scripts/outreach/publish_substack.py --dry-run  # Generate charts only
    python scripts/outreach/publish_substack.py --draft    # Save as draft
    python scripts/outreach/publish_substack.py --publish  # Publish & send

Auth: Set SUBSTACK_COOKIE env var to your connect.sid cookie string.
"""

import os
import sys
import json
import base64
import sqlite3
from pathlib import Path
from datetime import datetime

import requests
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DB_PATH = Path(__file__).resolve().parents[2] / "churches.db"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "substack"
SUBDOMAIN = "gridkeeper"


# ── ProseMirror builders ──────────────────────────────────────────────

def pm_doc(*content):
    """Root document node."""
    return {"type": "doc", "content": list(content)}

def pm_heading(text, level=2):
    return {"type": "heading", "attrs": {"level": level},
            "content": [{"type": "text", "text": text}]}

def pm_para(text):
    """Simple paragraph (plain text only)."""
    return {"type": "paragraph", "attrs": {"textAlign": None},
            "content": [{"type": "text", "text": text}]}

def pm_para_rich(parts):
    """Rich paragraph: parts = list of {"text": str, "bold": bool, "italic": bool}."""
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
    """Each item is a list of rich parts (see pm_para_rich)."""
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
    """Substack captionedImage block (image2 child, no caption)."""
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


# ── Stats ──────────────────────────────────────────────────────────────

def query_stats(db_path: Path) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    def one(q):
        cur.execute(q)
        return cur.fetchone()[0]

    s = {}
    s["total_global"] = one("SELECT COUNT(*) FROM churches")
    s["total_us"] = one("SELECT COUNT(*) FROM churches WHERE country='US'")
    s["with_coords"] = one("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    s["countries_covered"] = one("SELECT COUNT(DISTINCT country) FROM churches WHERE country IS NOT NULL AND country!='' AND length(country)=2")
    s["unique_taxonomies"] = one("SELECT COUNT(DISTINCT taxonomy_id) FROM churches WHERE taxonomy_id IS NOT NULL")
    s["unique_sources"] = one("SELECT COUNT(DISTINCT source) FROM churches WHERE source IS NOT NULL AND source!=''")
    s["db_size_mb"] = round(db_path.stat().st_size / (1024 * 1024), 0)
    s["provenance_entries"] = one("SELECT COUNT(*) FROM provenance_log")

    cur.execute("SELECT faith, COUNT(*) AS n FROM churches WHERE faith IS NOT NULL AND faith!='' GROUP BY faith ORDER BY n DESC")
    s["faiths"] = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT state, COUNT(*) AS n FROM churches WHERE country='US' AND state IS NOT NULL AND state!='' GROUP BY state ORDER BY n DESC")
    s["us_by_state"] = [dict(r) for r in cur.fetchall()]

    cur.execute("SELECT country, COUNT(*) AS n FROM churches WHERE country IS NOT NULL AND country!='' AND length(country)=2 GROUP BY country ORDER BY n DESC LIMIT 15")
    s["top_countries"] = [dict(r) for r in cur.fetchall()]

    s["us_pop"] = 334_000_000
    s["us_expected"] = s["us_pop"] // 300
    s["global_pop"] = 8_100_000_000
    s["global_expected"] = s["global_pop"] // 300
    s["india_estimated"] = 4_800_000

    conn.close()
    return s


# ── Figures ────────────────────────────────────────────────────────────

def make_figures(stats: dict, img_dir: Path) -> dict:
    images = {}  # {name: (path, width, height)}

    # 1. US choropleth
    df = pd.DataFrame(stats["us_by_state"])
    if not df.empty:
        fig = px.choropleth(df, locations="state", locationmode="USA-states",
                            color="n", scope="usa", color_continuous_scale="Blues",
                            title=f"Religious Buildings by State ({stats['total_us']:,} total in US)",
                            labels={"n": "Buildings", "state": "State"})
        fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), font=dict(size=12))
        path = img_dir / "us_choropleth.png"
        fig.write_image(str(path), width=1200, height=700, scale=2)
        images["us_map"] = (path, 2400, 1400)

    # 2. Faith treemap
    df = pd.DataFrame(stats["faiths"])
    if not df.empty:
        fig = px.treemap(df, path=["faith"], values="n", color="n",
                         color_continuous_scale="Viridis",
                         title=f"Global Faith Distribution ({stats['total_global']:,} total)")
        fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
        path = img_dir / "faith_treemap.png"
        fig.write_image(str(path), width=1200, height=700, scale=2)
        images["faith_treemap"] = (path, 2400, 1400)

    # 3. Top countries
    df = pd.DataFrame(stats["top_countries"]).head(12)
    if not df.empty:
        fig = px.bar(df, x="country", y="n", color="n", color_continuous_scale="Blues",
                     title="Top Countries by Religious Building Count",
                     labels={"n": "Buildings", "country": "Country"})
        fig.update_layout(margin=dict(l=0, r=0, t=40, b=80))
        path = img_dir / "top_countries.png"
        fig.write_image(str(path), width=1200, height=700, scale=2)
        images["top_countries"] = (path, 2400, 1400)

    # 4. US 300-theory
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Expected (300:1)", "GRID Actual"],
        y=[stats["us_expected"], stats["total_us"]],
        marker_color=["lightgray", "#1f77b4"],
        text=[f"{stats['us_expected']:,}", f"{stats['total_us']:,}"],
        textposition="auto",
    ))
    fig.update_layout(title="US: 300-People-Per-Church Theory vs. GRID Data",
                      yaxis_title="Religious Buildings", showlegend=False,
                      margin=dict(l=0, r=0, t=50, b=0))
    path = img_dir / "us_300_theory.png"
    fig.write_image(str(path), width=900, height=500, scale=2)
    images["us_300_theory"] = (path, 1800, 1000)

    # 5. Global 300-theory
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Expected (300:1)", "GRID Actual", "GRID + India estimate"],
        y=[stats["global_expected"], stats["total_global"],
           stats["total_global"] + stats["india_estimated"]],
        marker_color=["lightgray", "#1f77b4", "#ff7f0e"],
        text=[f"{stats['global_expected']:,}", f"{stats['total_global']:,}",
              f"{stats['total_global'] + stats['india_estimated']:,}"],
        textposition="auto",
    ))
    fig.update_layout(title="Global: 300-People-Per-Church Theory — The India Gap",
                      yaxis_title="Religious Buildings", showlegend=False,
                      margin=dict(l=0, r=0, t=50, b=0))
    path = img_dir / "global_300_theory.png"
    fig.write_image(str(path), width=900, height=500, scale=2)
    images["global_300_theory"] = (path, 1800, 1000)

    return images


# ── Upload images to Substack ──────────────────────────────────────────

def upload_images(images: dict, headers: dict) -> dict:
    """Upload images, return {name: {url, width, height, bytes}}."""
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
    """Build the ProseMirror doc content as a list of top-level nodes."""
    today = datetime.now().strftime("%B %d, %Y")
    faith_list = ", ".join(f"{f['faith']}: {f['n']:,}" for f in stats["faiths"][:6])

    def img(name):
        """Return a pm_image node if the image was uploaded, else a placeholder para."""
        if name in imgs:
            i = imgs[name]
            return pm_image(i["url"], i["width"], i["height"], i["bytes"])
        return pm_para(f"[Image: {name}]")

    doc = [
        pm_heading("How Many Churches Are in America? — The Question That Started GRID", 1),
        pm_para_rich([{"text": today, "italic": True},
                      {"text": " · Charles Prescott · GRID Project", "italic": True}]),
        pm_hr(),

        pm_heading("The Question Nobody Could Answer"),
        pm_para("In 2024, I asked a deceptively simple question: How many churches are there in the United States?"),
        pm_para("Not \"how many Christians.\" Not \"how many congregations.\" Not \"how many denominations.\""),
        pm_para("How many buildings — physical houses of worship where people gather to pray, sing, marry, mourn, and organize their communities?"),
        pm_para_rich([{"text": "The best answers available were embarrassing:", "bold": False}]),
        pm_bullet_list(
            [{"text": "~350,000", "bold": True}, {"text": " — from the 2010 U.S. Religion Census, already 14 years out of date, counting \"congregations\" not buildings, missing vast swaths of independent and non-Christian worship spaces."}],
            [{"text": "~180,000", "bold": True}, {"text": " — from the IRS Business Master File of 501(c)(3) religious organizations. But churches don't have to file for tax exemption, and many — especially small rural churches, storefront mosques, and informal temples — don't."}],
            [{"text": "\"Nobody knows\"", "bold": True}, {"text": " — the honest answer from every researcher I asked."}],
        ),
        pm_para("This wasn't just a trivia gap. Religious buildings are critical social infrastructure: polling places, disaster shelters, food pantries, community centers, and cultural landmarks. We have better maps of every McDonald's in America than we do of our houses of worship."),
        pm_para("So I started building one."),

        pm_heading("The 300-People-Per-Church Theory"),
        pm_para("Before GRID had any data, I needed a way to estimate how many religious buildings should exist — to know when the database was approaching completeness."),
        pm_para("The logic is grounded in the economics of religious labor:"),
        pm_ordered_list(
            [{"text": "A full-time religious professional (pastor, priest, imam, rabbi) needs to make a living."}],
            [{"text": "That requires support from approximately ", "bold": False},
             {"text": "three families", "bold": True},
             {"text": " with sufficient disposable wealth to tithe or donate."}],
            [{"text": "Sustaining three such families requires a broader community of roughly ", "bold": False},
             {"text": "300 people", "bold": True},
             {"text": " (accounting for children, the elderly, and those who attend but don't contribute financially)."}],
        ),
        pm_para("So the rule of thumb: 1 religious building per 300 people."),
        pm_para_rich([
            {"text": f"334,000,000 ÷ 300 ≈ {stats['us_expected']:,} expected religious buildings in the US", "bold": True}
        ]),
        img("us_300_theory"),
        pm_para_rich([
            {"text": f"8,100,000,000 ÷ 300 ≈ {stats['global_expected']:,} expected religious buildings worldwide", "bold": True}
        ]),
        img("global_300_theory"),

        pm_heading("What GRID Found"),
        pm_para(f"After 18 months of data collection — integrating 25+ sources from government registries, open data portals, Wikidata, OpenStreetMap, and denominational directories — here's what the Global Religious Infrastructure Database contains as of {today}:"),
        pm_heading("The United States", 3),
        pm_para_rich([{"text": f"{stats['total_us']:,} religious buildings", "bold": True}]),
        pm_para("That's remarkably close to the 300:1 prediction. The model held."),
        img("us_map"),
        pm_heading("Globally", 3),
        pm_para_rich([{"text": f"{stats['total_global']:,} religious buildings", "bold": True}]),
        pm_para(f"Across {stats['countries_covered']} countries and territories. But the 300:1 model says there should be ~{stats['global_expected']:,}. The gap is enormous — and it has a name: India."),
        pm_para(f"India alone, with 1.45 billion people and an estimated {stats['india_estimated']:,} religious sites, accounts for most of the shortfall. Our 225,873 Indian entries represent roughly 4.7% of the country's actual religious infrastructure."),
        img("faith_treemap"),
        img("top_countries"),

        pm_hr(),
        pm_heading("By The Numbers"),
        pm_para_rich([{"text": f"Faith distribution (global): {faith_list}"}]),
        pm_bullet_list(
            [{"text": "Records with GPS coordinates: ", "bold": True}, {"text": f"{stats['with_coords']:,} ({stats['with_coords']/stats['total_global']*100:.1f}%)"}],
            [{"text": "Unique taxonomy nodes: ", "bold": True}, {"text": str(stats['unique_taxonomies'])}],
            [{"text": "Data sources: ", "bold": True}, {"text": f"{stats['unique_sources']} distinct sources"}],
            [{"text": "Countries covered: ", "bold": True}, {"text": str(stats['countries_covered'])}],
            [{"text": "Database size: ", "bold": True}, {"text": f"{stats['db_size_mb']:.0f} MB SQLite"}],
            [{"text": "Provenance operations: ", "bold": True}, {"text": f"{stats['provenance_entries']:,}"}],
        ),

        pm_hr(),
        pm_heading("How GRID Was Built"),
        pm_para("GRID began as a simple IRS data import and grew into something much larger. The pipeline now ingests from:"),
        pm_bullet_list(
            [{"text": "Government registries: ", "bold": True}, {"text": "IRS Business Master File (US), Canada Revenue Agency, Ireland Charities Register"}],
            [{"text": "Open knowledge: ", "bold": True}, {"text": "Wikidata (1.35M records), OpenStreetMap (1.3M)"}],
            [{"text": "Commercial data: ", "bold": True}, {"text": "Overture Maps (229K)"}],
            [{"text": "National portals: ", "bold": True}, {"text": "Bahrain, Korea, Aragon (Spain), Tamil Nadu (India), Cape Town (South Africa)"}],
            [{"text": "Municipal data: ", "bold": True}, {"text": "Boston Property Assessment, Dublin Places of Worship"}],
            [{"text": "Denominational directories: ", "bold": True}, {"text": "SBC, Catholic dioceses, Chabad, Masstimes, LDS"}],
            [{"text": "Archaeological gazetteers: ", "bold": True}, {"text": "Pleiades (1,702 ancient sites)"}],
        ),
        pm_para("Every record is classified through the CFTLM taxonomy (Civilization-Faith-Tradition-Legacy-Movement), a 600-node hierarchy providing consistent depth across all faiths. AI-assisted verification via the DeepSeek API has reviewed 37,000+ edge cases."),
        pm_para(f"Every modification is logged. {stats['provenance_entries']:,} provenance entries record what changed, when, and why."),

        pm_hr(),
        pm_heading("What This Means"),
        pm_para("The 300-people-per-church theory isn't just an estimation tool — it's a validation framework. When the U.S. data converged on 1.07 million buildings against a prediction of 1.11 million, it told us the American dataset is approaching completeness. When the global data showed 3.5 million against 27 million expected, it told us exactly where the gaps are."),
        pm_para("GRID is not finished. But for the first time, \"how many churches are in America?\" has an answer grounded in data, not guesses."),
        pm_para("And that's just the beginning."),
        pm_hr(),
        pm_para("GRID (Global Religious Infrastructure Database) is available on BigQuery at american-rel-infra.American_Religious_Infrastructure. The full SQLite database is available to researchers and partner organizations. Contact: charles.prescott@gridproject.org. Support this work at buymeacoffee.com/CharlesPrescott."),
    ]

    return doc


# ── Main ───────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Publish a GRID report to Substack")
    parser.add_argument("--dry-run", action="store_true", help="Generate charts only, save PM doc to file")
    parser.add_argument("--draft", action="store_true", help="Save as draft on Substack")
    parser.add_argument("--publish", action="store_true", help="Publish and send to subscribers")
    args = parser.parse_args()

    if not any([args.dry_run, args.draft, args.publish]):
        print("Specify --dry-run, --draft, or --publish")
        sys.exit(1)

    # 1. Stats
    print("[1/4] Querying database...")
    stats = query_stats(DB_PATH)
    print(f"   {stats['total_global']:,} total | {stats['total_us']:,} US | {stats['countries_covered']} countries")

    # 2. Figures
    print("\n[2/4] Generating visualizations...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img_dir = OUTPUT_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    img_dir.mkdir(parents=True, exist_ok=True)
    images = make_figures(stats, img_dir)

    if args.dry_run:
        # Build doc with placeholder image refs (no upload)
        imgs = {name: {"url": str(path), "width": w, "height": h, "bytes": 0}
                for name, (path, w, h) in images.items()}
        doc = build_doc(stats, imgs)
        pm_json = json.dumps(pm_doc(*doc))
        pm_path = img_dir / "prosemirror_doc.json"
        pm_path.write_text(pm_json, encoding="utf-8")
        print(f"\n[DONE] ProseMirror doc saved to: {pm_path}")
        print(f"   Images in: {img_dir}")
        return

    # 3. Authenticate + upload images
    print("\n[3/4] Connecting to Substack...")
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
        print(f"   Auth failed ({r.status_code}): {r.text[:200]}")
        sys.exit(1)
    profile = r.json()
    pub_user = next((pu for pu in profile.get("publicationUsers", [])
                     if pu["publication"]["subdomain"] == SUBDOMAIN), None)
    if not pub_user:
        print(f"   No publication found: {SUBDOMAIN}")
        sys.exit(1)
    print(f"   Authenticated as {profile.get('handle')} (id={profile['id']})")

    # Upload images
    print("   Uploading images...")
    imgs = upload_images(images, headers)

    # 4. Build & post
    print("\n[4/4] Creating draft...")
    doc = build_doc(stats, imgs)
    pm_json = json.dumps(pm_doc(*doc))
    draft_body = {
        "draft_title": "How Many Churches Are in America? — The Question That Started GRID",
        "draft_subtitle": "The 300-people-per-church theory, the origin of GRID, and what 3.5M religious buildings tell us",
        "draft_body": pm_json,
        "type": "newsletter",
        "draft_bylines": [{"id": profile["id"], "publicationUserId": pub_user["id"]}],
    }

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
            json={"send": True, "share_automatically": False},
        )
        if r.status_code == 200:
            slug = r.json().get("slug", draft_id)
            print(f"\n[DONE] Published! https://{SUBDOMAIN}.substack.com/p/{slug}")
        else:
            print(f"   ERROR ({r.status_code}): {r.text[:200]}")


if __name__ == "__main__":
    main()
