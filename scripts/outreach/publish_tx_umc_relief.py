#!/usr/bin/env python
"""
Publish TX Hill Country UMC Relief Hub analysis to Substack.

Usage:
    python scripts/outreach/publish_tx_umc_relief.py --dry-run   # Charts + PM JSON only
    python scripts/outreach/publish_tx_umc_relief.py --draft     # Save as draft on Substack
    python scripts/outreach/publish_tx_umc_relief.py --publish   # Publish & send

Auth: Set SUBSTACK_COOKIE env var.
"""

import os
import sys
import json
import base64
import sqlite3
import urllib.parse
from pathlib import Path
from datetime import datetime

import requests
import pandas as pd

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

# ═══════════════════════════════════════════════════════════════════
# Config
# ═══════════════════════════════════════════════════════════════════
DB_PATH = Path(__file__).resolve().parents[2] / "churches.db"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "substack"
MAP_HTML = Path(__file__).resolve().parents[2] / "outputs" / "tx_umc_relief" / "tx_umc_relief_map.html"
SUBDOMAIN = "gridkeeper"
TIMESTAMP = datetime.now().strftime("%Y-%m-%d %H:%M")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ═══════════════════════════════════════════════════════════════════
# ProseMirror builders
# ═══════════════════════════════════════════════════════════════════

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
                "src": src, "srcNoWatermark": None, "fullscreen": None,
                "imageSize": None, "width": width, "height": height,
                "resizeWidth": None, "bytes": bts, "alt": None,
                "title": None, "type": "image/png", "href": None,
                "belowTheFold": False, "topImage": False, "internalRedirect": None,
            }
        }]
    }

# ═══════════════════════════════════════════════════════════════════
# Auth
# ═══════════════════════════════════════════════════════════════════

