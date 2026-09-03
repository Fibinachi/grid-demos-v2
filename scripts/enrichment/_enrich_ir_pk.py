"""
Enrich Iran (IR) and Pakistan (PK) records:
- Province/state assignment by lat/lon bounding boxes
- City placeholders (province capitals)
- Denomination from Overture/Wikidata categories
- Log provenance
"""
import sqlite3
from datetime import datetime, timezone

DB = 'E:/grid/churches.db'

# ============================================================
# IRAN PROVINCES (Ostans)
# ============================================================
IRAN_PROVINCES = {
    "Tehran": (35.3, 36.0, 51.0, 52.0),
    "Isfahan": (31.0, 34.5, 49.5, 56.0),
    "Fars": (27.0, 32.0, 50.5, 56.0),
    "East Azerbaijan": (36.5, 39.5, 45.0, 48.5),
    "West Azerbaijan": (36.0, 39.5, 44.0, 47.5),
    "Khorasan Razavi": (33.5, 38.0, 56.0, 62.0),
    "Khuzestan": (29.5, 33.0, 47.5, 51.0),
    "Mazandaran": (35.5, 37.0, 50.5, 54.5),
    "Gilan": (36.5, 38.5, 48.5, 50.5),
    "Kerman": (26.5, 32.0, 54.0, 60.0),
    "Sistan and Baluchestan": (25.0, 31.5, 58.0, 63.5),
    "Hormozgan": (25.5, 28.5, 52.5, 59.5),
    "Bushehr": (27.0, 30.5, 50.0, 53.0),
    "Yazd": (29.5, 35.5, 52.5, 58.5),
    "Qom": (34.0, 35.5, 50.0, 52.0),
    "Markazi": (33.5, 35.8, 48.5, 51.5),
    "Qazvin": (35.5, 37.0, 48.5, 51.0),
    "Zanjan": (35.5, 37.5, 47.0, 49.5),
    "Ardabil": (37.0, 39.5, 47.5, 49.0),
    "Hamadan": (34.0, 35.8, 47.5, 49.5),
    "Kermanshah": (33.5, 35.5, 45.0, 48.0),
    "Kurdistan": (34.5, 36.5, 45.5, 48.5),
    "Lorestan": (32.5, 34.5, 47.0, 50.0),
    "Ilam": (31.5, 34.0, 45.5, 48.0),
    "Chaharmahal and Bakhtiari": (31.0, 32.8, 49.5, 51.5),
    "Kohgiluyeh and Boyer-Ahmad": (30.0, 31.5, 50.0, 52.0),
    "North Khorasan": (36.5, 38.5, 55.5, 58.5),
    "South Khorasan": (30.5, 34.5, 56.0, 61.0),
    "Semnan": (34.5, 37.5, 51.5, 57.5),
    "Golestan": (36.5, 38.5, 54.0, 56.5),
    "Alborz": (35.5, 36.5, 50.5, 51.5),
}

IRAN_CAPITALS = {
    "Tehran": "Tehran", "Isfahan": "Isfahan", "Fars": "Shiraz",
    "East Azerbaijan": "Tabriz", "West Azerbaijan": "Urmia",
    "Khorasan Razavi": "Mashhad", "Khuzestan": "Ahvaz",
    "Mazandaran": "Sari", "Gilan": "Rasht", "Kerman": "Kerman",
    "Sistan and Baluchestan": "Zahedan", "Hormozgan": "Bandar Abbas",
    "Bushehr": "Bushehr", "Yazd": "Yazd", "Qom": "Qom",
    "Markazi": "Arak", "Qazvin": "Qazvin", "Zanjan": "Zanjan",
    "Ardabil": "Ardabil", "Hamadan": "Hamadan", "Kermanshah": "Kermanshah",
    "Kurdistan": "Sanandaj", "Lorestan": "Khorramabad", "Ilam": "Ilam",
    "Chaharmahal and Bakhtiari": "Shahr-e Kord",
    "Kohgiluyeh and Boyer-Ahmad": "Yasuj",
    "North Khorasan": "Bojnord", "South Khorasan": "Birjand",
    "Semnan": "Semnan", "Golestan": "Gorgan", "Alborz": "Karaj",
}

# ============================================================
# PAKISTAN PROVINCES
# ============================================================
PAK_PROVINCES = {
    "Punjab": (27.5, 34.5, 69.0, 75.5),
    "Sindh": (23.5, 28.5, 66.5, 71.5),
    "Khyber Pakhtunkhwa": (31.0, 37.0, 69.5, 74.5),
    "Balochistan": (24.0, 32.0, 60.0, 70.5),
    "Islamabad Capital Territory": (33.4, 33.9, 72.8, 73.4),
    "Gilgit-Baltistan": (35.0, 37.5, 72.5, 77.0),
    "Azad Kashmir": (32.5, 35.5, 73.0, 75.0),
}

