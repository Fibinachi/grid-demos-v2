"""
Import ACT Heritage Register religious sites into churches.db.

Source: ACT Government Heritage Register (data.gov.au)
Entries have city/suburb but no lat/lon — will need geocoding later.
"""
import csv
import sys
import re
sys.path.insert(0, r'E:\grid')
from gw_db import connect, Provenance

CHUNK_SIZE = 500

# Religious sites from the register with known/suburb info
HERITAGE_ENTRIES = [
    # (name, suburb, faith, taxonomy_id, landmark_type, denomination)
    ("All Saints Church", "Ainslie", "Christian", 2, "church", "Anglican"),
    ("Canberra Baptist Church and Manse", "Kingston", "Christian", 2, "church", "Baptist"),
    ("Free Serbian Orthodox Church And Murals", "Forrest", "Christian", 2, "church", "Eastern Orthodox"),
    ("Greek Orthodox Church", "Kingston", "Christian", 2, "church", "Eastern Orthodox"),
    ("Holy Trinity Lutheran Church", "Turner", "Christian", 2, "church", "Lutheran"),
    ("Sacred Heart Church", "Calwell", "Christian", 2, "church", "Roman Catholic"),
    ("St Andrew's Church Precinct", "Forrest", "Christian", 2, "church", "Anglican"),
    ("St Christopher's Cathedral Precinct", "Forrest", "Christian", 2, "cathedral", "Roman Catholic"),
    ("St Edmund's Anglican Church", "Tharwa", "Christian", 2, "church", "Anglican"),
    ("St John the Baptist Church and Churchyard", "Reid", "Christian", 2, "church", "Anglican"),
    ("St Joseph's Catholic Church", "O'Connor", "Christian", 2, "church", "Roman Catholic"),
    ("St Ninian's Church", "Lyneham", "Christian", 2, "church", "Anglican"),
    ("St Paul's Church", "Griffith", "Christian", 2, "church", "Anglican"),
    ("Ukrainian Orthodox Church", "Turner", "Christian", 2, "church", "Eastern Orthodox"),
    ("Uniting Church, Reid", "Reid", "Christian", 2, "church", "Uniting Church"),
    ("Canberra Church of England Girls Grammar School - Boarding House", "Deakin", "Christian", 2, "school", "Anglican"),
    ("Canberra National Seventh Day Adventist Church", "Turner", "Christian", 2, "church", "Seventh-day Adventist"),
    ("Cuppacumbalong (De Salis) Cemetery", "Tharwa", "Other", 6, "cemetery", None),
    ("Tharwa General Cemetery", "Tharwa", "Other", 6, "cemetery", None),
    ("Weetangera Cemetery", "Weetangera", "Other", 6, "cemetery", None),
    ("Woden Cemetery", "Phillip", "Other", 6, "cemetery", None),
]


def existing_in_db(db):
    """Load existing Canberra-area church names for dedup."""
    cur = db.execute(
        "SELECT id, name, city FROM churches "
        "WHERE country='AU' AND (state='ACT' OR city LIKE '%canberra%')"
    )
    result = {}
    for r in cur.fetchall():
        key = ((r[1] or '').strip().lower(), (r[2] or '').strip().lower())
        result[key] = r
    return result


def name_similar(a, b):
    """Check if two church names are similar enough to be the same."""
    a_words = set(re.findall(r'[a-z]+', a.lower()))
    b_words = set(re.findall(r'[a-z]+', b.lower()))
    stop = {'the','and','of','in','at','a','an','for','to','st','st.','church','precinct'}
    a_sig = a_words - stop
    b_sig = b_words - stop
    if not a_sig or not b_sig:
        return False
    common = a_sig & b_sig
    return len(common) >= max(2, len(a_sig) * 0.4, len(b_sig) * 0.4)


def main():
    db = connect()
    existing = existing_in_db(db)
    print(f"Canberra-area churches already in DB: {len(existing)}")
    
    # Check which ones already exist
    to_import = []
    already_have = []
    for name, suburb, faith, tax_id, lm_type, denom in HERITAGE_ENTRIES:
        matched = False
        for (db_name, db_city), (rid, rname, rcity) in existing.items():
            if name_similar(name, db_name):
                already_have.append((name, suburb, rid, rname, rcity))
                matched = True
                break
        if not matched:
            to_import.append((name, suburb, faith, tax_id, lm_type, denom))
    
    print(f"\nAlready in DB ({len(already_have)}):")
    for n, s, rid, dn, dc in sorted(already_have, key=lambda x: x[0]):
        print(f"  {n:55s} ({s:15s}) → id={rid} db=\"{dn}\" city={dc}")
    
    print(f"\nNew to import ({len(to_import)}):")
    for n, s, faith, tax_id, lm_type, denom in to_import:
        trad_str = denom or "-"
        print(f"  {n:55s} ({s:15s}) [{lm_type:12s}] {trad_str}")
    
    if not to_import:
        print("\nNothing to import.")
        db.close()
        return
    
    # Confirm
    reply = input(f"\nImport {len(to_import)} new entries? [y/N]: ").strip().lower()
    if reply != 'y':
        print("Aborted.")
        db.close()
        return
    
    # Import
    print(f"\nImporting {len(to_import)} entries...")
    with Provenance(db, source="act_heritage_register", action="inserted",
                    fields="name,city,country,state,faith,taxonomy_id,landmark_type,tradition",
                    records_attempted=len(to_import)) as prov:
        
        for i in range(0, len(to_import), CHUNK_SIZE):
            batch = to_import[i:i+CHUNK_SIZE]
            for name, suburb, faith, tax_id, lm_type, trad in batch:
                try:
                    cur = db.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM churches")
                    next_id = cur.fetchone()[0]
                    
                    db.execute("""
                        INSERT INTO churches
                            (id, name, city, country, state, faith, taxonomy_id,
                             landmark_type, tradition, source)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        next_id, name, suburb, 'AU', 'ACT',
                        faith, tax_id, lm_type, trad or 'Unknown',
                        'act_heritage_register'
                    ))
                    prov.churches_inserted += 1
                    
                except Exception as ex:
                    print(f"  ERROR: {name[:50]} - {ex}")
            
            db.commit()
            print(f"  Batch {i//CHUNK_SIZE + 1} committed ({prov.churches_inserted} total)")
    
    print(f"\nDone! {prov.churches_inserted} entries imported.")
    db.close()


if __name__ == '__main__':
    main()
