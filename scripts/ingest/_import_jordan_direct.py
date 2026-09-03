"""
Simple Jordan mosque import: parse raw_jordan_mosques JSON → insert into churches.
Different governorates have different Arabic column names — parse them all.
"""
import json, sys, re
sys.path.insert(0, r"E:\grid")
from gw_db import connect

db = connect()

# Read raw data
raw = db.execute("SELECT id, raw_data, source FROM raw_jordan_mosques").fetchall()
print(f"Raw records: {len(raw):,}")

# Arabic column name variants for mosque names
NAME_COLS = [
    "اسم المسجد ", "اسم المسجد", "المسجد", "مسجد",
]
CITY_COLS = [
    "المدينة", "مدينة", "المنطقة", "اللواء", "مكان المسجد", "عنوان المسجد", "تقسيم اداري"
]

parsed = []
for row_id, raw_data, source in raw:
    if not raw_data:
        continue
    try:
        d = json.loads(raw_data)
    except:
        continue
    
    name = ""
    city = ""
    phone = ""
    
    # Find name
    for key in d:
        key_clean = key.strip()
        if any(nc in key_clean for nc in NAME_COLS):
            val = str(d[key]).strip()
            if val and val not in ("nan", "None", "", "NaN"):
                name = val
                break
    
    # Find city
    for key in d:
        key_clean = key.strip()
        if any(cc in key_clean for cc in CITY_COLS):
            val = str(d[key]).strip()
            if val and val not in ("nan", "None", "", "NaN"):
                city = val
                break
    
    # Find phone (any column with "هاتف" or "جوال")
    for key in d:
        key_clean = key.strip()
        if "هاتف" in key_clean or "جوال" in key_clean:
            val = str(d[key]).strip()
            if val and val not in ("nan", "None", "", "NaN") and len(val) >= 7:
                phone = re.sub(r'[^\d+]', '', val)
                break
    
    # Also try "رقم المسجد" as a fallback city identifier  
    if not city:
        for key in d:
            key_clean = key.strip()
            if "رقم" in key_clean and "مسجد" in key_clean:
                continue  # This is a mosque number, not city
    
    if name:
        parsed.append({
            "name": name, 
            "city": city or "Jordan", 
            "phone": phone,
            "source": source or "jordan_mosques"
        })

print(f"Parsed names: {len(parsed):,}")

# Import into churches
max_id = db.execute("SELECT COALESCE(MAX(CAST(id AS INTEGER)), 0) FROM churches").fetchone()[0]
print(f"Starting from id: {max_id+1:,}")

imported = 0
with_phone = 0
for i, p in enumerate(parsed):
    new_id = max_id + imported + 1
    try:
        db.execute("""
            INSERT INTO churches (id, name, city, country, landmark_type, faith, source)
            VALUES (?, ?, ?, 'JO', 'mosque', 'Islam', ?)
        """, (str(new_id), p["name"], p["city"], p["source"]))
        imported += 1
        
        # Add phone contact if available
        if p["phone"]:
            db.execute("""
                INSERT INTO church_contact_values (church_id, contact_type, value, source, confidence)
                VALUES (?, 'phone', ?, 'jordan_mosques', 0.85)
            """, (str(new_id), p["phone"]))
            with_phone += 1
            
    except Exception as e:
        if imported < 5:
            print(f"  ERROR: {p['name'][:50]} - {e}")

    if (i + 1) % 500 == 0:
        db.commit()
        print(f"  {i+1:,}/{len(parsed):,}", flush=True)

db.commit()

# Log provenance
db.execute("""
    INSERT INTO provenance_log (source, script_name, row_count, started_at, completed_at, status)
    VALUES ('jordan_mosques', '_import_jordan_direct.py', ?, datetime('now'), datetime('now'), 'completed')
""", (imported,))
db.commit()

print(f"\nDone: {imported:,} mosques imported, {with_phone:,} with phone contacts")
db.close()
