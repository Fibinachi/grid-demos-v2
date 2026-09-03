#!/usr/bin/env python
"""Publish the Latino Catholic Shift post to Substack."""

import os, sys, json, base64
from pathlib import Path
from datetime import datetime
import requests, sqlite3
import plotly.express as px
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SUBDOMAIN = "gridkeeper"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "outputs" / "substack"
DB_PATH = Path(__file__).resolve().parents[2] / "churches.db"

# ── ProseMirror helpers ────────────────────────────────────────────────

def pm(*content):
    return {"type": "doc", "content": list(content)}

def h(text, level=2):
    return {"type": "heading", "attrs": {"level": level},
            "content": [{"type": "text", "text": text}]}

def p(text):
    return {"type": "paragraph", "attrs": {"textAlign": None},
            "content": [{"type": "text", "text": text}]}

def pr(parts):
    """Rich paragraph: parts=[{text,bold,italic}, ...]"""
    content = []
    for part in parts:
        marks = []
        if part.get("bold"):
            marks.append({"type": "bold"})
        if part.get("italic"):
            marks.append({"type": "italic"})
        node = {"type": "text", "text": part["text"]}
        if marks:
            node["marks"] = marks
        content.append(node)
    return {"type": "paragraph", "attrs": {"textAlign": None}, "content": content}

def hr():
    return {"type": "horizontal_rule"}

def bul(*items):
    lis = []
    for item in items:
        lis.append({"type": "list_item", "content": [
            pr(item) if isinstance(item, list) else p(item)
        ]})
    return {"type": "bullet_list", "content": lis}

def img(src, w, h, bts):
    return {
        "type": "captionedImage",
        "content": [{
            "type": "image2",
            "attrs": {
                "src": src, "srcNoWatermark": None, "fullscreen": None,
                "imageSize": None, "width": w, "height": h,
                "resizeWidth": None, "bytes": bts, "alt": None,
                "title": None, "type": "image/png", "href": None,
                "belowTheFold": False, "topImage": False, "internalRedirect": None,
            }
        }]
    }


# ── Charts ─────────────────────────────────────────────────────────────

def make_charts(img_dir: Path) -> dict:
    """Generate Catholic-focused charts, return {name: (path, w, h)}."""
    images = {}

    conn = sqlite3.connect(str(DB_PATH))
    # Catholic by state
    df = pd.read_sql_query(
        "SELECT state, COUNT(*) as n FROM churches WHERE country='US' AND taxonomy_id=100 AND state IS NOT NULL AND state!='' GROUP BY state ORDER BY n DESC",
        conn
    )
    conn.close()

    if not df.empty:
        fig = px.choropleth(df, locations="state", locationmode="USA-states",
                            color="n", scope="usa", color_continuous_scale="Reds",
                            title=f"Catholic Churches by State ({df['n'].sum():,} total)",
                            labels={"n": "Catholic Churches", "state": "State"})
        fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
        path = img_dir / "catholic_map.png"
        fig.write_image(str(path), width=1200, height=700, scale=2)
        images["catholic_map"] = (path, 2400, 1400)

    return images


# ── Upload ─────────────────────────────────────────────────────────────

def upload(images: dict, headers: dict) -> dict:
    result = {}
    for name, (local_path, w, h) in images.items():
        with open(local_path, "rb") as f:
            data = f.read()
        b64 = base64.b64encode(data).decode("utf-8")
        r = requests.post(f"https://{SUBDOMAIN}.substack.com/api/v1/image",
                          headers=headers, json={"image": f"data:image/png;base64,{b64}"})
        if r.status_code == 200:
            d = r.json()
            result[name] = {"url": d["url"], "width": d.get("imageWidth", w),
                            "height": d.get("imageHeight", h), "bytes": d.get("bytes", len(data))}
            print(f"   [OK] {name} uploaded")
        else:
            print(f"   [WARN] {name} failed ({r.status_code})")
    return result


# ── Build post ─────────────────────────────────────────────────────────

