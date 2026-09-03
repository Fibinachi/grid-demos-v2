"""Import overture_mexico_new.csv and overture_canada_new.csv into churches.db.
Already have coordinates from Overture — no geocoding needed. Fast bulk import."""
import csv, sqlite3, json, os, time

DB = "E:/grid/churches.db"
FILES = [
    ("E:/grid/data/overture_canada_new.csv", "CA", "overture_canada"),
    ("E:/grid/data/overture_mexico_new.csv", "MX", "overture_mexico"),
]

def main():
    db = sqlite3.connect(DB, timeout=60)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=OFF")
    db.execute("PRAGMA cache_size=-1000000")  # 1GB cache
    
    # Build in-memory index
    print("Loading name/state index...")
    exist = {}
    for r in db.execute("SELECT id, LOWER(COALESCE(name,'')), LOWER(COALESCE(state,'')) FROM churches"):
        if r[1] and r[2]: exist[(r[1], r[2])] = r[0]
    print(f"  {len(exist):,} pairs indexed")
    
    max_id = db.execute("SELECT COALESCE(MAX(id), 800000) FROM churches").fetchone()[0]
    
    # Ensure tables
    db.execute("CREATE TABLE IF NOT EXISTS church_sources (church_id INTEGER, source_name TEXT, source_url TEXT, notes TEXT, PRIMARY KEY (church_id, source_name))")
    db.commit()
    
    for csv_path, country, source_tag in FILES:
        if not os.path.exists(csv_path):
            print(f"\n{csv_path} not found, skipping")
            continue
        
        rows = list(csv.DictReader(open(csv_path, encoding="utf-8")))
        total = len(rows)
        print(f"\n=== {country}: {total:,} rows from {os.path.basename(csv_path)} ===")
        
        inserted = 0
        dup = 0
        fail = 0
        start = time.time()
        
        for i, ch in enumerate(rows):
            name = (ch.get('name') or '').strip()
            state = (ch.get('state') or '').strip()
            key = (name.lower(), state.lower())
            
            if not key[0] or not key[1]:
                fail += 1; continue
            
            db_id = exist.get(key)
            if db_id:
                try:
                    db.execute("INSERT OR IGNORE INTO church_sources (church_id, source_name, source_url, notes) VALUES (?, ?, ?, ?)",
                              (db_id, source_tag, ch.get('overture_id', ''), 'overture continent import'))
                except: pass
                dup += 1; continue
            
            try:
                lat = float(ch.get('latitude', 0) or 0)
                lon = float(ch.get('longitude', 0) or 0)
            except:
                lat = lon = 0
            
            max_id += 1
            try:
                db.execute("""
                    INSERT INTO churches (id, name, address, city, state, zip,
                        country, latitude, longitude, geocode_source, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'overture', ?)
                """, (max_id, name, ch.get('address', '') or '', ch.get('city', '') or '',
                      state, ch.get('zip', '') or '', country, lat, lon, source_tag))
                exist[key] = max_id
                inserted += 1
            except Exception:
                fail += 1
                max_id -= 1
            
            if i % 10000 == 9999:
                db.commit()
                elapsed = time.time() - start
                pct = (i + 1) / total * 100
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (total - i - 1) / rate if rate > 0 else 0
                print(f"  {i+1:,}/{total:,} ({pct:.0f}%), {inserted:,} ins, {dup:,} dup, {rate:.0f}/s, ETA {eta/60:.0f}m")
        
        db.commit()
        elapsed = time.time() - start
        print(f"  Done {country}: {inserted:,} ins, {dup:,} dup, {fail:,} fail in {elapsed/60:.1f}m")
    
    total_db = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
    mx_db = db.execute("SELECT COUNT(1) FROM churches WHERE country='MX'").fetchone()[0]
    ca_db = db.execute("SELECT COUNT(1) FROM churches WHERE country='CA'").fetchone()[0]
    print(f"\nFinal DB: {total_db:,} total | MX: {mx_db:,} | CA: {ca_db:,}")
    db.close()

if __name__ == "__main__":
    main()
