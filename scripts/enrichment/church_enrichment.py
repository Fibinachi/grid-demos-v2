#!/usr/bin/env python3
"""
GrantWizard Church Enrichment Engine
=====================================
Deep-enriches church profiles with data from web, APIs, and OSM.

Usage:
    python church_enrichment.py                               # enrich all
    python church_enrichment.py --chunks 100                  # first 100
    python church_enrichment.py --resume                      # resume from checkpoint
    python church_enrichment.py --module ssl,whois,tiktok     # specific modules only

Modules:
    ssl       SSL certificate age & issuer
    whois     Domain age & registrar
    tiktok    TikTok presence check
    techstack Website tech stack (CMS, frameworks, analytics)
    giving    Giving platform detection
    ada       ADA accessibility statement detection
    zerobounce Email deliverability score
    osm       OSM features (parking, transit, building footprint)
    density   Competition density (churches per sq mi)
    walk      Walkability estimate (POI density)
    denom     Denomination HQ, conference, network lookup
"""

import sqlite3, csv, json, os, re, sys, ssl, socket, time, datetime
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, quote

# ── Config ────────────────────────────────────────────────────────
DB_PATH = r"E:\grid\churches.db"
OUT_DIR = r"E:\grid\data\enrichment"
os.makedirs(OUT_DIR, exist_ok=True)
ZEROBOUNCE_KEY = os.environ.get("ZEROBOUNCE_API_KEY", "")
CHECKPOINT_FILE = os.path.join(OUT_DIR, "enrichment_checkpoint.json")
TIMEOUT = 15

# ── Signatures ────────────────────────────────────────────────────
TIKTOK_PATTERNS = [
    lambda n: n.lower().replace(" ", "").replace("'", "").replace(".", "")[:30],
    lambda n: n.lower().replace(" ", "_").replace("'", "").replace(".", "")[:30],
]
GIVING_SIGS = {
    "Tithe.ly": ["tithe.ly", "tith.ly", "pushpay"],
    "Subsplash": ["subsplash.com/giving", "pushpay.com"],
    "Planning Center": ["planningcenter.com/giving", "churchcenter.com/giving"],
    "SecureGive": ["securegive"],
    "EasyTithe": ["easyttithe", "easytithe"],
    "Givelify": ["givelify"],
    "Vanco": ["vanco", "faithdirect"],
    "Donorbox": ["donorbox"],
    "Stripe": ["stripe.com"],
    "PayPal": ["paypal.com"],
    "Square": ["squareup.com", "square.site"],
}
TECH_SIGS = {
    "WordPress": [r"wp-content", r"wp-includes", r"\/wp-json"],
    "Squarespace": [r"squarespace"],
    "Wix": [r"wix\.com", r"wixstatic"],
    "Drupal": [r"drupal", r"sites/default"],
    "Joomla": [r"joomla"],
    "Next.js": [r"__next"],
    "React": [r"react\.js", r"react\.min"],
    "Vue": [r"vue\.js"],
    "Cloudflare": [r"cloudflare"],
    "Google Analytics": [r"gtag", r"analytics\.js"],
    "Facebook Pixel": [r"fbq\("],
    "Mailchimp": [r"mailchimp"],
    "Boxcast": [r"boxcast"],
    "YouTube": [r"youtube\.com/embed"],
}
ADA_KW = ["accessibility", "ada compliant", "wcag", "accessible", "screen reader"]
DENOM_DATA = {
    "southern baptist convention": {"hq": "Nashville, TN", "conference": "SBC", "network": "SBC"},
    "united methodist church": {"hq": "Nashville, TN", "conference": "Annual Conference", "network": "UMC"},
    "episcopal": {"hq": "New York, NY", "conference": "Episcopal Diocese", "network": "Episcopal Church"},
    "presbyterian": {"hq": "Louisville, KY", "conference": "Presbytery", "network": "PCUSA"},
    "assemblies of god": {"hq": "Springfield, MO", "conference": "AG District", "network": "AG"},
    "church of god in christ": {"hq": "Memphis, TN", "conference": "COGIC Jurisdiction", "network": "COGIC"},
    "lutheran": {"hq": "Chicago, IL (ELCA) / St. Louis, MO (LCMS)", "conference": "Synod", "network": "ELCA/LCMS"},
    "calvary chapel": {"hq": "Costa Mesa, CA", "conference": "Calvary Chapel Fellowship", "network": "Calvary Chapel"},
    "vineyard": {"hq": "Sugar Land, TX", "conference": "Vineyard Regional", "network": "Vineyard USA"},
    "baptist": {"hq": "", "conference": "Baptist Association", "network": "Baptist"},
    "catholic": {"hq": "Vatican City / USCCB", "conference": "Diocese", "network": "Roman Catholic"},
    "methodist": {"hq": "", "conference": "Annual Conference", "network": "Methodist"},
    "pentecostal": {"hq": "", "conference": "District", "network": "Pentecostal"},
    "church of christ": {"hq": "", "conference": "", "network": "Churches of Christ"},
    "church of god": {"hq": "Cleveland, TN", "conference": "COG State Office", "network": "Church of God (Cleveland)"},
    "non-denominational": {"hq": "", "conference": "", "network": "Independent"},
}
OSM_URL = "https://overpass-api.de/api/interpreter"


