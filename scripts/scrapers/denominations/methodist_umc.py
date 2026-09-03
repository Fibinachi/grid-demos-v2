#!/usr/bin/env python3
"""UMC Conference Church Scraper - scrapes annual conference directories."""
import csv, json, os, re, sqlite3, sys, time, urllib.request
from datetime import datetime
from threading import Lock

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    if os.path.exists(os.path.join(PROJECT_DIR, "churches.db")):
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
OUT_DIR = os.path.join(PROJECT_DIR, "data", "denom")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_CSV = os.path.join(OUT_DIR, "umc_churches.csv")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
log_lock = Lock()

def log(msg):
    with log_lock:
        print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))

def fetch(url, timeout=20):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(r, timeout=timeout) as f:
            return f.read().decode("utf-8", "replace")
    except:
        return None

def clean_name(raw):
    s = re.sub(r'&nbsp;|&#\d+;|&amp;|&lt;|&gt;|&quot;', ' ', raw)
    return re.sub(r'\s+', ' ', s).strip()

def parse_church(raw, default_state):
    """Parse 'City, ST - Church Name', return (name, state, city)."""
    raw = clean_name(raw)
    if not raw or len(raw) < 5:
        return None, default_state, ""
    m = re.match(r'^([A-Za-z\s.]+),\s*(AL|AK|AZ|AR|CA|CO|CT|DE|DC|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\s*[–\-]\s*(.+)$', raw)
    if m:
        return m.group(3).strip(), m.group(2), m.group(1).strip()
    return raw, default_state, ""

def is_church(name):
    if not name or len(name) < 5:
        return False
    skip = ["facebook","twitter","instagram","youtube","login","donate","give",
            "cart","search","sitemap","blog","events","calendar","sermon",
            "staff","directory","copyright","handbook","book of","discipline",
            "resolution","church locator","find a church","church directory",
            "local church","church conference","church resources","immigration",
            "all rights","subscribe","sign up","password","username"]
    nl = name.lower()
    if any(s in nl for s in skip):
        return False
    if "church" not in nl and "methodist" not in nl:
        return False
    return True

def extract(html, state_hint):
    results = []
    seen = set()
    for m in re.finditer(r'<a\s+[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>\s*([^<]{5,150}?)\s*</a>', html, re.IGNORECASE):
        href = m.group(1).strip()
        name, state, city = parse_church(m.group(2), state_hint)
        if not name or not is_church(name):
            continue
        key = name.lower().strip()
        if key not in seen:
            seen.add(key)
            results.append((name[:80], href, state, city))
    return results[:500]