def build_doc(imgs: dict) -> list:
    def im(name):
        if name in imgs:
            i = imgs[name]
            return img(i["url"], i["width"], i["height"], i["bytes"])
        return p(f"[Image: {name}]")

    # Query Catholic count
    conn = sqlite3.connect(str(DB_PATH))
    catholic = conn.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND taxonomy_id=100").fetchone()[0]
    total_us = conn.execute("SELECT COUNT(*) FROM churches WHERE country='US'").fetchone()[0]
    conn.close()
    pct = round(catholic / total_us * 100, 1)

    return [
        h("America Is Changing: The Latino Catholic Shift Reshaping the U.S. Religious Landscape", 1),
        pr([{"text": "July 4, 2026", "italic": True},
            {"text": " · Charles Prescott · GRID Project", "italic": True}]),
        hr(),

        p("Independence Day is a holiday about American identity — not the symbolic version, but the demographic one. Every July 4th, we celebrate a nation that has never stopped changing. And if you want to understand how America is changing right now, you don't look at headlines or polling."),
        p("You look at infrastructure."),
        p("Specifically: Catholic infrastructure."),
        p("Because the most consequential religious transformation in modern American history is happening quietly, steadily, and with almost no public attention:"),
        pr([{"text": "The center of gravity in American Catholicism is becoming Latino.", "bold": True}]),
        p("This isn't speculative. It isn't theoretical. It isn't a projection."),
        p("It's already visible in the physical footprint of the church — in the buildings, parishes, and communities GRID tracks."),

        h("The Demographic Reality"),
        p("Academic demographers have been documenting the trend for two decades, but the scale is only now becoming undeniable:"),
        bul(
            [{"text": "Roughly ", "bold": False}, {"text": "40%", "bold": True}, {"text": " of U.S. Catholics are Latino."}],
            [{"text": "Among Catholics under 30, it's ", "bold": False}, {"text": "over 60%", "bold": True}, {"text": "."}],
            [{"text": "In many dioceses, Latino Catholics constitute the majority of active parish life."}],
            [{"text": "Spanish-language Mass attendance is rising even as English-language attendance declines."}],
        ),
        p("This is not a marginal shift. It is a structural realignment of American Catholic identity."),
        p("And unlike many religious trends, this one is not driven by institutional strategy. It is driven by population dynamics, migration patterns, and fertility differentials — the same forces that have shaped American religious life since the 19th century."),

        h("The Infrastructure Evidence (GRID's Lens)"),
        p(f"GRID tracks {catholic:,} Catholic churches across the United States — {pct}% of all religious buildings in the country. The dataset makes the shift visible in physical space:"),
        bul(
            [{"text": "Parishes adding Spanish Masses in counties that were once uniformly Anglo-Catholic."}],
            [{"text": "Bilingual clergy becoming a functional necessity rather than a cultural accommodation."}],
            [{"text": "Mission churches forming in Latino-majority suburbs and exurbs."}],
            [{"text": "Rural parishes stabilized — or revived — by Latino families moving into agricultural regions."}],
            [{"text": "Urban parishes experiencing demographic turnover that mirrors neighborhood change."}],
        ),
        pr([{"text": "The Catholic Church is not shrinking. It is reorganizing.", "bold": True}]),
        p("And the reorganization follows the same pattern as every major American demographic transition: new populations reshape old institutions by inhabiting them."),
        im("catholic_map"),

        h("Why This Matters for Understanding America"),
        p("On July 4th, we celebrate a nation defined by:"),
        bul(
            [{"text": "immigration"}],
            [{"text": "pluralism"}],
            [{"text": "voluntary association"}],
            [{"text": "community formation"}],
            [{"text": "local autonomy"}],
        ),
        p("Latino Catholicism is all of these things."),
        p("It is the continuation of a long American pattern: new communities revitalizing old civic structures."),
        p("In the 19th century, it was German and Irish Catholics. In the early 20th, Italian and Polish Catholics. In the late 20th and early 21st, it is Latino Catholics."),
        p("The pattern is academically clear: American Catholicism survives by becoming more American — and America becomes more American by becoming more diverse."),

        h("The Institutional Consequences"),
        p("This demographic shift will reshape:"),
        bul(
            [{"text": "seminary training"}],
            [{"text": "parish staffing"}],
            [{"text": "diocesan resource allocation"}],
            [{"text": "liturgical practice"}],
            [{"text": "community outreach"}],
            [{"text": "Catholic education"}],
            [{"text": "political engagement"}],
        ),
        p("It is not a cultural footnote. It is a civilizational-scale transition inside one of America's largest and oldest institutions."),
        p("And it is happening at the level GRID is built to observe: the building, the parish, the neighborhood."),

        h("The Fourth of July Meaning"),
        p("Independence Day is not just about the founding. It is about the ongoing project of American identity."),
        p("Latino Catholicism is now one of the most important engines of that project:"),
        bul(
            [{"text": "revitalizing parishes"}],
            [{"text": "stabilizing communities"}],
            [{"text": "reshaping civic life"}],
            [{"text": "redefining the cultural center of American Catholicism"}],
        ),
        p("It is a story of continuity through change — the most American story there is."),
        hr(),
        pr([{"text": "America is changing. Catholic America is changing with it. And the map shows it first.", "bold": True}]),
        hr(),
        pr([{"text": "GRID (Global Religious Infrastructure Database) tracks 3.5M+ religious buildings across 248 countries. The database is available on BigQuery at american-rel-infra.American_Religious_Infrastructure. Contact: charles.prescott@gridproject.org.", "italic": True}]),
    ]


# ── Main ───────────────────────────────────────────────────────────────

def main():
    cookie = os.environ.get("SUBSTACK_COOKIE", "")
    if not cookie:
        print("ERROR: Set SUBSTACK_COOKIE env var")
        sys.exit(1)

    headers = {
        "Cookie": f"connect.sid={cookie}; substack.sid={cookie}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
    }

    # Auth
    print("[1/3] Authenticating...")
    r = requests.get("https://substack.com/api/v1/user/profile/self", headers=headers)
    profile = r.json()
    pub_user = next(pu for pu in profile["publicationUsers"]
                    if pu["publication"]["subdomain"] == SUBDOMAIN)
    print(f"   {profile.get('handle')} (id={profile['id']})")

    # Charts
    print("\n[2/3] Generating charts...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img_dir = OUTPUT_DIR / f"catholic_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    img_dir.mkdir(parents=True, exist_ok=True)
    images = make_charts(img_dir)
    imgs = upload(images, headers)

    # Build & post
    print("\n[3/3] Creating draft...")
    doc = build_doc(imgs)
    body = {
        "draft_title": "America Is Changing: The Latino Catholic Shift Reshaping the U.S. Religious Landscape",
        "draft_subtitle": "The center of gravity in American Catholicism is becoming Latino — and the map shows it first",
        "draft_body": json.dumps(pm(*doc)),
        "type": "newsletter",
        "draft_bylines": [{"id": profile["id"], "publicationUserId": pub_user["id"]}],
    }
    r = requests.post(f"https://{SUBDOMAIN}.substack.com/api/v1/drafts",
                      headers=headers, json=body)
    if r.status_code != 200:
        print(f"   ERROR ({r.status_code}): {r.text[:300]}")
        sys.exit(1)
    draft = r.json()
    print(f"\n[DONE] https://{SUBDOMAIN}.substack.com/publish/post/{draft['id']}")


if __name__ == "__main__":
    main()
