#!/usr/bin/env python3
"""
Denomination Directory Scraper — runs in series, one directory at a time
========================================================================
Scrapes denomination directory websites for church listings + pastors.
Outputs CSV per directory + combined results.

Usage:
    python3 denom_scraper.py                          # Run all
    python3 denom_scraper.py --dirs episcopal,umc,sbc  # Specific only
    python3 denom_scraper.py --limit 10                # First 10 pages

Dirs: sbc, elca, pcusa, umc, lcms, ag, catholic, adventist, episcopal
"""
import csv, json, os, re, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime

OUT = os.path.expanduser("~/denom_results")
os.makedirs(OUT, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def get(url):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(r, timeout=15) as f:
            raw = f.read()
            return raw.decode("utf-8", "replace")
    except Exception as e:
        return None

def getj(url):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(r, timeout=15) as f:
            raw = f.read()
            return json.loads(raw.decode("utf-8-sig"))
    except Exception as e:
        return None

# ─── SBC (WP-JSON API — WORKS) ───
def sbc(limit=0):
    print("  [SBC] sbc.net/churches (WP-JSON)...")
    out, p = [], 1
    while True:
        d = getj(f"https://churches.sbc.net/wp-json/wp/v2/church?per_page=100&page={p}")
        if not d or len(d)==0: break
        for c in d:
            title = c.get("title",{}).get("rendered","")
            link = c.get("link","")
            # Scrape individual page for address/pastor
            html = None
            if link:
                html = get(link)
            city, state, pastor = "", "", ""
            if html:
                m = re.search(r'city["\':]+([^"\'<,]+)', html, re.I)
                if m: city = m.group(1).strip()
                m = re.search(r'state["\':]+([^"\'<,]+)', html, re.I)
                if m: state = m.group(1).strip()[:2]
                m = re.search(r'(?:lead_pastor|pastor)["\':]+([^"\'<,]+)', html, re.I)
                if m: pastor = m.group(1).strip()
            out.append({"n":title,"w":"","ci":city,"st":state,"pa":pastor,"ph":""})
        print(f"    p{p}={len(out)}")
        if limit and len(out)>=limit: break
        p+=1; time.sleep(0.3)
    return out

# ─── ELCA ───
def elca(limit=0):
    print("  [ELCA] elca.org/find...")
    h = get("https://elca.org/find")
    if not h: return []
    out = []
    for m in re.finditer(r'<h3[^>]*>(.*?)</h3>.*?href="(https?://[^"]*)"', h, re.DOTALL):
        out.append({"n":m.group(1).strip(),"w":m.group(2).strip(),"ci":"","st":"","pa":"","ph":""})
    return out

# ─── UMC ───
def umc(limit=0):
    print("  [UMC] findachurch.umc.org...")
    h = get("https://www.umc.org/find-a-church/search?per_page=100")
    out = []
    if not h: return out
    for m in re.finditer(r'<h3[^>]*>(.*?)</h3>.*?href="(https?://[^"]*)"', h, re.DOTALL):
        out.append({"n":m.group(1).strip(),"w":m.group(2).strip(),"ci":"","st":"","pa":"","ph":""})
    return out

# ─── AG ───
def ag(limit=0):
    print("  [AG] ag.org/churches...")
    h = get("https://ag.org/churches")
    out = []
    if not h: return out
    for m in re.finditer(r'<h4[^>]*>(.*?)</h4>.*?href="(https?://[^"]*)"', h, re.DOTALL):
        out.append({"n":m.group(1).strip(),"w":m.group(2).strip(),"ci":"","st":"","pa":"","ph":""})
    return out

# ─── Adventist ───
def adventist(limit=0):
    print("  [Adventist] adventist.org...")
    h = get("https://www.adventist.org/find-a-church/")
    out = []
    if not h: return out
    for m in re.finditer(r'<h3[^>]*>(.*?)</h3>.*?<div class="pastor"[^>]*>(.*?)</div>', h, re.DOTALL):
        out.append({"n":m.group(1).strip(),"w":"","ci":"","st":"","pa":m.group(2).strip(),"ph":""})
    return out

# ⚠ LCMS — auth-gated, needs Playwright. Skipping for now.
def lcms(limit=0):
    print("  [LCMS] SKIPPED — API requires authentication")
    return []

# ⚠ Episcopal — Drupal + Leaflet/ESRI maps. Needs ArcGIS investigation. Skipping for now.
def episcopal(limit=0):
    print("  [Episcopal] SKIPPED — map data via ESRI/Leaflet, needs Playwright")
    return []

# ⚠ PCUSA — Changed endpoint. Needs update.
def pcusa(limit=0):
    print("  [PCUSA] SKIPPED — need updated endpoint")
    return []

# ⚠ Catholic — Changed endpoint.
def catholic(limit=0):
    print("  [Catholic] SKIPPED — need updated endpoint")
    return []

SCRAPERS = [
    ("SBC", sbc, "Southern Baptist Convention"),
    ("ELCA", elca, "Evangelical Lutheran Church in America"),
    ("UMC", umc, "United Methodist Church"),
    ("AG", ag, "Assemblies of God"),
    ("Adventist", adventist, "Seventh-day Adventist"),
    # ⚠ LCMS — needs auth
    # ⚠ Episcopal — needs ArcGIS/Leaflet investigation
    # ⚠ PCUSA — endpoint changed
    # ⚠ Catholic — endpoint changed
]

def main():
    import argparse, sqlite3
    parser = argparse.ArgumentParser()
    parser.add_argument("--dirs", help="Comma-separated: sbc,elca,pcusa,umc,lcms,ag,catholic,adventist,episcopal")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--db", help="SQLite DB path for direct update (optional)")
    args = parser.parse_args()

    filt = None
    if args.dirs:
        filt = set(d.strip().lower() for d in args.dirs.split(","))

    sel = [(a,f,d) for a,f,d in SCRAPERS if not filt or a.lower() in filt]
    print(f"Scraping {len(sel)} directories in series...\n")

    # Connect to DB if provided
    db = None
    if args.db:
        db = sqlite3.connect(args.db)
        db.execute("PRAGMA journal_mode=WAL")  # Allow concurrent reads

    all_r = {}
    total = 0

    for abbr, fn, desc in sel:
        print(f"[{datetime.now().strftime('%H:%M')}] {abbr}: {desc}")
        try:
            c = fn(limit=args.limit)
        except Exception as e:
            print(f"  ERROR: {e}")
            c = []
        print(f"  -> {len(c):,} churches")
        all_r[abbr] = c
        total += len(c)

        if c:
            for x in c[:3]:
                print(f"     {x['n'][:45]:45s} ci={x.get('ci','')[:15]:15s} st={x.get('st','')} pa={x.get('pa','')[:20] if x.get('pa') else 'N/A':20s}")

        # ─── Match & update DB ───
        if db:
            matched = 0
            for church in c:
                name = church.get("n", "").strip()
                city = church.get("ci", "").strip()
                state = church.get("st", "").strip()
                website = church.get("w", "").strip()
                pastor = church.get("pa", "").strip()

                if not name:
                    continue

                # Try matching by name + state + city
                row = db.execute(
                    "SELECT id, website, denomination FROM churches WHERE name=? AND state=? AND city=? LIMIT 1",
                    (name, state, city)
                ).fetchone()

                if row:
                    cid, existing_web, existing_denom = row
                    updates = []
                    if website and not existing_web:
                        updates.append(f"website='{website.replace(chr(39), chr(39)*2)}'")
                        updates.append("website_scrape_status='found'")
                        updates.append("website_source='denom_directory'")
                        updates.append("website_confidence=0.8")
                    if pastor:
                        # Add to church_staff table
                        try:
                            db.execute("""
                                INSERT OR IGNORE INTO church_staff (church_id, name, role, source, confidence, last_updated)
                                VALUES (?, ?, 'Pastor', 'denom_directory', 80, datetime('now'))
                            """, (cid, pastor))
                        except:
                            pass
                    # Update denomination if we know the denom from the directory
                    if not existing_denom and abbr != "":
                        denom_map = {
                            "SBC": "Southern Baptist Convention",
                            "ELCA": "Evangelical Lutheran Church in America",
                            "UMC": "United Methodist Church",
                            "AG": "Assemblies of God",
                            "Adventist": "Seventh-day Adventist Church",
                        }
                        denom_name = denom_map.get(abbr)
                        if denom_name:
                            updates.append(f"denomination='{denom_name.replace(chr(39), chr(39)*2)}'")
                            updates.append("classification_source=CASE WHEN classification_source='' OR classification_source IS NULL THEN 'denom_directory' ELSE classification_source||',denom_directory' END")
                    if updates:
                        db.execute(f"UPDATE churches SET {', '.join(updates)} WHERE id=?", (cid,))
                        matched += 1
                else:
                    # No match found — this is a NEW church
                    # Insert as a discovery
                    try:
                        db.execute("""
                            INSERT INTO churches (name, website, city, state, denomination, source, website_source, website_scrape_status)
                            VALUES (?, ?, ?, ?, ?, 'denom_directory', 'denom_directory', 'found')
                        """, (name, website, city, state, 
                              {"SBC":"Southern Baptist Convention","ELCA":"Evangelical Lutheran Church in America",
                               "UMC":"United Methodist Church","AG":"Assemblies of God",
                               "Adventist":"Seventh-day Adventist Church"}.get(abbr, "")))
                        new_id = db.lastrowid
                        if pastor:
                            db.execute("""
                                INSERT INTO church_staff (church_id, name, role, source, confidence)
                                VALUES (?, ?, 'Pastor', 'denom_directory', 80)
                            """, (new_id, pastor))
                    except:
                        pass

            db.commit()
            print(f"  DB: {matched} matched + updated")

        # CSV output (always)
        csv_p = os.path.join(OUT, f"{abbr.lower()}.csv")
        with open(csv_p, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(["name","website","city","state","pastor","phone"])
            for x in c:
                w.writerow([x.get("n",""), x.get("w",""), x.get("ci",""), x.get("st",""), x.get("pa",""), x.get("ph","")])
        print(f"  Saved: {csv_p}")
        time.sleep(1)

    # Combined CSV
    p = os.path.join(OUT, "all_denom.csv")
    with open(p, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(["denom","name","website","city","state","pastor","phone"])
        for abbr, churches in all_r.items():
            for x in churches:
                w.writerow([abbr, x.get("n",""), x.get("w",""), x.get("ci",""), x.get("st",""), x.get("pa",""), x.get("ph","")])

    if db:
        # Log to provenance
        db.execute("""
            INSERT INTO provenance_log (source, script_name, completed_at, churches_updated, fields_populated, status, notes)
            VALUES (?, 'denom_scraper.py', datetime('now'), ?, 'denomination,website,pastor', 'running', ?)
        """, (("+".join(a for a,_,_ in sel)), total, f"Denom directories: {', '.join(f'{a}({len(all_r[a])})' for a in all_r)}"))
        db.commit()
        db.close()

    print(f"\n{'='*50}")
    print(f"TOTAL: {total:,} churches from {len(sel)} dirs")
    print(f"Combined: {p}")


if __name__ == "__main__":
    main()