def get_auth():
    decoded = urllib.parse.unquote(os.environ.get("SUBSTACK_COOKIE", ""))
    cookie = f"connect.sid={decoded}; substack.sid={decoded}"
    headers = {"Cookie": cookie, "User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}
    return headers, cookie

def check_auth(headers):
    r = requests.get("https://substack.com/api/v1/user/profile/self", headers=headers)
    if r.status_code != 200:
        print(f"Auth failed: {r.status_code} {r.text[:200]}")
        sys.exit(1)
    profile = r.json()
    pub = next(pu for pu in profile["publicationUsers"] if pu["publication"]["subdomain"] == SUBDOMAIN)
    print(f"Authenticated: {profile['handle']} (id={profile['id']})")
    return profile, pub["id"]

# ═══════════════════════════════════════════════════════════════════
# Screenshot map
# ═══════════════════════════════════════════════════════════════════

def screenshot_map(html_path, png_path):
    """Capture map screenshot via Playwright."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"file:///{html_path}")
        page.wait_for_timeout(3000)
        page.screenshot(path=png_path, full_page=True)
        browser.close()
    print(f"  Screenshot saved: {png_path}")

# ═══════════════════════════════════════════════════════════════════
# Upload image
# ═══════════════════════════════════════════════════════════════════

def upload_image(png_path, headers):
    with open(png_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    r = requests.post(
        f"https://{SUBDOMAIN}.substack.com/api/v1/image",
        headers=headers,
        json={"image": f"data:image/png;base64,{b64}"}
    )
    if r.status_code == 200:
        d = r.json()
        print(f"  Uploaded: {d['url'][:80]}...")
        return {
            "url": d["url"],
            "width": d.get("imageWidth", 1200),
            "height": d.get("imageHeight", 800),
            "bytes": d.get("bytes", 0),
        }
    else:
        print(f"  Upload failed: {r.status_code} {r.text[:200]}")
        return None

# ═══════════════════════════════════════════════════════════════════
# Create draft
# ═══════════════════════════════════════════════════════════════════

def create_draft(title, subtitle, doc_parts, headers, profile, pub_user_id):
    body = {
        "draft_title": title,
        "draft_subtitle": subtitle,
        "draft_body": json.dumps(pm_doc(*doc_parts)),
        "type": "newsletter",
        "draft_bylines": [{"id": profile["id"], "publicationUserId": pub_user_id}],
    }
    r = requests.post(f"https://{SUBDOMAIN}.substack.com/api/v1/drafts", headers=headers, json=body)
    if r.status_code == 200:
        did = r.json()["id"]
        print(f"  Draft created: https://{SUBDOMAIN}.substack.com/publish/post/{did}")
        return did
    else:
        print(f"  Draft failed: {r.status_code} {r.text[:300]}")
        return None

# ═══════════════════════════════════════════════════════════════════
# Data queries
# ═══════════════════════════════════════════════════════════════════

def load_umc_data():
    """Load UMC relief hub data from CSV generated by map_tx_umc_relief.py"""
    csv_path = Path(__file__).resolve().parents[2] / "outputs" / "tx_umc_relief" / "umc_relief_hubs.csv"
    if not csv_path.exists():
        print(f"ERROR: CSV not found at {csv_path}. Run scripts/aid/map_tx_umc_relief.py first.")
        sys.exit(1)
    df = pd.read_csv(csv_path)
    df = df.sort_values("relief_score", ascending=False)
    return df

# ═══════════════════════════════════════════════════════════════════
# Build post content
# ═══════════════════════════════════════════════════════════════════

def build_post(umc, map_img):
    """Build the full ProseMirror document for the Substack post."""

    # Load CSV data
    primary = umc[umc["hub_tier"] == "primary_hub"]
    secondary = umc[umc["hub_tier"] == "secondary_hub"]
    at_risk = umc[umc["at_risk"] == True]
    total = len(umc)
    with_contact = int(umc["has_any_contact"].sum())
    below_5m = int((umc["height_above_drainage"] < 5).sum())

    doc = []

    # ── Title & Lead ──
    doc.append(pm_heading("Texas Hill Country Flash Flood: Where UMC Relief Hubs Can Set Up Safely", level=1))
    doc.append(pm_para_rich([
        {"text": "July 17, 2026", "bold": True},
        {"text": " | Charles Prescott, GRID Project"},
    ]))

    doc.append(pm_hr())

    doc.append(pm_para(
        "At 8:00 AM yesterday, the Guadalupe River at Comfort, Texas sat at 5 feet. "
        "By 10:00 AM, it hit 35 feet — a 30-foot vertical rise in two hours. "
        "Flash Flood Emergencies lit up Kerr and Kendall counties. Sirens blared. "
        "Summer camps evacuated. At least one person is dead."
    ))
    doc.append(pm_para(
        "This is the same stretch of Texas Hill Country where 130 people died in the "
        "July 4, 2025 floods, almost exactly one year ago. The question now — as the "
        "flood wave moves downstream toward New Braunfels and beyond — is: "
        "where can relief organizations safely stage?"
    ))
    doc.append(pm_para(
        "I run the GRID Project (Global Religious Infrastructure Database), which maps "
        "every church, mosque, temple, and synagogue on Earth — 3.3 million and counting. "
        "For this analysis, I focused on the denomination best positioned to respond: "
        "the United Methodist Church, whose relief arm UMCOR is one of the most "
        "experienced disaster response organizations in the country."
    ))
    doc.append(pm_para(
        f"There are {total} United Methodist churches across the 12 affected counties. "
        f"I scored every one using USGS satellite elevation data, FEMA floodplain maps, "
        f"and contact availability. Here's what I found."
    ))

    # ── Map image ──
    if map_img:
        doc.append(pm_heading("Interactive Relief Hub Map", level=2))
        doc.append(pm_image(map_img["url"], map_img["width"], map_img["height"], map_img["bytes"]))
        doc.append(pm_para_rich([
            {"text": "Green = Primary/Secondary hubs. Yellow = Support sites. "
                     "Red labels = directly flooded counties. "
                     "Full interactive map available in the dataset.",
             "italic": True},
        ]))

    # ── The Two Safe Havens ──
    doc.append(pm_heading("The Two Safe Havens", level=2))
    doc.append(pm_para(
        "Only two UMC churches scored as Primary Relief Hubs — sites with both "
        "high elevation and significant clearance above local drainage."
    ))

    for _, r in primary.iterrows():
        elev_ft = r["ned_elev_m"] * 3.28084
        drain_ft = r["height_above_drainage"] * 3.28084
        contact_str = ""
        if r["has_website"]: contact_str += "website, "
        if r["has_phone"]: contact_str += "phone, "
        if r["has_email"]: contact_str += "email, "
        contact_str = contact_str.rstrip(", ") or "no digital contact"

        doc.append(pm_heading(f"{r['name']} — {r['city']}, {r['county']} County", level=3))
        doc.append(pm_bullet_list(
            [{"text": f"Elevation: {r['ned_elev_m']:.0f}m ({elev_ft:.0f} ft)", "bold": True}],
            [{"text": f"Height above local drainage: +{r['height_above_drainage']:.0f}m (+{drain_ft:.0f} ft)", "bold": True}],
            [{"text": f"Contact: {contact_str}"}],
            [{"text": f"Relief Score: {r['relief_score']:.0f}/51"}],
        ))

    # ── Secondary Hubs ──
    doc.append(pm_heading("Seven Secondary Hubs", level=2))
    doc.append(pm_para(
        "These churches scored well but have vulnerabilities — typically lower "
        "clearance above drainage or proximity to the river corridor:"
    ))

    # Build text list for secondary hubs
    for _, r in secondary.iterrows():
        contact = ""
        if r["has_website"]: contact += " [W]"
        if r["has_phone"]: contact += " [P]"
        if r["has_email"]: contact += " [E]"
        if not contact: contact = " [no contact]"
        drain = r["height_above_drainage"]
        warn = " [LOW CLEARANCE]" if drain < 3 else ""
        doc.append(pm_para(
            f"[{r['relief_score']:.0f}] {r['name'][:45]} | {r['city']}, {r['county']} | "
            f"{r['ned_elev_m']:.0f}m +{drain:.0f}m drainage{warn} | {contact}"
        ))

    # ── Gaddis UMC at Ground Zero ──
    doc.append(pm_heading("Gaddis UMC in Comfort: Ground Zero", level=2))
    gaddis = umc[umc["name"].str.contains("GADDIS", case=False, na=False)]
    if len(gaddis) > 0:
        r = gaddis.iloc[0]
        doc.append(pm_para(
            f"Gaddis United Methodist Church is in Comfort, Texas — the town where "
            f"the Guadalupe gauge recorded the 30-foot rise. Gaddis sits at {r['ned_elev_m']:.0f}m "
            f"elevation with only +{r['height_above_drainage']:.0f}m of clearance above local "
            f"drainage. This illustrates the methodology: a church can be at high absolute "
            f"elevation yet still be vulnerable if it's in a low spot relative to immediate "
            f"surroundings. The Guadalupe doesn't care about sea level; it cares about "
            f"the lowest path downhill."
        ))

    # ── At-Risk ──
    doc.append(pm_heading(f"At-Risk: {below_5m} of {total} Churches Within 5 Meters of Drainage", level=2))
    doc.append(pm_para(
        f"The most sobering number: {below_5m} of the {total} UMC churches are within "
        f"5 meters (16 feet) of their local drainage elevation. The flood produced "
        f"a 9-meter (30-foot) surge. If any of these churches sit on a tributary that "
        f"feeds the Guadalupe or Pedernales, they're in the danger zone."
    ))
    doc.append(pm_para(
        "The eastern counties — Hays, Comal, Medina — are particularly exposed. "
        "Churches in San Marcos (188m), New Braunfels (195m), Devine (196m), and "
        "Kyle (220m) sit at the lowest absolute elevations and have minimal drainage "
        "clearance. As the flood wave moves downstream, these are the churches that "
        "will feel it next."
    ))

    # ── The Contact Problem ──
    doc.append(pm_heading("The Contact Problem", level=2))
    doc.append(pm_para(
        f"Only {with_contact} of {total} UMC churches have any contact information "
        f"in our database. The churches that are physically safest (Utopia, Mountain Home) "
        f"have the thinnest digital footprints. This is a structural problem with rural "
        f"church data — the churches most useful in a disaster are the hardest to reach "
        f"electronically."
    ))

    # ── Methodology ──
    doc.append(pm_heading("Methodology", level=2))
    doc.append(pm_bullet_list(
        [{"text": "Elevation: ", "bold": True}, {"text": "USGS National Elevation Dataset (NED) 10-meter resolution via OpenTopoData API. Approximately ±2.4m vertical accuracy at 95% confidence."}],
        [{"text": "Local drainage: ", "bold": True}, {"text": "For each church, we sampled elevation at the building point plus four cardinal offset points at 100m distance. Height above drainage = building elevation minus minimum of the five sample points."}],
        [{"text": "Relief Hub Score: ", "bold": True}, {"text": "Composite of 8 components — height above drainage (10 pts), FEMA floodplain status (10), website (5), phone (3), email (3), zone urgency (5), building type (5), absolute elevation (10). Max 51."}],
        [{"text": "Data: ", "bold": True}, {"text": "GRID Project churches.db, 3.3M records. Full dataset and interactive map in outputs/tx_umc_relief/."}],
    ))

    # ── Limitations ──
    doc.append(pm_heading("Limitations", level=2))
    doc.append(pm_bullet_list(
        [{"text": "Elevation is point-based, not terrain-based. ", "bold": True}, {"text": "The 100m sampling may miss closer drainage features like culverts or small washes."}],
        [{"text": "Distance to river not modeled. ", "bold": True}, {"text": "A church at +2m drainage but 10km from the Guadalupe may be perfectly safe."}],
        [{"text": "FEMA maps don't capture 30-foot flash surges. ", "bold": True}, {"text": "None of the 38 churches are in FEMA 100-year floodplains — yesterday's event was beyond probable."}],
        [{"text": "Building capacity unknown. ", "bold": True}, {"text": "No data on square footage, seating, parking, kitchens, or generators."}],
        [{"text": "Contact data may be stale. ", "bold": True}, {"text": "Aggregated from public sources; phone/email may have changed."}],
        [{"text": "Road access not modeled. ", "bold": True}, {"text": "A safe building is useless if the road to it is underwater."}],
        [{"text": "NED 10m accuracy. ", "bold": True}, {"text": "±2.4m vertical uncertainty at 95% confidence. Drainage values below 3m should be treated cautiously."}],
        [{"text": "No ground truth. ", "bold": True}, {"text": "All results from remote sensing and database queries. No on-site verification."}],
    ))

    # ── Disclaimer ──
    doc.append(pm_heading("Disclaimer", level=2))
    doc.append(pm_para_rich([
        {"text": "This analysis is for informational and humanitarian coordination purposes only. It does not constitute professional engineering, hydrological, or emergency management advice.", "bold": True},
    ]))
    doc.append(pm_para(
        "The findings are based on automated analysis of satellite-derived elevation data, "
        "publicly available contact information, and FEMA flood hazard maps. No on-site "
        "inspection or ground-truth verification has been performed. Building conditions, "
        "structural integrity, actual flood damage, road accessibility, and real-time "
        "hazard conditions are unknown."
    ))
    doc.append(pm_para(
        "Relief organizations should verify building conditions through on-site assessment, "
        "consult local emergency management for current road closures, and confirm contact "
        "information independently. In an emergency, follow instructions from local "
        "authorities and emergency services — not this document."
    ))

    doc.append(pm_hr())

    # ── Footer ──
    doc.append(pm_para_rich([
        {"text": "Charles Prescott", "bold": True},
        {"text": " is the creator of the GRID Project (Global Religious Infrastructure Database). "
                 "He maps churches for disaster response. "},
    ]))
    doc.append(pm_para("Contact: charlesaprescott@outlook.com"))
    doc.append(pm_para("Support: buymeacoffee.com/CharlesPrescott"))
    doc.append(pm_para_rich([
        {"text": "Data & code: ", "bold": True},
        {"text": "outputs/tx_umc_relief/ (CSV + interactive map) | scripts/aid/map_tx_umc_relief.py"},
    ]))

    return doc

# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    dry_run = "--dry-run" in sys.argv
    is_draft = "--draft" in sys.argv
    is_publish = "--publish" in sys.argv

    print("=" * 70)
    print("TX HILL COUNTRY UMC RELIEF — SUBSTACK PUBLISHER")
    print(f"Mode: {'DRY RUN' if dry_run else 'DRAFT' if is_draft else 'PUBLISH' if is_publish else 'DRY RUN (default)'}")
    print("=" * 70)

    # 1. Load data
    print("\n[1/5] Loading UMC relief hub data...")
    umc = load_umc_data()
    print(f"  {len(umc)} churches loaded")
    primary_n = len(umc[umc["hub_tier"] == "primary_hub"])
    secondary_n = len(umc[umc["hub_tier"] == "secondary_hub"])
    print(f"  Primary hubs: {primary_n}, Secondary: {secondary_n}")

    # 2. Screenshot map
    print("\n[2/5] Capturing map screenshot...")
    map_png = OUTPUT_DIR / "tx_umc_relief_map.png"
    if not map_png.exists() or not dry_run:
        screenshot_map(str(MAP_HTML), str(map_png))

    # 3. Auth
    print("\n[3/5] Authenticating...")
    headers, cookie = get_auth()
    profile, pub_user_id = check_auth(headers)

    # 4. Upload image (skip in dry run if we don't need auth)
    map_img = None
    if not dry_run:
        print("\n[4/5] Uploading map image...")
        map_img = upload_image(str(map_png), headers)
    else:
        print("\n[4/5] DRY RUN — skipping image upload")
        map_img = {"url": "PLACEHOLDER_URL", "width": 1200, "height": 800, "bytes": 0}

    # 5. Build & post
    print("\n[5/5] Building post content...")
    doc = build_post(umc, map_img)

    # Save PM JSON for dry run
    pm_json_path = OUTPUT_DIR / "tx_umc_relief_pm.json"
    pm_body = pm_doc(*doc)
    with open(pm_json_path, "w", encoding="utf-8") as f:
        json.dump(pm_body, f, indent=2, ensure_ascii=False)
    print(f"  ProseMirror JSON saved: {pm_json_path}")

    if dry_run:
        print("\n  DRY RUN COMPLETE. PM JSON saved. Run with --draft to post to Substack.")
        return

    # Create draft
    title = "Texas Hill Country Flash Flood: Where UMC Relief Hubs Can Set Up Safely"
    subtitle = (
        f"Satellite elevation analysis of 38 United Methodist churches across 12 affected counties. "
        f"Only 2 primary hubs found. 28 of 38 within 5 meters of local drainage. "
        f"UMCOR-targeted relief coordination data."
    )
    did = create_draft(title, subtitle, doc, headers, profile, pub_user_id)

    if did and is_publish:
        print(f"\n  Draft ready. To publish: open https://{SUBDOMAIN}.substack.com/publish/post/{did}")
        print("  (Manual publish via Substack UI recommended for review)")

if __name__ == "__main__":
    main()
