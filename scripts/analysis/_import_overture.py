"""Import Overture results into the DB (no website_source column)"""
import sqlite3, csv

DB = r'E:\grid\churches.db'
UPD = r'E:\grid\data\overture_updates.csv'
NEW = r'E:\grid\data\overture_new.csv'

db = sqlite3.connect(DB)

def esc(x):
    return x.replace(chr(39), chr(39)*2)

# ── 1. Import updates (website + phone + address for existing churches) ──
updated = 0
with open(UPD, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        db_id = r['db_id']
        website = (r.get('website') or '').strip()
        phone = (r.get('phone') or '').strip()
        address = (r.get('address') or '').strip()
        
        parts = ["website_scrape_status='verified'", "website_last_verified=datetime('now')",
                 "website_confidence=0.95"]
        if website:
            parts.append(f"website='{esc(website)}'")
        if phone:
            parts.append(f"phone='{esc(phone)}'")
        if address:
            parts.append(f"address='{esc(address)}'")
        
        db.execute(f"UPDATE churches SET {', '.join(parts)} WHERE id=?", (db_id,))
        updated += 1
        if updated % 500 == 0:
            db.commit()

db.commit()
print(f"Updated {updated:,} existing churches with Overture data")

# ── 2. Import new churches ──
inserted = 0
updated_existing = 0
with open(NEW, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        name = (r.get('name') or '').strip()
        website = (r.get('website') or '').strip()
        phone = (r.get('phone') or '').strip()
        address = (r.get('address') or '').strip()
        city = (r.get('city') or '').strip()
        state = (r.get('state') or '').strip()
        zipcode = (r.get('zip') or '').strip()
        
        if not name:
            continue
        
        existing = db.execute(
            "SELECT id, website FROM churches WHERE name=? AND state=? AND city=?",
            (name, state, city)
        ).fetchone()
        
        if existing:
            if website and not existing[1]:
                db.execute("UPDATE churches SET website=?, website_scrape_status='verified', website_last_verified=datetime('now') WHERE id=?", (website, existing[0]))
                updated_existing += 1
        else:
            db.execute("""INSERT INTO churches (name, website, phone, address, city, state, zip,
                website_scrape_status, website_confidence, website_last_verified, source)
                VALUES (?,?,?,?,?,?,?,'verified',0.95,datetime('now'),'overture_discovery')""",
                (name, website, phone, address, city, state, zipcode if zipcode else None))
            inserted += 1
        
        if (inserted + updated_existing) % 500 == 0:
            db.commit()

db.commit()
print(f"Added {inserted:,} new churches, updated {updated_existing:,} existing with websites")

w = db.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''").fetchone()[0]
v = db.execute("SELECT COUNT(*) FROM churches WHERE website_scrape_status='verified'").fetchone()[0]
t = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
print(f"\nFinal: {t:,} total churches, {w:,} with websites ({v:,} verified)")
db.close()
