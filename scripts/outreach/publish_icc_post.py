#!/usr/bin/env python
"""Publish the Independent Christian Church post to Substack.

The Independent Christian Churches / Churches of Christ are the instrumental
branch of the Restoration Movement (Stone-Campbell Movement). This post tells
their story using GRID's physical-infrastructure data.
"""

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
    """Generate a tri-color RGB heat map from raw GPS points.

    Each branch (ICC=Red, CoC=Green, Doc=Blue) gets its own kernel density
    surface. The three surfaces are combined into an RGB image where:
      - Red intensity = ICC density
      - Green intensity = CoC density
      - Blue intensity = Doc density

    State borders are overlaid for reference. This ignores state boundaries
    for the density calculation, revealing the true regional patterns.
    """
    images = {}
    conn = sqlite3.connect(str(DB_PATH))

    # Pull raw GPS points for all three branches
    df = pd.read_sql_query(
        """SELECT c.taxonomy_id, c.latitude, c.longitude
           FROM churches c
           WHERE c.taxonomy_id IN (324, 320, 318)
             AND c.latitude IS NOT NULL AND c.longitude IS NOT NULL
             AND c.latitude BETWEEN 24 AND 50
             AND c.longitude BETWEEN -125 AND -66""",
        conn
    )
    conn.close()

    if df.empty:
        return images

    # Split by branch
    icc_pts = df[df["taxonomy_id"] == 324][["longitude", "latitude"]].values
    coc_pts = df[df["taxonomy_id"] == 320][["longitude", "latitude"]].values
    doc_pts = df[df["taxonomy_id"] == 318][["longitude", "latitude"]].values

    # Create a regular grid over the continental US
    import numpy as np
    from scipy.stats import gaussian_kde

    lon_min, lon_max = -125, -66
    lat_min, lat_max = 24, 50
    grid_res = 300  # 300x300 grid = 90k cells

    lon_grid = np.linspace(lon_min, lon_max, grid_res)
    lat_grid = np.linspace(lat_min, lat_max, grid_res)
    LON, LAT = np.meshgrid(lon_grid, lat_grid)
    grid_coords = np.vstack([LON.ravel(), LAT.ravel()])

    def kde_density(pts, grid_coords, bw=1.5):
        """Gaussian KDE density on grid. bw in degrees (~165 km at 1 deg)."""
        if len(pts) < 3:
            return np.zeros(grid_coords.shape[1])
        kde = gaussian_kde(pts.T, bw_method=bw)
        return kde(grid_coords)

    print("  Computing KDE for ICC (red)...")
    icc_dens = kde_density(icc_pts, grid_coords)
    print("  Computing KDE for CoC (green)...")
    coc_dens = kde_density(coc_pts, grid_coords)
    print("  Computing KDE for Doc (blue)...")
    doc_dens = kde_density(doc_pts, grid_coords)

    # Normalize each channel independently to [0, 1]
    for arr in (icc_dens, coc_dens, doc_dens):
        mx = arr.max()
        if mx > 0:
            arr /= mx

    # Build RGB image
    rgb = np.dstack([
        icc_dens.reshape(grid_res, grid_res),   # R
        coc_dens.reshape(grid_res, grid_res),   # G
        doc_dens.reshape(grid_res, grid_res),   # B
    ])

    # Apply gamma for better visual contrast
    gamma = 0.6
    rgb = np.power(rgb, gamma)

    # Plot with matplotlib for precise control
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(14, 9))

    # Show the RGB heatmap
    extent = [lon_min, lon_max, lat_min, lat_max]
    ax.imshow(rgb, extent=extent, origin='lower', aspect='auto', alpha=0.9)

    # Overlay state borders
    from matplotlib.patches import Polygon
    from matplotlib.collections import PatchCollection
    import json

    # Load US state boundaries from a simple GeoJSON (or use cartopy if available)
    # For simplicity, draw a clean US outline and major state boundaries
    # We'll use a pre-downloaded simplified state boundary file if available
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=ccrs.PlateCarree())
        ax.imshow(rgb, extent=extent, origin='lower', aspect='auto', alpha=0.9,
                  transform=ccrs.PlateCarree())
        ax.add_feature(cfeature.STATES.with_scale('50m'), edgecolor='white',
                       facecolor='none', linewidth=0.5, alpha=0.8)
        ax.add_feature(cfeature.COASTLINE.with_scale('50m'), edgecolor='white',
                       linewidth=0.5, alpha=0.6)
    except ImportError:
        # Fallback: simple matplotlib with basic state outlines
        # Draw a clean background
        ax.set_xlim(lon_min, lon_max)
        ax.set_ylim(lat_min, lat_max)
        ax.set_aspect(1.3)

    # Title with totals
    icc_tot = len(icc_pts)
    coc_tot = len(coc_pts)
    doc_tot = len(doc_pts)
    ax.set_title(
        f"Restoration Movement Density: ICC (Red) | CoC (Green) | Doc (Blue)\n"
        f"ICC={icc_tot:,}  CoC={coc_tot:,}  Doc={doc_tot:,}  |  Kernel density, state borders overlaid",
        fontsize=12, fontweight='bold', pad=15
    )

    # Add a custom legend
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='red', label='Independent Christian Churches (ICC)'),
        Patch(facecolor='green', label='Churches of Christ (CoC)'),
        Patch(facecolor='blue', label='Christian Church / Disciples of Christ (Doc)'),
    ]
    ax.legend(handles=legend_elements, loc='lower left', framealpha=0.9,
              fontsize=9, title='Branch (RGB Channel)')

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")

    path = img_dir / "icc_map.png"
    fig.savefig(str(path), dpi=200, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(f"  [OK] Tri-color heatmap saved: {path}")
    images["icc_map"] = (path, 2800, 1800)

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

    conn = sqlite3.connect(str(DB_PATH))
    icc = conn.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=324").fetchone()[0]
    coc = conn.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=320").fetchone()[0]
    doc = conn.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=318").fetchone()[0]
    # Midwest states
    midwest = ['IN','IL','KY','OH','MO','KS','OK','MI','IA','MN','WI','NE','ND','SD']
    q = ",".join("?"*len(midwest))
    mw = conn.execute(f"""
        SELECT COUNT(*) FROM churches c
        LEFT JOIN church_location l ON c.id=l.church_id
        WHERE c.taxonomy_id=324 AND l.country='US' AND l.state IN ({q})
    """, midwest).fetchone()[0]
    # Top states
    top = conn.execute("""
        SELECT l.state, COUNT(*) n FROM churches c
        LEFT JOIN church_location l ON c.id=l.church_id
        WHERE c.taxonomy_id=324 AND l.country='US' AND l.state IS NOT NULL AND l.state!=''
        GROUP BY l.state ORDER BY n DESC LIMIT 5
    """).fetchall()
    conn.close()

    top_str = ", ".join(f"{s} ({n})" for s, n in top)
    mw_pct = round(mw / icc * 100, 0)

    return [
        h("The Church That Refuses to Be a Denomination: Inside the Independent Christian Churches", 1),
        pr([{"text": "September 6, 2026", "italic": True},
            {"text": " · Charles Prescott · GRID Project", "italic": True}]),
        hr(),

        p("There is a religious movement in America that has no headquarters, no pope, no synod, no denominational president, and no official membership rolls. It has no creed beyond a single sentence. And yet it has planted thousands of churches across the country — and it is still growing."),
        p("It is called the Independent Christian Churches / Churches of Christ, and it is one of the most quietly successful religious movements in American history."),
        p("Most Americans have never heard of it. But they have driven past its buildings their whole lives — the modest brick church on the corner of Main Street with the sign that simply reads \u201cFirst Christian Church.\u201d"),
        pr([{"text": "That sign is the whole theology.", "bold": True}]),

        h("A Movement That Began With a Radical Idea"),
        p("The story starts in the early 1800s, on the American frontier. Two Presbyterian ministers — Barton Stone in Kentucky and Thomas Campbell (and his son Alexander) in Pennsylvania — independently reached the same conclusion: the endless denominational squabbling of the day was a scandal."),
        p("Their solution was radical. Instead of founding yet another denomination, they proposed to abandon denominational labels entirely and simply restore the church described in the New Testament. No creeds. No human-made divisions. Just Christians."),
        p("Their slogan became the movement's DNA:"),
        pr([{"text": "\u201cWhere the Scriptures speak, we speak; where the Scriptures are silent, we are silent.\u201d", "italic": True}]),
        p("And their goal was unity: \u201cWe are Christians only, but not the only Christians.\u201d"),
        p("The movement spread like wildfire across the frontier — through Kentucky, Ohio, Indiana, Tennessee, and Missouri. It was, in many ways, the perfect religion for a young, individualistic, self-governing nation."),

        h("One Movement, Three Branches"),
        p("But the movement that began as a plea for unity did what all movements do: it divided. Over the 20th century, the Restoration Movement split into three main branches:"),
        bul(
            [{"text": "The ", "bold": False}, {"text": "Churches of Christ", "bold": True}, {"text": " (a cappella, non-instrumental) — the most conservative branch, strongest in the South."}],
            [{"text": "The ", "bold": False}, {"text": "Christian Church (Disciples of Christ)", "bold": True}, {"text": " — the most liberal, organized branch, which formally became a denomination in 1968."}],
            [{"text": "The ", "bold": False}, {"text": "Independent Christian Churches / Churches of Christ", "bold": True}, {"text": " — the middle path: theologically conservative, but fiercely independent and instrumental in worship."}],
        ),
        p("The Independent Christian Churches are the branch this post is about. And they are, in a sense, the most American of the three."),

        h("What Makes Them \u201cIndependent\u201d"),
        p("The word \u201cindependent\u201d is not a marketing slogan. It is a structural fact. The Independent Christian Churches have:"),
        bul(
            [{"text": "No central headquarters"}],
            [{"text": "No denominational hierarchy"}],
            [{"text": "No governing synod or council"}],
            [{"text": "No official membership rolls"}],
            [{"text": "No authority over local congregations"}],
        ),
        p("Each congregation is autonomous. It calls its own minister, owns its own building, and makes its own decisions. The \u201cfellowship\u201d is held together not by structure but by shared conviction, shared history, and a network of parachurch institutions — Bible colleges, mission agencies, and publications."),
        p("The most famous of those publications is the one that gave this movement its name: the Christian Standard, founded in Cincinnati in 1866. It is still published today — and its online directory is exactly the kind of source GRID uses to map the movement's physical footprint."),

        h("The Instrumental Question"),
        p("If you want to understand the difference between the Independent Christian Churches and their a cappella cousins, look no further than the organ."),
        p("In the 1860s, some congregations began introducing musical instruments into worship. The more conservative wing — concentrated in the South, around Nashville and the Gospel Advocate — rejected this as unbiblical. They became the a cappella Churches of Christ."),
        p("The more moderate wing — concentrated in the North, around Cincinnati and the Christian Standard — accepted instruments. They became the Independent Christian Churches."),
        p("It is a remarkably small difference to split a movement over. But it is a difference that still shapes the religious geography of America today."),

        h("What GRID's Data Shows"),
        p(f"GRID (Global Religious Infrastructure Database) tracks {icc:,} Independent Christian Church congregations worldwide — and the physical footprint tells the story better than any membership roll."),
        p(f"The movement's heartland is unmistakable. Roughly {mw_pct:.0f}% of U.S. Independent Christian Churches sit in the historic Restoration Movement core of the Midwest: {top_str}."),
        p("This is not an accident. It is the direct legacy of the frontier revivals of the 1820s and 1830s, which swept through the Ohio River Valley and the upper South. The movement grew where the frontier was — and it stayed."),
        im("icc_map"),
        p("For comparison, GRID also tracks the other two branches:"),
        bul(
            [{"text": f"Independent Christian Churches: {icc:,}"}],
            [{"text": f"Churches of Christ (a cappella): {coc:,}"}],
            [{"text": f"Christian Church (Disciples of Christ): {doc:,}"}],
        ),
        p("The a cappella Churches of Christ, true to their Southern roots, are more evenly spread across the South and Texas. The Independent Christian Churches cluster in the Midwest. The Disciples, the most urbanized and liberal branch, are concentrated in cities."),

        h("The Naming Convention"),
        p("There is a subtle but telling rule in this movement: congregations are named after places, not people."),
        p("Because the movement insists that the church belongs to Christ — not to any founder or pastor — it is considered improper to name a congregation after a person. So you get \u201cFirst Christian Church of Springfield,\u201d \u201cLexington Christian Church,\u201d \u201cAntioch Christian Church\u201d — but never \u201cSmith Memorial Church.\u201d"),
        p("This is why, when you drive through the Midwest, you see so many buildings with the same simple, unadorned name. It is a theological statement written in brick."),

        h("A Movement Without a Headquarters"),
        p("The Independent Christian Churches are often described as the largest religious body in America with no central organization. Estimates put their U.S. membership at roughly 1.1 to 1.3 million across 5,500 to 5,700 congregations."),
        p("They are held together by a web of voluntary institutions rather than authority:"),
        bul(
            [{"text": "Bible colleges (like Cincinnati Christian University and Hope International University)"}],
            [{"text": "Mission agencies (supporting missionaries directly, rather than through a central board)"}],
            [{"text": "Publications (the Christian Standard and its successors)"}],
            [{"text": "Conventions (like the North American Christian Convention)"}],
        ),
        p("This is congregationalism taken to its logical extreme — and it works. The movement has planted churches on every continent, and its missionaries are supported directly by the congregations that send them."),

        h("Why This Matters"),
        p("The Independent Christian Churches matter for understanding America for a simple reason: they are a living example of how American religion actually works."),
        p("America's religious landscape is not a top-down story of denominations and hierarchies. It is a bottom-up story of autonomous congregations, voluntary networks, and local initiative. The Independent Christian Churches are that story in its purest form."),
        p("They also remind us that the most consequential religious movements are often the ones that make the least noise. No headquarters, no press releases, no celebrity pastors — just thousands of local churches, each one an independent decision to gather, worship, and serve."),
        p("And in an era of institutional decline, that is worth paying attention to."),

        h("The Infrastructure Lens"),
        p("GRID's approach is to study religion through its physical footprint — the buildings, parishes, and communities where faith actually happens. The Independent Christian Churches are a perfect case study."),
        p("Their buildings are modest. Their names are plain. Their organization is invisible. But their footprint is real, measurable, and concentrated in a way that tells the story of American religious history in a single map."),
        p("The next time you pass a small brick church that simply says \u201cChristian Church,\u201d you will know what you're looking at: a congregation that has spent two centuries refusing to become a denomination — and succeeding."),
        hr(),
        pr([{"text": "The church that refuses to be a denomination is, in the end, one of the most American institutions there is.", "bold": True}]),
        hr(),
        pr([{"text": "GRID (Global Religious Infrastructure Database) tracks 4.9M+ religious buildings across 248 countries. The database is available on BigQuery at american-rel-infra.American_Religious_Infrastructure. Contact: charles@gridataset.com.", "italic": True}]),
    ]


# ── Main ───────────────────────────────────────────────────────────────

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft-id", type=str, default=None,
                    help="Update an existing draft instead of creating a new one")
    args = ap.parse_args()

    cookie = os.environ.get("SUBSTACK_COOKIE", "")
    if not cookie:
        print("ERROR: Set SUBSTACK_COOKIE env var")
        sys.exit(1)

    headers = {
        "Cookie": f"connect.sid={cookie}; substack.sid={cookie}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
    }

    print("[1/3] Authenticating...")
    r = requests.get("https://substack.com/api/v1/user/profile/self", headers=headers)
    profile = r.json()
    pub_user = next(pu for pu in profile["publicationUsers"]
                    if pu["publication"]["subdomain"] == SUBDOMAIN)
    print(f"   {profile.get('handle')} (id={profile['id']})")

    print("\n[2/3] Generating charts...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    img_dir = OUTPUT_DIR / f"icc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    img_dir.mkdir(parents=True, exist_ok=True)
    images = make_charts(img_dir)
    imgs = upload(images, headers)

    print("\n[3/3] Building post...")
    doc = build_doc(imgs)
    title = "The Church That Refuses to Be a Denomination: Inside the Independent Christian Churches"
    body = {
        "draft_title": title,
        "draft_subtitle": "No headquarters, no hierarchy, no membership rolls — just thousands of autonomous congregations. The Independent Christian Churches are one of America's most quietly successful religious movements.",
        "draft_body": json.dumps(pm(*doc)),
        "type": "newsletter",
        "draft_bylines": [{"id": profile["id"], "publicationUserId": pub_user["id"]}],
    }

    if args.draft_id:
        r = requests.put(f"https://{SUBDOMAIN}.substack.com/api/v1/drafts/{args.draft_id}",
                         headers=headers, json=body)
        if r.status_code != 200:
            print(f"   ERROR ({r.status_code}): {r.text[:300]}")
            sys.exit(1)
        draft = r.json()
        print(f"\n[DONE] Updated draft: https://{SUBDOMAIN}.substack.com/publish/post/{draft['id']}")
    else:
        r = requests.post(f"https://{SUBDOMAIN}.substack.com/api/v1/drafts",
                          headers=headers, json=body)
        if r.status_code != 200:
            print(f"   ERROR ({r.status_code}): {r.text[:300]}")
            sys.exit(1)
        draft = r.json()
        print(f"\n[DONE] https://{SUBDOMAIN}.substack.com/publish/post/{draft['id']}")


if __name__ == "__main__":
    main()