def find_dirs(html, base_url):
    dirs = []
    for m in re.finditer(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', html, re.IGNORECASE):
        href, text = m.group(1).strip(), m.group(2).strip().lower().replace(" ","")
        hl = href.lower()
        for p in ["findachurch","churchdirectory","churches","congregation",
                  "locator","ourchurches","churchlist","churchlocator"]:
            if p in text or p in hl:
                if href.startswith("/"):
                    from urllib.parse import urlparse
                    pu = urlparse(base_url)
                    href = f"{pu.scheme}://{pu.netloc}{href}"
                elif not href.startswith("http"):
                    href = base_url.rstrip("/") + "/" + href.lstrip("/")
                dirs.append(href)
                break
    return list(set(dirs))[:5]

CONFS = [
    ("GNJ UMC", "https://www.gnjumc.org", "NJ"),
    ("NY Annual Conf", "https://www.nyac.com", "NY"),
    ("Eastern PA Conf", "https://www.epaumc.org", "PA"),
    ("Susquehanna Conf", "https://www.susumc.org", "PA"),
    ("North GA Conf", "https://www.ngumc.org", "GA"),
    ("South GA Conf", "https://www.sgaumc.org", "GA"),
    ("AL-W FL Conf", "https://awfumc.org", "AL"),
    ("North AL Conf", "https://www.northalabamaumc.org", "AL"),
    ("MS Conf", "https://www.mississippi-umc.org", "MS"),
    ("TN-W KY Conf", "https://www.twkumc.org", "TN"),
    ("KY Conf", "https://www.kyumc.org", "KY"),
    ("SC Conf", "https://www.umcsc.org", "SC"),
    ("Western NC Conf", "https://www.wnccumc.org", "NC"),
    ("NC Conf", "https://www.nccumc.org", "NC"),
    ("Holston Conf", "https://holston.org", "TN"),
    ("VA Conf", "https://www.vaumc.org", "VA"),
    ("West OH Conf", "https://www.westohioumc.org", "OH"),
    ("East OH Conf", "https://www.eastohioumc.com", "OH"),
    ("IN Conf", "https://www.inumc.org", "IN"),
    ("IL Great Rivers", "https://www.igrc.org", "IL"),
    ("Northern IL Conf", "https://www.umcnic.org", "IL"),
    ("MI Conf", "https://www.michiganumc.org", "MI"),
    ("WI Conf", "https://www.wumc.org", "WI"),
    ("MN Conf", "https://www.minnesotaumc.org", "MN"),
    ("IA Conf", "https://www.iaumc.org", "IA"),
    ("MO Conf", "https://www.moumethodist.org", "MO"),
    ("NE Conf", "https://www.umcnebraska.org", "NE"),
    ("Dakotas Conf", "https://www.dakotasumc.org", "SD"),
    ("Central TX Conf", "https://www.ctcumc.org", "TX"),
    ("North TX Conf", "https://www.ntcumc.org", "TX"),
    ("NW TX Conf", "https://www.nwtxumc.org", "TX"),
    ("Rio TX Conf", "https://www.riotexas.org", "TX"),
    ("TX Conf", "https://www.txcumc.org", "TX"),
    ("OK Conf", "https://www.okumc.org", "OK"),
    ("AR Conf", "https://www.arumc.org", "AR"),
    ("LA Conf", "https://www.la-umc.org", "LA"),
    ("NM Conf", "https://www.nmconfumc.com", "NM"),
    ("CA-NV Conf", "https://www.cnumc.org", "CA"),
    ("CA-Pac Conf", "https://www.calpacumc.org", "CA"),
    ("OR-ID Conf", "https://www.umoi.org", "OR"),
    ("PNW Conf", "https://www.pnwumc.org", "WA"),
    ("Desert SW Conf", "https://www.dscumc.org", "AZ"),
    ("Rocky Mtn Conf", "https://www.rmcumc.org", "CO"),
    ("Yellowstone", "https://www.yellowstoneumc.org", "MT"),
]

def scrape_one(name, url, state):
    r = {"conference": name, "url": url, "state": state, "churches": [], "error": ""}
    html = fetch(url)
    if not html:
        r["error"] = "fail"
        return r
    r["churches"] = extract(html, state)
    for d in find_dirs(html, url)[:3]:
        time.sleep(1.0)
        dh = fetch(d)
        if dh:
            r["churches"].extend(extract(dh, state))
    seen = set()
    uniq = []
    for n, u, s, c in r["churches"]:
        k = n.lower()
        if k not in seen:
            seen.add(k)
            uniq.append((n, u, s, c))
    r["churches"] = uniq
    return r

def normalize(name):
    """Normalize a church name for fuzzy matching."""
    n = name.upper().strip()
    n = re.sub(r"'S\b", "S", n)
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r'\s+', ' ', n).strip()
    for prefix in ["THE ", "FIRST ", "SAINT ", "ST ", "MT ", "MOUNT "]:
        if n.startswith(prefix):
            n = n[len(prefix):]
    for suffix in [" UNITED METHODIST CHURCH", " METHODIST CHURCH", " UMC",
                   " UNITED METHODIST", " BAPTIST CHURCH"]:
        if n.endswith(suffix):
            n = n[:-len(suffix)]
    for prefix in ["UNITED METHODIST CHURCH OF ", "UNITED METHODIST CHURCH ",
                   "FIRST UNITED METHODIST CHURCH OF ", "FIRST UNITED METHODIST "]:
        if n.startswith(prefix):
            n = n[len(prefix):]
    return n.strip()

