"""Import Saudi Arabia mosques from Wikipedia List of mosques in Saudi Arabia.
Source: https://en.wikipedia.org/wiki/List_of_mosques_in_Saudi_Arabia
CC BY-SA 4.0 licensed.
Dedupes by name + city against existing churches."""
import sqlite3, re
from datetime import datetime, timezone

DB = r"E:\grid\churches.db"
SOURCE = "wikipedia_sa_mosques"
SCRIPT = "_import_wikipedia_sa_mosques"

conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

# ── Mosques from Wikipedia table ──
# (name, city_original, era, notes)
MOSQUES = [
    ("Great Mosque of Mecca", "Mecca", "Era of Ibrahim", "Islam's holiest site, surrounds the Kaaba"),
    ("Masjid al-Haram", "Mecca", "Era of Ibrahim", "Alternate name for Great Mosque of Mecca"),
    ("Prophet's Mosque", "Medina", "622", "Second-holiest site in Islam"),
    ("Masjid an-Nabawi", "Medina", "622", "Alternate name for Prophet's Mosque"),
    ("Quba Mosque", "Medina", "622", "First mosque built by Muhammad"),
    ("Masjid al-Qiblatayn", "Medina", "623", "Where qiblah direction was changed to Mecca"),
    ("Al Jum'ah Mosque", "Medina", "622", ""),
    ("Al-Ijabah Mosque", "Medina", "622", ""),
    ("Jawatha Mosque", "Jawatha", "629", "Part of UNESCO Al-Ahsa Oasis"),
    ("Abd Allah ibn al-Abbas Mosque", "Taif", "630", "Burial site of Ibn Abbas"),
    ("Abu Bakr Mosque", "Medina", "705-709", "c.91 AH"),
    ("Mosque of Al-Ghamama", "Medina", "712", ""),
    ("Bay'ah Mosque", "Mecca", "761", ""),
    ("An-Namirah Mosque", "Wadi Uranah", "9th century", "Near Jabal Arafat, Hajj site"),
    ("Masjid al-Namirah", "Wadi Uranah", "9th century", "Alternate for An-Namirah"),
    ("Al Qantara Mosque", "Taif", "1856", "Ottoman-era mosque"),
    ("Anbariya Mosque", "Medina", "1908", ""),
    ("Al-Rahmah Mosque", "Jeddah", "1985", "Floating mosque on Red Sea"),
    ("King Saud Mosque", "Jeddah", "1987", ""),
    ("Sayyid Ash-Shuhada Mosque", "Medina", "2017", "Near grave of Hamza at Mount Uhud"),
    ("Masjid Bilal ibn Rabah", "Badr", "2019", ""),
    ("Abdulaziz Abdullah Sharbatly Mosque", "Jeddah", "2024", "World's first 3D-printed mosque"),
    ("Al-Ji'ranah Mosque", "Al-Ji'rana", "?", "Boundary of Haram of Makkah"),
    ("Addas Mosque", "Taif", "?", "Named after Addas, Iraqi Christian who embraced Islam"),
    ("Aisha Mosque", "At-Tan'eem", "?", ""),
    ("Masjid Aisha", "At-Tan'eem", "?", "Alternate for Aisha Mosque"),
    ("Ajyad Mosque", "Mecca", "?", ""),
    ("Alowidah Mosque", "Riyadh", "?", ""),
    ("Al Hamra Mosque", "Medina", "?", ""),
    ("Al-Ejabah Mosque", "Mecca", "?", ""),
    ("Al-Fuqair Mosque", "Medina", "?", ""),
    ("Al Malik Fahd Mosque", "Jeddah", "?", ""),
    ("Al-Khaif Mosque", "Mina", "?", "Largest mosque in Mina, Hajj site"),
    ("Al-Mash'ar Al-Haram", "Muzdalifah", "?", "Hajj site"),
    ("Al-Rayah Mosque", "Medina", "?", ""),
    ("As-Sabaq Mosque", "Medina", "?", ""),
    ("As-Sajadah Mosque", "Medina", "?", ""),
    ("Bani Bayadhah Mosque", "Medina", "?", ""),
    ("Bani Harithah Mosque", "Medina", "?", ""),
    ("Bin Laden Mosque", "Jeddah", "?", ""),
    ("Faqi Mosque", "Mecca", "?", ""),
    ("Fas'h Mosque", "Medina", "?", ""),
    ("Hassan Enany Mosque", "Jeddah", "?", ""),
    ("Manartain Mosque", "Medina", "?", ""),
    ("Masjid-u-Shajarah", "Medina", "?", ""),
    ("Mosque of Al-Fadeekh", "Medina", "?", ""),
    ("Mosque of Al-Saqiya", "Medina", "?", ""),
    ("Mosque of Atban Bin Malik", "Medina", "?", ""),
    ("Mosque of Bani Haram", "Medina", "?", ""),
    ("The Seven Mosques", "Medina", "?", ""),
    ("Al-Arish Mosque", "Medina", "?", ""),
    ("Al-Deraa Mosque", "Medina", "?", ""),
]

# ── Normalize city to SA cities ──
CITY_MAP = {
    "Mecca": "Mecca", "Medina": "Medina", "Jeddah": "Jeddah",
    "Taif": "Taif", "Riyadh": "Riyadh", "Badr": "Badr",
    "Jawatha": "Hofuf", "Wadi Uranah": "Mecca", "Al-Ji'rana": "Mecca",
    "At-Tan'eem": "Mecca", "Mina": "Mecca", "Muzdalifah": "Mecca",
}

# ── Get max ID ──
max_id = c.execute("SELECT MAX(id) FROM churches").fetchone()[0]
print(f"Max church ID: {max_id:,}")

# ── Insert ──
imported = 0
skipped = 0
errors = 0

for name, city_raw, era, notes in MOSQUES:
    city = CITY_MAP.get(city_raw, city_raw)
    
    # Check for existing by name + country
    existing = c.execute(
        "SELECT id, name FROM churches WHERE name=? AND country='SA'",
        (name,)
    ).fetchone()
    
    if existing:
        print(f"  SKIP (exists): {name} (id={existing[0]})")
        skipped += 1
        continue
    
    # Also check fuzzy match
    fuzzy = c.execute(
        "SELECT id, name FROM churches WHERE country='SA' AND name LIKE ?",
        (f"%{name}%",)
    ).fetchall()
    if fuzzy:
        print(f"  SKIP (fuzzy): {name} -> {fuzzy[0][1]} (id={fuzzy[0][0]})")
        skipped += 1
        continue
    
    # Insert
    max_id += 1
    try:
        c.execute("""
            INSERT INTO churches (id, name, city, country, faith, tradition,
                landmark_type, source_primary, building_year, 
                culture_id, faith_id,
                last_updated, source)
            VALUES (?, ?, ?, 'SA', 'Islam', 'Sunni', 
                'mosque', ?, ?,
                555, 4,
                ?, ?)
        """, (max_id, name, city, SOURCE, 
               era if era != '?' else None,
               datetime.now(timezone.utc).isoformat(), SCRIPT))
        print(f"  ADD: {name} ({city}, era={era})")
        imported += 1
    except Exception as e:
        print(f"  ERROR: {name} - {e}")
        errors += 1
        max_id -= 1

conn.commit()

print(f"\n=== Import complete ===")
print(f"  Imported: {imported}")
print(f"  Skipped (exists): {skipped}")
print(f"  Errors: {errors}")

conn.close()
