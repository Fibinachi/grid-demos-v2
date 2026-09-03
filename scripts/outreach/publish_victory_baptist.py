#!/usr/bin/env python
"""
Publish the Victory Baptist / Funny Church Names post to Substack.

Usage:
    python scripts/outreach/publish_victory_baptist.py --dry-run   # Charts + PM JSON only
    python scripts/outreach/publish_victory_baptist.py --draft     # Save as draft on Substack
    python scripts/outreach/publish_victory_baptist.py --publish   # Publish & send

Auth: Set SUBSTACK_COOKIE env var.
"""

import os
import sys
import json
import base64
import sqlite3
from pathlib import Path
from datetime import datetime

import requests
import plotly.graph_objects as go
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

DB_PATH = Path(__file__).resolve().parents[2] / "churches.db"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "substack"
SUBDOMAIN = "gridkeeper"

# ═══════════════════════════════════════════════════════════════════
# ProseMirror builders (same as publish_substack.py)
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

def pm_ordered_list(*items):
    list_items = []
    for item in items:
        para = pm_para_rich(item) if isinstance(item, list) else pm_para(item)
        list_items.append({"type": "list_item", "content": [para]})
    return {"type": "ordered_list", "content": list_items}

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

# ═══════════════════════════════════════════════════════════════════
# Generate choropleth: Victory Baptist by state
# ═══════════════════════════════════════════════════════════════════

def make_victory_map(db_path: Path, img_dir: Path) -> dict:
    """Generate Victory Baptist choropleth, return {name: (path, width, height)}."""
    conn = sqlite3.connect(str(db_path))
    df = pd.read_sql_query("""
        SELECT state, COUNT(*) as cnt
        FROM churches
        WHERE country='US' AND name LIKE '%Victory Baptist%'
        GROUP BY state
        ORDER BY cnt DESC
    """, conn)
    conn.close()

    fig = go.Figure(data=go.Choropleth(
        locations=df["state"],
        z=df["cnt"],
        locationmode="USA-states",
        colorscale="Greens",
        colorbar_title="Victory Baptists",
        text=df.apply(lambda r: f"{r['state']}: {r['cnt']}", axis=1),
        hoverinfo="text",
        marker_line_color="white",
        marker_line_width=0.5,
    ))
    fig.update_layout(
        title=dict(
            text=f"<b>Victory Baptist Churches by State</b><br><sub>520 churches nationwide — GA leads with 47</sub>",
            font=dict(size=18),
        ),
        geo=dict(scope="usa", bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=60, b=0),
        font=dict(size=12),
    )

    path = img_dir / "victory_baptist_map.png"
    fig.write_image(str(path), width=1200, height=700, scale=2)
    return {"victory_map": (path, 2400, 1400)}

# ═══════════════════════════════════════════════════════════════════
# Upload images to Substack
# ═══════════════════════════════════════════════════════════════════

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
            print(f"   [WARN] {name} upload failed ({r.status_code}): {r.text[:100]}")
    return result

# ═══════════════════════════════════════════════════════════════════
# Build the ProseMirror document
# ═══════════════════════════════════════════════════════════════════