PAK_CAPITALS = {
    "Punjab": "Lahore", "Sindh": "Karachi",
    "Khyber Pakhtunkhwa": "Peshawar", "Balochistan": "Quetta",
    "Islamabad Capital Territory": "Islamabad",
    "Gilgit-Baltistan": "Gilgit", "Azad Kashmir": "Muzaffarabad",
}

# Category → denomination mapping (same as CN script)
DENOM_MAP = {
    "catholic_church": "Roman Catholic",
    "baptist_church": "Baptist",
    "evangelical_church": "Evangelical",
    "pentecostal_church": "Pentecostal",
    "anglican_church": "Anglican",
    "episcopal_church": "Episcopal",
    "buddhist_temple": "Buddhist",
    "church_cathedral": "Christian",
    "mosque": None,  # Most are Sunni, but don't assume
    "hindu_temple": "Hindu",
    "sikh_temple": "Sikh",
    "synagogue": "Jewish",
}

def enrich_country(c, country_code, provinces, capitals):
    """Assign provinces and city placeholders for a country."""
    prov_assigned = 0
    for prov, (lat_min, lat_max, lon_min, lon_max) in provinces.items():
        c.execute("""UPDATE churches SET state=? WHERE country=?
            AND (state IS NULL OR state = '')
            AND latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?""",
            (prov, country_code, lat_min, lat_max, lon_min, lon_max))
        prov_assigned += c.rowcount

    print(f"  Provinces assigned: {prov_assigned}")

    city_assigned = 0
    for prov, city in capitals.items():
        c.execute("""UPDATE churches SET city=? WHERE country=?
            AND (city IS NULL OR city = '') AND state=?""",
            (city, country_code, prov))
        city_assigned += c.rowcount

    print(f"  City placeholders: {city_assigned}")
    return prov_assigned, city_assigned

def assign_denominations(c, country_code):
    """Assign denominations from source_secondary (Overture categories)."""
    denom_assigned = 0
    for src_sec, denom in DENOM_MAP.items():
        if denom is None:
            continue
        c.execute("""UPDATE churches SET denomination=? WHERE country=?
            AND (denomination IS NULL OR denomination = '') AND source_secondary=?""",
            (denom, country_code, src_sec))
        denom_assigned += c.rowcount
    print(f"  Denominations assigned: {denom_assigned}")
    return denom_assigned

def main():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()
    ts = datetime.now(timezone.utc).isoformat()

    total_updates = 0

    # ── IRAN ──
    print("=" * 60)
    print("IRAN (IR) ENRICHMENT")
    print("=" * 60)
    p, cty = enrich_country(c, "IR", IRAN_PROVINCES, IRAN_CAPITALS)
    d = assign_denominations(c, "IR")
    total_updates += p + cty + d

    # ── PAKISTAN ──
    print("\n" + "=" * 60)
    print("PAKISTAN (PK) ENRICHMENT")
    print("=" * 60)
    p, cty = enrich_country(c, "PK", PAK_PROVINCES, PAK_CAPITALS)
    d = assign_denominations(c, "PK")
    total_updates += p + cty + d

    # Log provenance
    c.execute("""INSERT INTO provenance_log
        (source, script_name, started_at, completed_at, churches_updated, fields_populated, status, notes)
        VALUES (?,?,?,?,?,?,?,?)""",
        ("manual", "enrich_ir_pk.py", ts, datetime.now(timezone.utc).isoformat(),
         total_updates, "state,city,denomination",
         "completed",
         f"IR+PK enrichment: {total_updates} field updates total"))

    conn.commit()

    # Summary
    for code, name in [("IR", "Iran"), ("PK", "Pakistan")]:
        print(f"\n--- {name} ---")
        c.execute("SELECT COUNT(*) FROM churches WHERE country=? AND state IS NOT NULL AND state != ''", (code,))
        print(f"  With province: {c.fetchone()[0]:,}")
        c.execute("SELECT COUNT(*) FROM churches WHERE country=? AND city IS NOT NULL AND city != ''", (code,))
        print(f"  With city: {c.fetchone()[0]:,}")
        c.execute("SELECT COUNT(*) FROM churches WHERE country=? AND denomination IS NOT NULL AND denomination != ''", (code,))
        print(f"  With denomination: {c.fetchone()[0]:,}")
        c.execute("SELECT COUNT(*) FROM churches WHERE country=?", (code,))
        print(f"  Total: {c.fetchone()[0]:,}")

    conn.close()
    print("\nDone.")

if __name__ == "__main__":
    main()