# ── Helpers ────────────────────────────────────────────────────────
def log(msg):
    t = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{t}] {msg}")

def fetch(url, timeout=TIMEOUT):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.5",
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace")
    except:
        return ""

def osm_query(q):
    try:
        data = json.dumps({"data": q}).encode()
        req = urllib.request.Request(OSM_URL, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read())
    except:
        return None


# ── Module: SSL ────────────────────────────────────────────────────
def check_ssl(hostname):
    try:
        hostname = hostname.replace("https://","").replace("http://","").split("/")[0]
        ctx = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ss:
                c = ss.getpeercert()
                nb = c.get("notBefore","")
                na = c.get("notAfter","")
                iss = dict(x[0] for x in c.get("issuer",[])).get("organizationName","")
                d1 = datetime.datetime.strptime(nb, "%b %d %H:%M:%S %Y %Z")
                d2 = datetime.datetime.strptime(na, "%b %d %H:%M:%S %Y %G")
                return {"ssl_issuer": iss, "ssl_age_days": (datetime.datetime.now()-d1).days, "ssl_expires_days": (d2-datetime.datetime.now()).days}
    except:
        return {"ssl_issuer":"","ssl_age_days":None,"ssl_expires_days":None}

# ── Module: WHOIS ──────────────────────────────────────────────────
def check_whois(domain):
    try:
        import whois
        d = domain.replace("https://","").replace("http://","").split("/")[0]
        w = whois.whois(d)
        c = w.creation_date
        if isinstance(c, list): c = c[0]
        if c: return {"domain_created": str(c.date()), "domain_age_days": (datetime.datetime.now()-c).days, "domain_registrar": str(w.registrar or "")}
    except: pass
    return {"domain_created":"","domain_age_days":None,"domain_registrar":""}