def build_doc(imgs: dict) -> list:
    def img(name):
        if name in imgs:
            i = imgs[name]
            return pm_image(i["url"], i["width"], i["height"], i["bytes"])
        return pm_para(f"[Image: {name}]")

    today = datetime.now().strftime("%B %d, %Y")

    doc = [
        pm_heading("🏆 The Church of Winning (and Losing): A Statistical Theology of Branding", 1),
        pm_heading("What 3.3 million American houses of worship tell us about who's winning, who's losing, and who's worshipping at the Church of the Dinosaur", 3),
        pm_para_rich([{"text": today, "italic": True},
                      {"text": " · Charles Prescott · GRID Project", "italic": True}]),
        pm_hr(),

        # ── I. The Victory Industrial Complex ──
        pm_heading("I. The Victory Industrial Complex"),
        pm_para("There are 520 Victory Baptist Churches in America. That's one Victory Baptist for roughly every 640,000 Americans — about as common as a Panda Express, but with more eternal consequences."),
        pm_para("But \"Victory\" as a brand isn't just Baptist. Across all denominations, 4,433 churches in the United States have \"Victory\" in their name. That's more than the number of Starbucks locations. Victory is a franchise."),

        img("victory_map"),

        pm_para("Only South Dakota and Wyoming have zero Victory Baptist churches. If you live in Rapid City and want to win one for the Lord, you'll have to drive to Montana — they have two."),
        pm_para("Twelve states have exactly one. The Lone Victors Club: Vermont, Utah, Nevada, New Jersey, New Hampshire, North Dakota, Maine, Hawaii, Delaware, DC, Connecticut, and Colorado. Every Sunday in Montpelier, exactly one congregation is singing about victory. The pressure must be immense."),

        # ── II. First Is Everywhere ──
        pm_heading("II. First Is Everywhere, Victory Is Special"),
        pm_para("For perspective: there are 15,787 \"First Baptist\" churches in America. That's 30 First Baptists for every one Victory Baptist. If church names were high school superlatives, \"First Baptist\" is \"Most Likely to Succeed\" and \"Victory Baptist\" is \"Best Personality.\""),
        pm_para("The ratio tells you something about Baptist psychology. \"First Baptist\" is a historical claim — we were here first. It's primogeniture, a deed, a legal filing. \"Victory Baptist\" is aspirational. You don't name your church Victory Baptist if things are going fine. You name it Victory Baptist because you're in a fight."),
        pm_para("And the Baptists aren't alone. Victory shows up everywhere:"),
        pm_bullet_list(
            [{"text": "Victory Outreach", "bold": True}, {"text": " — Palmdale, CA to Amarillo, TX (a whole network)"}],
            [{"text": "Victory Biker Church International", "bold": True}, {"text": " — Dallas, TX and Lennon, MI (apparently bikers need victory too)"}],
            [{"text": "Victory World Outreach", "bold": True}, {"text": " — Amarillo again (Amarillo really wants to win)"}],
            [{"text": "Victory Rock Fellowship", "bold": True}, {"text": " — Marengo, IL (victory rocks, literally)"}],
            [{"text": "Life of Victory Ministries", "bold": True}, {"text": " — Detroit, MI (even in Detroit, victory is possible)"}],
            [{"text": "Greater Victory Church COGIC", "bold": True}, {"text": " — Memphis, TN (not just victory, greater victory)"}],
        ),

        # ── III. The Losers ──
        pm_heading("III. The Losers: A Taxonomy of Defeat"),
        pm_para("Here's the thing about American religion: almost nobody names their church after losing."),
        pm_para("I searched for \"Loser,\" \"Defeat,\" \"Failure,\" \"Lost Cause,\" and \"Surrender\" in 3.3 million church names. The results were sparse."),
        pm_para("What I found instead was the grammar of anticipated victory through acknowledged struggle:"),
        pm_bullet_list(
            [{"text": "VICTORY OUT OF DEFEAT", "bold": True}, {"text": " — Atlanta, GA (the most honest church name in America)"}],
            [{"text": "NEVER DEFEATED MINISTRIES", "bold": True}, {"text": " — Hampton, VA (confident, perhaps overly so)"}],
            [{"text": "TOTAL SURRENDER EVANGELISTIC ASSOCIATION", "bold": True}, {"text": " — Arlington, TX (surrender as a flex)"}],
            [{"text": "SURRENDERED CLAY MINISTRIES", "bold": True}, {"text": " — Pittsburgh, PA (pottery metaphor, or just giving up?)"}],
            [{"text": "BROKEN NOT DEAD MINISTRIES", "bold": True}, {"text": " — Muscle Shoals, AL (the theological equivalent of \"I'm not dead yet!\")"}],
            [{"text": "GODS NOT DEAD FOUNDATION", "bold": True}, {"text": " — Scottsdale, AZ (based on the Newsboys song? Almost certainly)"}],
            [{"text": "LIFE OUT OF DEATH MINISTRIES", "bold": True}, {"text": " — Calabash, NC"}],
        ),
        pm_para("And then there's HELL NO MINISTRIES in St. Louis, Missouri. No further commentary needed. Sometimes the brand speaks for itself. (Verified: IRS 501(c)(3) filing. The federal government has officially recognized \"HELL NO\" as a tax-exempt religious organization.)"),

        # ── IV. Source Check ──
        pm_heading("IV. The Source-Check Interlude: What's Real and What's Database Garbage"),
        pm_para("Before we get to the truly unhinged names, a methodological note. GRID combines data from dozens of sources. The IRS tax-exempt organization database is rock-solid — if it's in there, someone filed paperwork with that name. But the Overture Maps dataset (from Meta/Microsoft/Amazon) occasionally has creative entries."),
        pm_para("I fact-checked the wildest names in this post. Here's the scorecard:"),
        pm_bullet_list(
            [{"text": "✅ HELL NO MINISTRIES", "bold": True}, {"text": " — IRS. The IRS said yes to Hell No."}],
            [{"text": "✅ LIVEJOY DEATHWITCH ABBEY", "bold": True}, {"text": " — IRS. Pagan abbey in Wake Forest, NC."}],
            [{"text": "✅ HOT METAL BRIDGE FAITH COMMUNITY", "bold": True}, {"text": " — IRS + UMC + 2 others. Real church on the Hot Metal Bridge, Pittsburgh."}],
            [{"text": "✅ HOLY COVENANT OF THE DRAGON", "bold": True}, {"text": " — IRS. New Age shrine in Fremont, CA."}],
            [{"text": "✅ CHURCH OF LUCIFER", "bold": True}, {"text": " — IRS. Madison, WI. 501(c)(3) and everything."}],
            [{"text": "✅ GRAND TEMPLE OF LUCIFER", "bold": True}, {"text": " — IRS. Birmingham, AL. Southern Luciferians."}],
            [{"text": "❌ FIRST INTERNATIONAL CHURCH OF THE DINOSAUR", "bold": True}, {"text": " — Overture. Links to a Zambian website (.co.zm). Fake."}],
            [{"text": "❌ CHURCH OF SURF, SAND AND ALCOHOL", "bold": True}, {"text": " — Overture. Links to a Spanish church site. Also fake."}],
            [{"text": "⚠️ DINOSAUR BIBLE FELLOWSHIP", "bold": True}, {"text": " — Overture. Town IS named Dinosaur, CO, but links to an Australian church. Suspicious."}],
        ),
        pm_para("The pattern: Overture Maps gave us the funniest fake names. The IRS gave us the funniest real ones. The government, for once, is the reliable narrator."),

        # ── V. Absolute Chaos ──
        pm_heading("V. The Taxonomy of Absolute Chaos (Verified Edition)"),
        
        pm_para_rich([{"text": "The Heavy Metal Churches", "bold": True}]),
        pm_para("There are at least seven heavy metal churches in America. The First Heavy Metal Church of Christ has four locations across three states (Ohio, Michigan, Virginia). This is not a joke. This is an emerging denomination."),
        pm_bullet_list(
            [{"text": "First Heavy Metal Church of Christ", "bold": True}, {"text": " — Englewood, OH; Dayton, OH; Pierson, MI; Vienna, VA"}],
            [{"text": "EXTREME UNITY - The Metal Church for Jesus", "bold": True}, {"text": " — Philadelphia, PA"}],
            [{"text": "Metal Church", "bold": True}, {"text": " — Burnt Cabins, PA"}],
        ),
        pm_para("7 heavy metal churches vs. 520 Victory Baptists. Heavy metal is 1.3% as popular as victory. That feels about right."),

        pm_para_rich([{"text": "The Dragon Churches", "bold": True}]),
        pm_para("HOLY COVENANT OF THE DRAGON in Fremont, California is a real IRS-registered organization. Listed as a New Age shrine. DRAGON SLAYER MINISTRIES (New Bern, NC), DRAGON SEAT MEDITATION CENTER (Memphis, TN), DRAGONS LEAP (San Francisco, CA), ANCIENT DRAGON ZEN GATE (Chicago, IL). Thirteen dragon-themed religious organizations in America. The Holy Covenant of the Dragon sounds like the final boss of a Dungeons & Dragons campaign, but it filed paperwork with the United States government."),

        pm_para_rich([{"text": "The Cowboy and Biker Churches", "bold": True}]),
        pm_para("COWBOY CHURCH OF ANCHORAGE (Anchorage, AK) — because when you think \"cowboy,\" you think Alaska. HAPPY TRAILS COWBOY CHURCH (Pelzer, SC). TRIPLE CROWN COWBOY CHURCH (Frankfort, KY). On the biker side: BROKEN CHAINS BIKER CHURCH (Taunton, MA and Burlington, NC), BARE BONES BIKER CHURCH (Spartanburg, SC), and VICTORY BIKER CHURCH INTERNATIONAL — because even bikers want to win."),

        pm_para_rich([{"text": "The Luciferians", "bold": True}]),
        pm_para("CHURCH OF LUCIFER in Madison, Wisconsin and GRAND TEMPLE OF LUCIFER in Birmingham, Alabama are both real IRS-registered organizations. Two Luciferian churches. One in a college town, one in the Deep South. The theological diversity of America is genuinely staggering."),

        pm_para_rich([{"text": "The Livejoy Deathwitch Abbey", "bold": True}]),
        pm_para("LIVEJOY DEATHWITCH ABBEY — Wake Forest, North Carolina. Registered with the IRS. Classification: Pagan. Landmark type: abbey. This is a real organization. Someone filled out Form 1023, wrote \"LIVEJOY DEATHWITCH ABBEY\" on it, mailed it to the IRS, and the IRS said \"approved.\" I present this without further comment."),

        # ── VI. Fire & Miracles ──
        pm_heading("VI. The Fire and Miracles Franchise"),
        pm_para("MOUNTAIN OF FIRE AND MIRACLES MINISTRIES (MFM) has 79 locations in the United States. That's more than Trader Joe's has in some states. They have branches in Brooklyn, Bronx, South Jersey, Indianapolis, Hyattsville, Pennsylvania, and at least 73 more."),
        pm_para("\"Mountain of Fire and Miracles\" is not a name — it's a promise. It's the theological equivalent of an action movie title. You know exactly what you're getting, and what you're getting is intense."),
        pm_para("Between Victory (4,433) and Fire & Miracles (79), American Christianity has fully embraced the blockbuster naming convention. Meanwhile, 15,787 churches went with \"First Baptist.\" Some brands are NVIDIA. Some brands are \"Dave's Computer Store.\" Both are valid."),

        # ── VII. Hot Metal Bridge ──
        pm_heading("VII. The Hot Metal Bridge to Nowhere"),
        pm_para("HOT METAL BRIDGE FAITH COMMUNITY in Pittsburgh is verified real by four independent data sources — IRS, United Methodist Church national directory, Overture Maps, and a church union scraper. They have a real website: hotmetalbridge.com."),
        pm_para("The church is named after the Hot Metal Bridge, a former railroad bridge that carried molten iron across the Monongahela River. It's the rare church name that is simultaneously metal as hell and historically accurate. Pittsburgh: where even the churches are industrial."),

        # ── VIII. Taxonomy ──
        pm_heading("VIII. What the Names Tell Us"),
        pm_para("American church naming follows a clear taxonomy:"),
        pm_ordered_list(
            [{"text": "The Historical Claim", "bold": True}, {"text": " (15,787 First Baptists) — \"We were here first\""}],
            [{"text": "The Aspirational Brand", "bold": True}, {"text": " (4,433 Victories, 79 Mountains of Fire) — \"We're going somewhere\""}],
            [{"text": "The Geographic Descriptor", "bold": True}, {"text": " (Buffalo, Surfside, Kings Highway) — \"We are here\""}],
            [{"text": "The Subculture Signal", "bold": True}, {"text": " (Cowboy, Biker, Heavy Metal, Skate) — \"We are YOUR kind of people\""}],
            [{"text": "The Absolutely Unhinged", "bold": True}, {"text": " (Deathwitch Abbey, Hell No Ministries, Holy Covenant of the Dragon) — \"We defy taxonomy\""}],
            [{"text": "The Database Artifact", "bold": True}, {"text": " (Surf Sand and Alcohol, First International Church of the Dinosaur) — \"We were invented by a geospatial data pipeline\""}],
        ),
        pm_para("Categories 5 and 6 are, objectively, the best categories. But only Category 5 is real."),

        # ── IX. Final Scoreboard ──
        pm_heading("IX. Final Scoreboard"),
        pm_bullet_list(
            [{"text": "Most churches named after winning: ", "bold": True}, {"text": "Victory Baptist — 520"}],
            [{"text": "Most churches named after being first: ", "bold": True}, {"text": "First Baptist — 15,787"}],
            [{"text": "Most action-movie church name: ", "bold": True}, {"text": "Mountain of Fire and Miracles — 79 locations"}],
            [{"text": "Most honest church name: ", "bold": True}, {"text": "Victory Out of Defeat — 1"}],
            [{"text": "Best church name the IRS approved: ", "bold": True}, {"text": "LIVEJOY DEATHWITCH ABBEY — 1"}],
            [{"text": "Best church name that doesn't exist: ", "bold": True}, {"text": "Church of Surf, Sand and Alcohol — 0"}],
            [{"text": "States with no Victory Baptists: ", "bold": True}, {"text": "South Dakota, Wyoming — 2"}],
            [{"text": "Heavy metal churches per capita in Ohio: ", "bold": True}, {"text": "Shockingly high — 4"}],
        ),

        pm_hr(),
        pm_para("Charles Prescott is the creator of GRID (Global Religious Infrastructure Database), which maps every church, mosque, temple, synagogue, gurdwara, and meetinghouse on Earth. He wrote this instead of doing actual work. All IRS-verified entries can be confirmed in the IRS Tax Exempt Organization Search. The Overture garbage entries are being flagged for cleanup because database hygiene matters, even when the garbage is funny."),
        pm_para("GRID is available on BigQuery at american-rel-infra.American_Religious_Infrastructure. Support this work at buymeacoffee.com/CharlesPrescott."),
    ]
    return doc

# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Publish Victory Baptist post to Substack")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--draft", action="store_true")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()

    if not any([args.dry_run, args.draft, args.publish]):
        print("Specify --dry-run, --draft, or --publish")
        sys.exit(1)

    # 1. Generate map
    print("[1/3] Generating Victory Baptist choropleth...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img_dir = OUTPUT_DIR / f"victory_baptist_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    img_dir.mkdir(parents=True, exist_ok=True)
    images = make_victory_map(DB_PATH, img_dir)

    if args.dry_run:
        imgs = {name: {"url": str(path), "width": w, "height": h, "bytes": 0}
                for name, (path, w, h) in images.items()}
        doc = build_doc(imgs)
        pm_json = json.dumps(pm_doc(*doc), indent=2)
        pm_path = img_dir / "prosemirror_doc.json"
        pm_path.write_text(pm_json, encoding="utf-8")
        print(f"\n[DONE] ProseMirror doc saved to: {pm_path}")
        print(f"   Map saved to: {img_dir}")
        return

    # 2. Auth
    print("\n[2/3] Connecting to Substack...")
    cookie = os.environ.get("SUBSTACK_COOKIE", "")
    if not cookie:
        print("ERROR: SUBSTACK_COOKIE env var not set. Get it from browser dev tools.")
        sys.exit(1)

    headers = {
        "Cookie": f"connect.sid={cookie}; substack.sid={cookie}",
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
    print(f"   Authenticated as {profile.get('handle')}")

    # Upload map
    print("   Uploading map...")
    imgs = upload_images(images, headers)

    # 3. Build & post
    print("\n[3/3] Creating draft...")
    doc = build_doc(imgs)
    pm_json = json.dumps(pm_doc(*doc))
    draft_body = {
        "draft_title": "🏆 The Church of Winning (and Losing): A Statistical Theology of Branding",
        "draft_subtitle": "520 Victory Baptists, 7 Heavy Metal churches, 1 Deathwitch Abbey — what 3.3M houses of worship tell us about branding, theology, and database garbage",
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
