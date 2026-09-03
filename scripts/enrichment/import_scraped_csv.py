#!/usr/bin/env python3
"""
Generic CSV/JSON Import for Denom Scrapers
==========================================
Imports CSV or JSONL files from data/denom/ into local SQLite.
Auto-detects column mapping.

Usage:
    python scripts/enrichment/import_scraped_csv.py data/denom/sbc_churches.csv --denom "Southern Baptist Convention"
    python scripts/enrichment/import_scraped_csv.py data/denom/jw_churches.jsonl --denom "Jehovah's Witnesses"
    python scripts/enrichment/import_scraped_csv.py data/denom/*.csv --denom "Auto-detect"
    python scripts/enrichment/import_scraped_csv.py data/denom/sda_churches.jsonl --denom "Seventh-day Adventist" --dry-run
"""
import csv, json, os, re, sqlite3, sys, glob
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
for _ in range(5):
    dbpath = os.path.join(PROJECT_DIR, "churches.db")
    if os.path.exists(dbpath) and os.path.getsize(dbpath) > 1024:
        break
    parent = os.path.dirname(PROJECT_DIR)
    if parent == PROJECT_DIR:
        break
    PROJECT_DIR = parent

DB_PATH = os.path.join(PROJECT_DIR, "churches.db")

NAME_KEYS = ["name", "church_name", "church", "congregation", "parish", "organization", "title"]
ADDR_KEYS = ["address", "street", "street_address", "location", "full_address"]
CITY_KEYS = ["city", "town", "municipality"]
STATE_KEYS = ["state", "state_code", "province", "region"]
ZIP_KEYS = ["zip", "zip_code", "postal_code", "postcode"]
PHONE_KEYS = ["phone", "telephone", "phone_number", "tel", "contact_phone"]
WEB_KEYS = ["website", "url", "site", "web", "church_url", "web_site"]
EMAIL_KEYS = ["email", "e_mail", "email_address", "contact_email"]
PASTOR_KEYS = ["pastor", "pastor_name", "clergy", "priest", "minister", "lead_pastor", "senior_pastor"]
LAT_KEYS = ["lat", "latitude"]
LON_KEYS = ["lon", "lng", "longitude", "long"]

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def find_key(row, keys):
    for k in keys:
        if k in row and row[k] and str(row[k]).strip():
            return str(row[k]).strip()
    return ""

def detect_denom_from_filename(filepath):
    """Try to detect denomination from filename."""
    name = os.path.basename(filepath).lower()
    mapping = {
        "sbc": "Southern Baptist Convention",
        "jw": "Jehovah's Witnesses",
        "sda": "Seventh-day Adventist",
        "rca": "Reformed Church in America",
        "cma": "Christian and Missionary Alliance",
        "pca": "Presbyterian Church in America",
        "goarch": "Greek Orthodox Archdiocese of America",
        "acna": "Anglican Church in North America",
        "cog": "Church of God (Cleveland, TN)",
        "opc": "Orthodox Presbyterian Church",
        "ame": "African Methodist Episcopal Church",
        "umc": "United Methodist Church",
        "catholic": "Roman Catholic Church",
        "jewish": "Jewish",
        "ou": "Orthodox Union",
        "fwb": "Free Will Baptist",
        "arp": "Associate Reformed Presbyterian",
        "baptist": "Baptist (unspecified)",
    }
    for key, denom in mapping.items():
        if key in name:
            return denom
    return None

def load_csv(filepath):
    rows = []
    with open(filepath, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def load_jsonl(filepath):
    rows = []
    with open(filepath, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except:
                    pass
    return rows

def import_file(filepath, denom_override=None, dry_run=False):
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".csv":
        rows = load_csv(filepath)
    elif ext == ".jsonl":
        rows = load_jsonl(filepath)
    else:
        log(f"  SKIP {filepath}: unsupported format")
        return 0, 0

    denom = denom_override or detect_denom_from_filename(filepath)
    log(f"  {os.path.basename(filepath)}: {len(rows):,} records, denom={denom}")

    if not rows:
        return 0, 0

    db = sqlite3.connect(DB_PATH, timeout=60)
    matched, inserted = 0, 0

    for row in rows:
        name = find_key(row, NAME_KEYS)
        city = find_key(row, CITY_KEYS)
        state = find_key(row, STATE_KEYS)
        if not name or not state:
            continue

        existing = db.execute("""
            SELECT id FROM churches
            WHERE LOWER(name) = LOWER(?) AND LOWER(COALESCE(city,'')) = LOWER(?) AND state = ?
            LIMIT 1
        """, (name, city, state)).fetchone()

        if existing:
            if not dry_run:
                db.execute("""UPDATE churches SET
                    denomination = COALESCE(NULLIF(denomination,''), ?),
                    family = COALESCE(NULLIF(family,''), ?),
                    website = CASE WHEN (website = '' OR website IS NULL) AND ? != '' THEN ? ELSE website END,
                    phone = CASE WHEN (phone = '' OR phone IS NULL) AND ? != '' THEN ? ELSE phone END,
                    last_updated = datetime('now')
                    WHERE id = ?""",
                    (denom, denom,
                     find_key(row, WEB_KEYS), find_key(row, WEB_KEYS),
                     find_key(row, PHONE_KEYS), find_key(row, PHONE_KEYS),
                     existing[0]))
            matched += 1
        else:
            if not dry_run:
                db.execute("""INSERT INTO churches
                    (name, address, city, state, zip, faith_tradition, family, denomination,
                     website, phone, email, pastor_name, latitude, longitude, source, last_updated)
                    VALUES (?,?,?,?,?,'christian',?,?,
                            ?,?,?,?,?,?,'csv_import',datetime('now'))""",
                    (name,
                     find_key(row, ADDR_KEYS), city, state, find_key(row, ZIP_KEYS),
                     denom, denom,
                     find_key(row, WEB_KEYS), find_key(row, PHONE_KEYS), find_key(row, EMAIL_KEYS),
                     find_key(row, PASTOR_KEYS),
                     find_key(row, LAT_KEYS) or None, find_key(row, LON_KEYS) or None))
            inserted += 1

    if not dry_run:
        db.commit()
    db.close()

    log(f"    → {matched} matched, {inserted} new")
    return matched, inserted

def main():
    dry_run = "--dry-run" in sys.argv
    denom_override = None
    files = []

    for a in sys.argv[1:]:
        if a == "--dry-run":
            continue
        if a.startswith("--denom="):
            denom_override = a.split("=", 1)[1]
        elif a.startswith("--denom"):
            continue  # handled below
        else:
            files.extend(glob.glob(a))

    if "--denom" in sys.argv:
        idx = sys.argv.index("--denom")
        if idx + 1 < len(sys.argv) and not sys.argv[idx + 1].startswith("--"):
            denom_override = sys.argv[idx + 1]

    if not files:
        files = glob.glob(os.path.join(PROJECT_DIR, "data", "denom", "*.csv")) + \
                glob.glob(os.path.join(PROJECT_DIR, "data", "denom", "*.jsonl"))

    log(f"Importing {len(files)} file(s), dry_run={dry_run}, denom_override={denom_override}")
    total_m, total_i = 0, 0
    for fp in sorted(files):
        m, i = import_file(fp, denom_override, dry_run)
        total_m += m
        total_i += i

    log(f"\nTotal: {total_m} matched, {total_i} new records")

if __name__ == "__main__":
    main()
