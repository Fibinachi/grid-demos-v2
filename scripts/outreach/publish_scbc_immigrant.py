#!/usr/bin/env python
"""Publish SCBC Rural Immigrant Congregation Opportunities post to Substack."""

import os, sys, json, base64
from pathlib import Path
from datetime import datetime
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

SUBDOMAIN = "gridkeeper"
CHART_PATH = Path(__file__).resolve().parents[2] / "reports" / "scbc_immigrant" / "scbc_immigrant_rural_chart.png"

# ── ProseMirror helpers ────────────────────────────────────────────

def pm(*content):
    return {"type": "doc", "content": list(content)}

def h(text, level=2):
    return {"type": "heading", "attrs": {"level": level},
            "content": [{"type": "text", "text": text}]}

def p(text):
    return {"type": "paragraph", "attrs": {"textAlign": None},
            "content": [{"type": "text", "text": text}]}

def pr(parts):
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

# ── Build post ─────────────────────────────────────────────────────

def build_doc(imgs: dict) -> list:
    def im(name):
        if name in imgs:
            i = imgs[name]
            return img(i["url"], i["width"], i["height"], i["bytes"])
        return p(f"[Image: {name}]")

    return [
        h("Where Rural SBC Decline Meets Immigrant Opportunity: 25 South Carolina Churches Ready for Something New", 1),
        pr([{"text": "July 17, 2026", "italic": True},
            {"text": " \u00b7 Charles Prescott \u00b7 GRID Project", "italic": True}]),
        hr(),

        p("Every denomination has a map problem it doesn't want to look at."),
        p("For the Southern Baptist Convention, the map problem is rural South Carolina."),
        p("Between 2010 and 2020, SBC adherents in the state's non-metro counties declined by an average of 20%. In some counties, the loss exceeded 30%. These are not churches closing -- at least, not yet. They are churches shrinking, aging, and wondering what comes next."),
        pr([{"text": "At the same time, immigrant communities are settling in these same rural counties -- drawn by agriculture, manufacturing, and the lower cost of living that makes small-town America viable for new arrivals.", "bold": False}]),
        p("The question is whether these two trends -- declining SBC presence and growing immigrant presence -- can be connected. Not through institutional mandate. Through local churches making local decisions about sharing space, sharing ministry, and sharing a future."),
        p("This report identifies 25 SBC churches in rural South Carolina that are positioned at the intersection of these two trends."),

        h("The Methodology"),
        p("We scored 368 SBC churches in South Carolina's non-metro counties (RUCC 4-9, the USDA's rural-urban classification) using four factors:"),
        bul(
            [{"text": "Immigrant proximity (35%)", "bold": True}, {"text": " \u2014 Hispanic and Asian percentage in the church's ZIP code, from ACS 5-year estimates. Rural-adjusted threshold: 15%."}],
            [{"text": "SBC decline (30%)", "bold": True}, {"text": " \u2014 County-level SBC adherent loss from 2010 to 2020, using the ARDA U.S. Religion Census. Rural-adjusted threshold: 40%."}],
            [{"text": "Population reach (15%)", "bold": True}, {"text": " \u2014 Total population within a 15km radius of the church, computed from Census 2020 tract centroids. Rural-adjusted threshold: 200,000."}],
            [{"text": "Facility viability (20%)", "bold": True}, {"text": " \u2014 Building square footage, parking capacity, and estimated seating -- because a church that can't physically host a second congregation isn't a candidate for one."}],
        ),
        p("The results are capped at 3 churches per county to ensure geographic diversity. Without the cap, a single county (Newberry, with 30% SBC decline and 19% immigrant presence) would have dominated the entire list."),

        im("scbc_chart"),

        h("What the Map Shows"),
        p("The 25 churches span 11 counties, from the Upstate foothills of Oconee County to the Lowcountry plains of Hampton and Colleton. The geographic distribution matters:"),
        bul(
            [{"text": "Newberry County", "bold": True}, {"text": " (3 churches): 30% SBC decline, 13-19% immigrant ZIPs. Ground zero for the overlap. Fairview Baptist in Kinards sits in an 18.7% immigrant ZIP code -- nearly one in five residents."}],
            [{"text": "Greenwood County", "bold": True}, {"text": " (3 churches): 24% SBC decline, 4-12% immigrant ZIPs. More modest numbers, but Callie Self Memorial Baptist sits in an 11.5% immigrant ZIP with a 63,000-person catchment."}],
            [{"text": "Oconee County", "bold": True}, {"text": " (3 churches): Only 13% SBC decline, but Walhalla area ZIPs are 12-17% immigrant. Iglesia Cristiana La Roca is already here -- a Spanish-language church operating in SBC territory."}],
            [{"text": "Colleton, Chesterfield, and Barnwell", "bold": True}, {"text": " (3 each): Lower SBC decline (14-17%) but ZIP immigrant percentages ranging from 6-19%. Smaller catchments, smaller facilities -- but also less competition."}],
            [{"text": "Lee, Orangeburg, Marion, Hampton, and Cherokee", "bold": True}, {"text": " (1-2 each): Filling out the map. Grassy Pond Baptist in Cherokee County is the only Upstate representative north of the Greenville-Spartanburg metro line."}],
        ),

        pr([{"text": "This is not a list of the 25 most immigrant-dense ZIP codes in South Carolina. It is a list of 25 churches where the numbers suggest a conversation is worth having.", "italic": True}]),

        h("Why Rural, and Why Now"),
        p("The standard church-planting playbook focuses on suburbs and exurbs -- growing populations, younger demographics, new construction. That model works where population growth creates demand faster than existing churches can absorb it."),
        p("Rural America works differently. The population isn't growing. The buildings already exist. The challenge isn't building new capacity -- it's repurposing capacity that is currently underused."),
        p("This is the argument for immigrant congregations in rural SBC churches:"),
        bul(
            [{"text": "Lower costs", "bold": True}, {"text": ". A rural church that seats 200 but averages 45 on Sunday morning has margin. The building is paid for. The parking exists. The kitchen works."}],
            [{"text": "Less competition", "bold": True}, {"text": ". In metro Charleston, new immigrant congregations compete with dozens of established ethnic churches. In rural Newberry County, they may be the only Spanish-language option within 20 miles."}],
            [{"text": "Community integration", "bold": True}, {"text": ". Rural churches are often the center of their community in ways suburban churches aren't. A church that hosts a food pantry, ESL classes, and a Spanish-language service becomes indispensable -- not just to immigrants, but to the town."}],
            [{"text": "Workforce alignment", "bold": True}, {"text": ". The industries drawing immigrants to rural South Carolina -- poultry processing, agriculture, warehousing, construction -- are not moving to cities. The workers are here. The churches should be too."}],
        ),

        h("What SCBC Can Do"),
        p("The South Carolina Baptist Convention has the infrastructure to act on this data. The question is whether the institutional will exists to prioritize rural immigrant ministry alongside suburban church planting."),
        p("Five concrete steps:"),
        bul(
            [{"text": "Site visits to the top 5 churches", "bold": True}, {"text": " -- Fairview Baptist (Kinards), Glenn Street Baptist (Newberry), Enoree Baptist (Newberry), Callie Self Memorial (Greenwood), and Connie Maxwell (Greenwood). Assess facility condition, meet the pastor, gauge openness."}],
            [{"text": "Partner with NAMB's Send Network", "bold": True}, {"text": " -- The North American Mission Board has rural church planting resources. This is a natural fit for their assessment process."}],
            [{"text": "Identify bi-vocational planters", "bold": True}, {"text": " -- Rural immigrant congregations will rarely support a full-time pastor immediately. Look for bi-vocational leaders already working in local industries."}],
            [{"text": "Map the employers", "bold": True}, {"text": " -- Before planting a Spanish-language congregation, know where the Spanish-speaking workforce is. Poultry plants, farms, distribution centers -- these are your mission field demographics."}],
            [{"text": "Start with ESL and food ministry", "bold": True}, {"text": " -- The fastest way to build trust between a declining Anglo SBC church and a new immigrant congregation is shared service. ESL classes on Tuesday nights. Food distribution on Saturday mornings. The worship service comes later."}],
        ),

        hr(),

        h("The Bigger Picture"),
        p("The SBC has spent two decades fighting about membership decline. The fights have been about theology, about politics, about identity -- everything except what the data actually shows."),
        p("The data shows that SBC decline is geographically concentrated. It is worst in rural counties with aging populations and limited economic growth. Those same counties, in many cases, are seeing immigration-driven demographic renewal."),
        p("The SBC doesn't have a theology problem in rural South Carolina. It has a capacity utilization problem. The buildings are there. The parking lots are there. The communities are changing around them."),
        pr([{"text": "The question is whether the denomination can see the opportunity before the buildings close.", "bold": True}]),

        hr(),
        p("Methodology notes: Churches scored on immigrant proximity (ZIP-level Hispanic% + Asian%, ACS 5-year, 35% weight), county SBC decline (ARDA 2010-2020, 30% weight), 15km population catchment (Census 2020 tracts, 15% weight), and facility viability (building sq ft + parking + capacity, 20% weight). Results capped at 3 per county for geographic diversity. RUCC 4-9 only."),
        pr([{"text": "GRID (Global Religious Infrastructure Database) tracks 3.5M+ religious buildings across 248 countries. Full dataset available on BigQuery at american-rel-infra.American_Religious_Infrastructure. Contact: charles@gridataset.com.", "italic": True}]),
    ]

