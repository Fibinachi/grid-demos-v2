"""
import_churchunion.py — Deduplicate + insert churchunion CSV into SQLite.
For duplicates: logs to provenance table as 'second_source'.
Geocoding skipped during import — run batch geocode later.
"""
import csv, sqlite3, json, os, time

CSV = "E:/grid/data/churchunion_scraped.csv"
DB  = "E:/grid/churches.db"
CK  = "E:/grid/data/churchunion_import_ck.json"
BATCH_COMMIT = 5000
PROGRESS_EVERY = 10000

def load_ck():
    if os.path.exists(CK): return json.load(open(CK))
    return {'processed': 0, 'inserted': 0, 'dup': 0, 'fail': 0, 'max_id': None}

def save_ck(d):
    json.dump(d, open(CK, 'w'))

def log_duplicate(conn, db_id, ch):
    """Log that churchunion also lists this church."""
    conn.execute("""
        INSERT OR IGNORE INTO church_sources (church_id, source_name, source_url, notes)
        VALUES (?, 'churchunion_scraper', ?, 'duplicate found during churchunion import')
    """, (db_id, ch.get('url', '')))

def main():
    ck = load_ck()
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA busy_timeout=30000")

    # Build in-memory (name_lower, state_lower) -> id index
    print("Loading existing church index...")
    exist = {}  # (name_lower, state_lower) -> id
    for r in conn.execute("SELECT id, LOWER(COALESCE(name,'')), LOWER(COALESCE(state,'')) FROM churches"):
        if r[1] and r[2]: exist[(r[1], r[2])] = r[0]
    print(f"  {len(exist):,} existing (name, state) pairs")

    if ck['max_id'] is None:
        ck['max_id'] = conn.execute("SELECT COALESCE(MAX(id), 400000) FROM churches").fetchone()[0]
    max_id = ck['max_id']
    print(f"  max id: {max_id}")

    # Ensure church_sources table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS church_sources (
            church_id INTEGER, source_name TEXT, source_url TEXT, notes TEXT,
            PRIMARY KEY (church_id, source_name)
        )
    """)
    conn.commit()

    print(f"\nResume from row {ck['processed']:,}")
    print(f"  Prev: {ck['inserted']:,} ins, {ck['dup']:,} dup, {ck['fail']:,} fail")

    while True:
        if not os.path.exists(CSV):
            time.sleep(5); continue
        rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
        new = rows[ck['processed']:]

        if not new:
            # Check if scraper is done
            scraper_ck_file = "E:/grid/data/churchunion_checkpoint.json"
            done = False
            if os.path.exists(scraper_ck_file):
                sc = json.load(open(scraper_ck_file))
                done = sc.get('last_page', 0) >= sc.get('total_pages', 16512) - 2
            if done and ck['processed'] >= len(rows):
                print(f"\nDone! All {ck['processed']:,} rows processed.")
                break
            time.sleep(10)
            continue

        print(f"\n  Processing {len(new):,} new rows (CSV total: {len(rows):,})")
        inserted_batch = 0
        dup_batch = 0
        fail_batch = 0

        for i, ch in enumerate(new):
            ck['processed'] += 1
            key = (ch['name'].lower().strip(), ch['state'].lower().strip())

            if not key[0] or not key[1]:
                fail_batch += 1; ck['fail'] += 1; continue

            # Check duplicate
            db_id = exist.get(key)
            if db_id:
                log_duplicate(conn, db_id, ch)
                dup_batch += 1; ck['dup'] += 1
                continue

            # Insert without geocoding (batch geocode later)
            max_id += 1
            try:
                conn.execute("""
                    INSERT INTO churches (id, name, address, city, state, county_name, source)
                    VALUES (?, ?, ?, ?, ?, ?, 'churchunion_scraper')
                """, (max_id, ch['name'], ch['address'], ch['city'], ch['state'],
                      ch['county']))
                exist[key] = max_id
                ck['inserted'] += 1
                inserted_batch += 1
            except Exception as e:
                ck['fail'] += 1
                fail_batch += 1
                max_id -= 1

            if i % BATCH_COMMIT == BATCH_COMMIT - 1:
                conn.commit()
                save_ck(ck)
            if i % PROGRESS_EVERY == PROGRESS_EVERY - 1:
                pct = ck['processed'] / len(rows) * 100 if rows else 0
                print(f"    ... {ck['processed']:,}/{len(rows):,} ({pct:.1f}%) | {ck['inserted']:,} ins, {ck['dup']:,} dup")

        conn.commit()
        ck['max_id'] = max_id
        save_ck(ck)

        pct = ck['processed'] / len(rows) * 100 if rows else 0
        print(f"    +{inserted_batch} ins, {dup_batch} dup, {fail_batch} fail")
        print(f"    Total: {ck['inserted']:,} ins, {ck['dup']:,} dup, {ck['fail']:,} fail | {pct:.1f}% of CSV")

if __name__ == "__main__":
    main()
