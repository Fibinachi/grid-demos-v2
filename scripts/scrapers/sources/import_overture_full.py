"""
Import overture_churches_new.csv into churches.db.
All churches already have coordinates from Overture — no geocoding needed.
Deduplication by (name_lower, state_lower).
"""
import csv, sqlite3, json, os, time

CSV = "E:/grid/data/overture_churches_new.csv"
DB  = "E:/grid/churches.db"
CK  = "E:/grid/data/overture_import_ck.json"

def load_ck():
    if os.path.exists(CK): return json.load(open(CK))
    return {'processed': 0, 'inserted': 0, 'dup': 0, 'fail': 0, 'max_id': None}

def save_ck(d):
    json.dump(d, open(CK, 'w'))

def main():
    ck = load_ck()
    conn = sqlite3.connect(DB, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=OFF")
    conn.execute("PRAGMA busy_timeout=30000")

    # Build existing index
    print("Loading existing church index...")
    exist = {}
    for r in conn.execute("SELECT id, LOWER(COALESCE(name,'')), LOWER(COALESCE(state,'')) FROM churches"):
        if r[1] and r[2]: exist[(r[1], r[2])] = r[0]
    print(f"  {len(exist):,} existing (name, state) pairs")

    if ck['max_id'] is None:
        ck['max_id'] = conn.execute("SELECT COALESCE(MAX(id), 400000) FROM churches").fetchone()[0]
    max_id = ck['max_id']
    print(f"  max id: {max_id}")

    # Ensure church_sources table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS church_sources (
            church_id INTEGER, source_name TEXT, source_url TEXT, notes TEXT,
            PRIMARY KEY (church_id, source_name)
        )
    """)
    conn.commit()

    # Read CSV
    rows = list(csv.DictReader(open(CSV, encoding="utf-8")))
    total = len(rows)
    new_rows = rows[ck['processed']:]
    print(f"\nProcessing {len(new_rows):,} rows (CSV total: {total:,})")
    if ck['processed'] > 0:
        print(f"  Prev: {ck['inserted']:,} ins, {ck['dup']:,} dup, {ck['fail']:,} fail")

    inserted_batch = 0
    dup_batch = 0
    fail_batch = 0

    for i, ch in enumerate(new_rows):
        ck['processed'] += 1
        name = (ch.get('name') or '').strip()
        state = (ch.get('state') or '').strip()
        key = (name.lower(), state.lower())

        if not key[0] or not key[1]:
            fail_batch += 1; ck['fail'] += 1; continue

        # Check duplicate
        db_id = exist.get(key)
        if db_id:
            # Log duplicate
            try:
                conn.execute("""
                    INSERT OR IGNORE INTO church_sources (church_id, source_name, source_url, notes)
                    VALUES (?, 'overture_full', ?, 'duplicate found during overture full import')
                """, (db_id, ch.get('overture_id', '')))
            except:
                pass
            dup_batch += 1; ck['dup'] += 1
            continue

        # Insert new church (coordinates already from Overture)
        try:
            lat = float(ch.get('latitude', 0) or 0)
            lon = float(ch.get('longitude', 0) or 0)
            if lat == 0 and lon == 0:
                fail_batch += 1; ck['fail'] += 1; continue
        except:
            fail_batch += 1; ck['fail'] += 1; continue

        max_id += 1
        try:
            conn.execute("""
                INSERT INTO churches (id, name, address, city, state,
                    latitude, longitude, geocode_source, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'overture', 'overture_full')
            """, (max_id, name, ch.get('address', '') or '', ch.get('city', '') or '',
                  state, lat, lon))
            exist[key] = max_id
            ck['inserted'] += 1
            inserted_batch += 1
        except Exception as e:
            fail_batch += 1; ck['fail'] += 1
            max_id -= 1

        if i % 5000 == 4999:
            conn.commit()
            save_ck(ck)
            pct = ck['processed'] / total * 100
            print(f"  ... {ck['processed']:,}/{total:,} ({pct:.1f}%) | {ck['inserted']:,} ins, {ck['dup']:,} dup")

    conn.commit()
    ck['max_id'] = max_id
    save_ck(ck)

    pct = ck['processed'] / total * 100 if total else 0
    print(f"\nDone! {ck['inserted']:,} ins, {ck['dup']:,} dup, {ck['fail']:,} fail | {pct:.1f}%")

    total_db = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
    overture_count = conn.execute("SELECT COUNT(*) FROM churches WHERE source='overture_full'").fetchone()[0]
    print(f"DB total: {total_db:,} | Overture full: {overture_count:,}")

    conn.close()

if __name__ == "__main__":
    main()