# ── Main ───────────────────────────────────────────────────────────

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
    if r.status_code != 200:
        print(f"   AUTH ERROR ({r.status_code}): {r.text[:200]}")
        sys.exit(1)
    profile = r.json()
    pub_user = next(pu for pu in profile["publicationUsers"]
                    if pu["publication"]["subdomain"] == SUBDOMAIN)
    print(f"   {profile.get('handle')} (id={profile['id']})")

    # Upload chart
    print("\n[2/3] Uploading chart...")
    with open(CHART_PATH, "rb") as f:
        chart_data = f.read()
    b64 = base64.b64encode(chart_data).decode("utf-8")
    r = requests.post(f"https://{SUBDOMAIN}.substack.com/api/v1/image",
                      headers=headers, json={"image": f"data:image/png;base64,{b64}"})
    if r.status_code != 200:
        print(f"   UPLOAD ERROR ({r.status_code}): {r.text[:200]}")
        sys.exit(1)
    upload = r.json()
    imgs = {
        "scbc_chart": {
            "url": upload["url"],
            "width": upload.get("imageWidth", 2800),
            "height": upload.get("imageHeight", 2300),
            "bytes": upload.get("bytes", len(chart_data)),
        }
    }
    print(f"   [OK] Chart uploaded ({len(chart_data)/1024:.0f} KB)")

    # Build & create draft
    print("\n[3/3] Creating draft...")
    doc = build_doc(imgs)
    title = "Where Rural SBC Decline Meets Immigrant Opportunity: 25 South Carolina Churches Ready for Something New"
    body = {
        "draft_title": title,
        "draft_subtitle": "SCBC has a capacity utilization problem, not a theology problem. The buildings are there, the parking lots are there -- and the communities are changing around them.",
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