def do_import(results):
    """Import into DB, matching by city+state first, then normalized name."""
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    matched, inserted = 0, 0
    new_rows = []
    
    for r in results:
        for name, url, st, city in r["churches"]:
            state = st or r["state"]
            norm = normalize(name)
            
            # Strategy 1: Exact name + state match
            cur.execute("SELECT id, denomination, city FROM churches WHERE name=? AND state=? LIMIT 1", (name, state))
            row = cur.fetchone()
            
            # Strategy 2: City + state + normalized name fragment
            if not row and city:
                city_u = city.upper().strip()
                # Find churches in this city+state
                cur.execute("SELECT id, name, denomination, city FROM churches WHERE state=? AND city LIKE ? LIMIT 10",
                          (state, f"%{city_u}%"))
                candidates = cur.fetchall()
                if len(candidates) == 1:
                    row = candidates[0]  # Only one church in this city
                elif len(candidates) > 1:
                    # Multiple churches in city - match by normalized name keywords
                    norm_words = set(norm.split())
                    best = None
                    best_score = 0
                    for cid, cname, cdenom, ccity in candidates:
                        cnorm = normalize(cname)
                        cwords = set(cnorm.split())
                        overlap = len(norm_words & cwords)
                        if overlap > best_score:
                            best_score = overlap
                            best = (cid, cdenom, ccity)
                    if best and best_score >= 2:
                        row = best
            
            # Strategy 3: Normalized name + state match
            if not row and len(norm) > 3:
                cur.execute("SELECT id, denomination, city, name FROM churches WHERE name LIKE ? AND state=? LIMIT 1",
                          (f"%{norm}%", state))
                row = cur.fetchone()
            
            # Strategy 4: First significant word + state
            if not row and len(norm) > 5:
                words = [w for w in norm.split() if w not in ("UNITED", "METHODIST", "CHURCH", "UMC", "THE", "A", "OF", "AND", "IN")]
                if words:
                    cur.execute("SELECT id, denomination, city, name FROM churches WHERE name LIKE ? AND state=? AND name LIKE ? LIMIT 1",
                              (f"%{words[0]}%", state, f"%{norm[:25]}%"))
                    row = cur.fetchone()
            
            if row:
                matched += 1
                cid, denom, db_city = row[0], row[1], row[2]
                up, pa = [], []
                if not denom:
                    up.append("denomination=?")
                    pa.append("United Methodist Church")
                up.append("conference=COALESCE(NULLIF(conference,''),?)")
                pa.append(r["conference"])
                if city and not db_city:
                    up.append("city=COALESCE(NULLIF(city,''),?)")
                    pa.append(city)
                if up:
                    pa.append(cid)
                    cur.execute(f"UPDATE churches SET {', '.join(up)} WHERE id=?", pa)
            else:
                inserted += 1
                new_rows.append((name, url if url.startswith("http") else "", city, state, r["conference"]))
                cur.execute("INSERT INTO churches (name, website, city, state, conference, denomination, source) VALUES (?,?,?,?,?,?,?)",
                          (name, url if url.startswith("http") else "", city, state, r["conference"], "United Methodist Church", "umc_scrape"))
        db.commit()
    db.close()
    return matched, inserted, new_rows

def main():
    test = "--test" in sys.argv
    confs = CONFS[:5] if test else CONFS
    log(f"UMC Scraper ({'test' if test else str(len(confs))} confs)")
    results = []
    for i, (n, u, s) in enumerate(confs):
        log(f"  [{i+1}/{len(confs)}] {n} -> {u}")
        r = scrape_one(n, u, s)
        log(f"    found={len(r['churches'])} err={r['error'] or 'ok'}")
        results.append(r)
        time.sleep(1.5)
    total = sum(len(r["churches"]) for r in results)
    working = sum(1 for r in results if r["churches"])
    log(f"\n=== RESULTS ===\n  Scraped: {len(results)}, working: {working}\n  Churches found: {total}")
    if total > 0:
        m, ins, new = do_import(results)
        log(f"  Imported: {m} matched, {ins} new")
        if new:
            with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["name","website","city","state","conference"])
                w.writerows(new)
            log(f"  New churches saved to {OUT_CSV}")

if __name__ == "__main__":
    main()