# ── Module: TikTok ─────────────────────────────────────────────────
def check_tiktok(name, website):
    found = []
    for fn in TIKTOK_PATTERNS:
        h = fn(name)
        try:
            r = urllib.request.Request(f"https://www.tiktok.com/@{h}", headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(r, timeout=5) as resp:
                if resp.status == 200:
                    b = resp.read().decode("utf-8",errors="replace")[:2000]
                    if "uniqueId" in b: found.append(f"@{h}")
        except: pass
    if website:
        html = fetch(f"https://{website}" if not website.startswith("http") else website, 5)
        for u in re.findall(r'tiktok\.com/@[\w.]+', html):
            h = u.split("@")[-1].split("?")[0]
            if h and f"@{h}" not in found: found.append(f"@{h}")
    return {"tiktok_handle": ";".join(found[:3])}

# ── Module: Tech Stack ─────────────────────────────────────────────
def detect_tech(html):
    f = []
    for tech, pats in TECH_SIGS.items():
        for p in pats:
            if re.search(p, html, re.I): f.append(tech); break
    return {"tech_stack": ";".join(f[:8])}

# ── Module: Giving Platform ────────────────────────────────────────
def detect_giving(html, website):
    f = []
    for plat, sigs in GIVING_SIGS.items():
        for s in sigs:
            if s in html.lower(): f.append(plat); break
    if website:
        for p in ["/give","/giving","/donate"]:
            h = fetch(f"{website.rstrip('/')}{p}", 5)
            for plat, sigs in GIVING_SIGS.items():
                if plat not in f:
                    for s in sigs:
                        if s in h.lower(): f.append(plat); break
    return {"giving_platform": ";".join(f[:5])}

# ── Module: ADA ────────────────────────────────────────────────────
def check_ada(html, website):
    f = [k for k in ADA_KW if k in html.lower()]
    if "accessibe" in html.lower(): f.append("AccessiBe")
    if website:
        h = fetch(f"{website.rstrip('/')}/accessibility", 5)
        if any(k in h.lower() for k in ADA_KW): f.append("AccessibilityPage")
    return {"ada_accessibility": ";".join(set(f))}

# ── Module: ZeroBounce ─────────────────────────────────────────────
def check_zb(email):
    if not ZEROBOUNCE_KEY or not email: return {"email_status":"","email_score":None}
    try:
        u = f"https://api.zerobounce.net/v2/validate?api_key={ZEROBOUNCE_KEY}&email={quote(email)}"
        d = json.loads(fetch(u, 10))
        return {"email_status":d.get("status",""), "email_score":d.get("score"), "email_sub_status":d.get("sub_status","")}
    except: return {"email_status":"error","email_score":None,"email_sub_status":""}

# ── Module: OSM ────────────────────────────────────────────────────
def check_osm(lat, lng):
    if not lat or not lng: return {}
    r = {}
    # Parking
    q = f'[out:json][timeout:12];(node["amenity"="parking"](around:200,{lat},{lng});way["amenity"="parking"](around:200,{lat},{lng}););out count;'
    x = osm_query(q)
    r["parking_nearby"] = x.get("elements",[{}])[0].get("tags",{}).get("count",0) if x and x.get("elements") else 0
    # Transit
    q = f'[out:json][timeout:12];(node["highway"="bus_stop"](around:400,{lat},{lng});node["railway"="station"](around:400,{lat},{lng}););out count;'
    x = osm_query(q)
    r["transit_stops_nearby"] = x.get("elements",[{}])[0].get("tags",{}).get("count",0) if x and x.get("elements") else 0
    # Building
    q = f'[out:json][timeout:12];(way["building"](around:30,{lat},{lng}););out center tags 3;'
    x = osm_query(q)
    if x and x.get("elements"):
        b = x["elements"][0].get("tags",{})
        r["building_footprint"] = "yes"
        r["building_levels"] = b.get("building:levels","")
    else:
        r["building_footprint"] = ""
    return r

# ── Module: Density ────────────────────────────────────────────────
def check_density(lat, lng, cid):
    if not lat or not lng: return {}
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    r = {}
    for m, lbl in [(1,"1mi"),(3,"3mi"),(5,"5mi")]:
        d = m/69.0
        cur.execute("SELECT COUNT(*) FROM churches WHERE id!=? AND latitude IS NOT NULL AND ABS(latitude-?)<? AND ABS(longitude-?)<?", (cid,lat,d,lng,d))
        r[f"churches_within_{lbl}"] = cur.fetchone()[0]
    db.close()
    return r

# ── Module: Walkability ────────────────────────────────────────────
def check_walk(lat, lng):
    if not lat or not lng: return {"walkability_pois":None}
    amens = "restaurant|cafe|supermarket|convenience|pharmacy|bank|library|park|school"
    q = f'[out:json][timeout:12];(node["amenity"~"^{amens}$"](around:1000,{lat},{lng}););out count;'
    x = osm_query(q)
    c = x.get("elements",[{}])[0].get("tags",{}).get("count",0) if x and x.get("elements") else 0
    return {"walkability_pois": c}

# ── Module: Denomination lookup ────────────────────────────────────
def lookup_denom(denom):
    if not denom: return {"denom_hq":"","denom_conference":"","denom_network":""}
    k = denom.lower().strip()
    for pat, d in DENOM_DATA.items():
        if pat in k or k in pat:
            return {"denom_hq":d["hq"],"denom_conference":d["conference"],"denom_network":d["network"]}
    return {"denom_hq":"","denom_conference":"","denom_network":""}

# ── Orchestrator ───────────────────────────────────────────────────
def enrich_one(row, modules):
    cid, name, website, city, state, email = row[0], row[1], row[2], row[3] if len(row)>3 else "", row[4] if len(row)>4 else "", row[5] if len(row)>5 else ""
    lat, lng = row[6] if len(row)>6 else None, row[7] if len(row)>7 else None
    denom = row[8] if len(row)>8 else ""
    result = {"id":cid, "name":name, "website":website}
    if "ssl" in modules and website: result.update(check_ssl(website))
    if "whois" in modules and website: result.update(check_whois(website))
    if "tiktok" in modules and (website or name): result.update(check_tiktok(name, website))
    if any(m in modules for m in ["techstack","giving","ada"]) and website:
        html = fetch(f"https://{website}" if not website.startswith("http") else website)
        if html:
            if "techstack" in modules: result.update(detect_tech(html))
            if "giving" in modules: result.update(detect_giving(html, website))
            if "ada" in modules: result.update(check_ada(html, website))
    if "zerobounce" in modules and email: result.update(check_zb(email))
    if "density" in modules and lat: result.update(check_density(lat, lng, cid))
    if "osm" in modules and lat: result.update(check_osm(lat, lng))
    if "walk" in modules and lat: result.update(check_walk(lat, lng))
    if "denom" in modules and denom: result.update(lookup_denom(denom))
    return result

def save_ckpt(ids):
    with open(CHECKPOINT_FILE,"w") as f: json.dump({"processed":list(ids),"updated":str(datetime.datetime.now())},f)

def load_ckpt():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f: return set(json.load(f).get("processed",[]))
    return set()

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--chunks", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--module", default="ssl,whois,tiktok,techstack,giving,ada,density,osm,walk,denom")
    parser.add_argument("--output", default=os.path.join(OUT_DIR,"enriched_churches.csv"))
    args = parser.parse_args()
    modules = [m.strip() for m in args.module.split(",")]
    log(f"Modules: {', '.join(modules)}")

    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    q = "SELECT id, name, website, city, state, email, latitude, longitude, denomination FROM churches WHERE website IS NOT NULL AND website != '' AND latitude IS NOT NULL"
    if args.chunks: q += f" LIMIT {args.chunks}"
    cur.execute(q)
    churches = cur.fetchall()
    db.close()
    log(f"Loaded {len(churches):,} churches")

    if args.resume:
        done = load_ckpt()
        churches = [c for c in churches if c[0] not in done]
        log(f"Resume: {len(churches):,} remaining ({len(done):,} done)")

    results, t0 = [], time.time()
    for i, ch in enumerate(churches):
        results.append(enrich_one(ch, modules))
        if (i+1) % 10 == 0:
            rate = (i+1)/(time.time()-t0)
            log(f"  {i+1}/{len(churches)} ({(i+1)*100/len(churches):.0f}%) | {rate:.1f}/s")
            save_ckpt([c[0] for c in churches[:i+1]])
        if "zerobounce" in modules: time.sleep(0.2)
        if "osm" in modules: time.sleep(0.3)

    if results:
        with open(args.output,"w",newline="",encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            w.writeheader(); w.writerows(results)
        log(f"Saved {len(results):,} results to {args.output}")
    log(f"Done in {time.time()-t0:.0f}s")

if __name__ == "__main__":
    main()
