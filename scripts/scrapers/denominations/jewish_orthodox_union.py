#!/usr/bin/env python3
"""
OU Orthodox Synagogue Scraper
===============================
Scrapes the OU (Orthodox Union) public API for synagogues and mikvaot.

API: https://schools-api.ouapis.org/public/community-resource
Returns: name, address, lat/lon, website, email, phone, rabbi, hashkafa, etc.

Usage:
    python scripts/scrapers/scrape_ou.py
    python scripts/scrapers/scrape_ou.py --workers 4
    python scripts/scrapers/scrape_ou.py --state NY
    python scripts/scrapers/scrape_ou.py --import-only
"""
import csv, json, os, sqlite3, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import argparse, urllib.request, urllib.parse

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
OUT_DIR = os.path.join(PROJECT_DIR, "data", "denom")
os.makedirs(OUT_DIR, exist_ok=True)

API_BASE = "https://schools-api.ouapis.org/public/community-resource"
PAGE_SIZE = 100

STATES = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA",
          "HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
          "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
          "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
          "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def log(msg):
    print("[%s] %s" % (datetime.now().strftime("%H:%M:%S"), msg))


def fetch_json(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as f:
            return json.loads(f.read().decode("utf-8"))
    except Exception as e:
        log("  FETCH ERROR: %s" % e)
        return None


def scrape_state(state, workers=4):
    """Scrape all OU synagogues/mikvaot for a single state."""
    results = []
    page = 1
    total = None
    
    while True:
        url = "%s?page=%d&limit=%d&type=synagogue&state=%s" % (API_BASE, page, PAGE_SIZE, state)
        data = fetch_json(url)
        if not data:
            break
        
        items = data.get("results", [])
        if total is None:
            total = data.get("count", 0)
        
        if not items:
            break
        
        for item in items:
            results.append(item)
        
        if len(results) >= total:
            break
        page += 1
        time.sleep(0.2)
    
    return results


def extract_fields(items):
    """Extract key fields from OU API items."""
    extracted = []
    for item in items:
        contacts = item.get("contacts") or []
        primary_contact = contacts[0] if contacts else {}
        
        geo = item.get("geo") or {}
        coords = geo.get("coordinates") or []
        
        metadata = item.get("metadata") or {}
        
        rec = {
            "name": (item.get("name") or "").strip(),
            "address": (item.get("Street") or "").strip(),
            "city": (item.get("City") or "").strip(),
            "state": (item.get("State") or "").strip(),
            "zip": (item.get("Zip") or "").strip()[:5],
            "country": (item.get("Country") or "").strip(),
            "website": (item.get("website") or "").strip(),
            "latitude": coords[1] if len(coords) >= 2 else (item.get("latitude") or ""),
            "longitude": coords[0] if len(coords) >= 2 else (item.get("longitude") or ""),
            "phone": (primary_contact.get("phone") or item.get("RabbiPhone") or "").strip(),
            "email": (primary_contact.get("email") or item.get("ShulEmail") or "").strip(),
            "rabbi_name": (item.get("RabbiName") or "").strip(),
            "associate_rabbi": (item.get("AssociateRabbiName") or "").strip(),
            "rabbi_email": (item.get("RabbiEmail") or "").strip(),
            "rabbi_phone": (item.get("RabbiPhone") or "").strip(),
            "hashkafa": (item.get("Hashkafa") or "").strip(),
            "movement": (item.get("movement") or "").strip(),
            "is_ou_member": item.get("is_ou_member") or False,
            "of_families": item.get("ofFamilies") or "",
            "members": "",
            "type": (item.get("type") or "").strip(),
            "source": "ou_api",
        }
        
        # Get members from metadata
        if metadata.get("members"):
            rec["members"] = metadata["members"]
        
        # Clean phone
        phone = rec["phone"]
        if phone:
            phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            if len(phone) >= 10:
                rec["phone"] = "(%s) %s-%s" % (phone[-10:-7], phone[-7:-4], phone[-4:])
        
        extracted.append(rec)
    
    return extracted


def save_csv(results, filename):
    """Save results to CSV."""
    fp = os.path.join(OUT_DIR, filename)
    with open(fp, "w", newline="", encoding="utf-8") as f:
        if results:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
    log("  Saved %d records to %s" % (len(results), fp))
    return fp


def import_to_db(results):
    """Import OU congregations into churches.db."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Check columns
    cols = {r[1] for r in cur.execute("PRAGMA table_info(churches)").fetchall()}
    
    inserted = 0
    skipped = 0
    for r in results:
        name = r["name"]
        city = r.get("city", "")
        state = r.get("state", "")
        website = r.get("website", "")
        
        if not name or not state:
            continue
        
        # Check existing
        existing = cur.execute(
            "SELECT id FROM churches WHERE UPPER(name)=? AND UPPER(city)=? AND state=?",
            (name.upper(), city.upper(), state)
        ).fetchone()
        
        if existing:
            # Update with website/contact if missing
            updates = []
            vals = []
            if website and "website" in cols:
                updates.append("website=COALESCE(NULLIF(website,''),?)")
                vals.append(website)
            updates.append("denomination=COALESCE(NULLIF(denomination,''),?)")
            vals.append("Orthodox")
            updates.append("faith_tradition='jewish'")
            updates.append("jewish_movement=COALESCE(NULLIF(jewish_movement,''),?)")
            vals.append("Orthodox")
            updates.append("notes=COALESCE(NULLIF(notes,''),?)")
            vals.append("Source: ou_api")
            if r.get("rabbi_name") and "pastor_name" in cols:
                updates.append("pastor_name=COALESCE(NULLIF(pastor_name,''),?)")
                vals.append(r.get("rabbi_name", ""))
            
            if updates:
                sql = "UPDATE churches SET %s WHERE id=?" % ",".join(updates)
                vals.append(existing[0])
                cur.execute(sql, vals)
            skipped += 1
        else:
            # Insert new record
            cols_list = ["name", "city", "state", "source", "faith_tradition", "jewish_movement",
                         "denomination", "notes"]
            vals_list = [name, city, state, "ou_api", "jewish", "Orthodox",
                         "Orthodox", "Source: OU API"]
            
            if r.get("address") and "address" in cols:
                cols_list.append("address")
                vals_list.append(r.get("address", ""))
            if r.get("zip") and "zip" in cols:
                cols_list.append("zip")
                vals_list.append(r.get("zip", ""))
            if website and "website" in cols:
                cols_list.append("website")
                vals_list.append(website)
            if r.get("phone") and "phone" in cols:
                cols_list.append("phone")
                vals_list.append(r.get("phone", ""))
            if r.get("email") and "email" in cols:
                cols_list.append("email")
                vals_list.append(r.get("email", ""))
            if r.get("latitude") and "latitude" in cols:
                try:
                    cols_list.append("latitude")
                    vals_list.append(float(r["latitude"]))
                except: pass
            if r.get("longitude") and "longitude" in cols:
                try:
                    cols_list.append("longitude")
                    vals_list.append(float(r["longitude"]))
                except: pass
            if r.get("rabbi_name") and "pastor_name" in cols:
                cols_list.append("pastor_name")
                vals_list.append(r.get("rabbi_name", ""))
            if r.get("members") and "attendance_est" in cols:
                try:
                    cols_list.append("attendance_est")
                    vals_list.append(int(r["members"]))
                except: pass
            
            placeholders = ",".join("?" for _ in vals_list)
            try:
                cur.execute("INSERT INTO churches (%s) VALUES (%s)" % (",".join(cols_list), placeholders),
                            vals_list)
                inserted += 1
            except Exception as e:
                log("  INSERT ERROR: %s - %s" % (name[:50], e))
    
    conn.commit()
    conn.close()
    log("  DB: %d inserted, %d updated/skipped" % (inserted, skipped))


def main():
    parser = argparse.ArgumentParser(description="OU Orthodox synagogue scraper")
    parser.add_argument("--state", help="Single state to scrape (e.g. NY)")
    parser.add_argument("--workers", type=int, default=4, help="Worker threads")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to DB")
    parser.add_argument("--import-only", action="store_true", help="Import existing CSV to DB")
    args = parser.parse_args()
    
    if args.import_only:
        fp = os.path.join(OUT_DIR, "ou_orthodox.csv")
        if os.path.exists(fp):
            with open(fp, "r", encoding="utf-8") as f:
                results = list(csv.DictReader(f))
            log("Loaded %d records from %s" % (len(results), fp))
            import_to_db(results)
        return
    
    states = [args.state] if args.state else STATES
    all_results = []
    
    for st in states:
        log("=== %s ===" % st)
        items = scrape_state(st, workers=args.workers)
        extracted = extract_fields(items)
        log("  %s: %d synagogues/mikvaot" % (st, len(extracted)))
        all_results.extend(extracted)
    
    # Save combined
    save_csv(all_results, "ou_orthodox.csv")
    
    log("\n=== Summary ===")
    log("  Total: %d congregations" % len(all_results))
    
    if not args.dry_run and all_results:
        import_to_db(all_results)
    
    log("Done!")


if __name__ == "__main__":
    main()
