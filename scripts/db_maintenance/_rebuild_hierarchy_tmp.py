"""
Rebuild ahmadiyya_hierarchy on a temp DB copy, then swap.
"""
import sqlite3, os, shutil, json
from collections import defaultdict
from datetime import datetime, timezone

SRC = "churches.db"
TMP = "churches_tmp.db"

def main():
    if not os.path.exists(TMP):
        print("ERROR: churches_tmp.db not found!")
        return

    conn = sqlite3.connect(TMP, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()

    # Get all Ahmadiyya entries
    c.execute("""
        SELECT rowid, id, name, city, state, country, latitude, longitude, denomination
        FROM churches 
        WHERE (muslim_affiliation='Ahmadiyya' OR taxonomy_id = 26)
          AND name IS NOT NULL
        ORDER BY country, city
    """)
    rows = c.fetchall()
    print(f"Total Ahmadiyya entries: {len(rows)}")

    # Find World HQ: Baitul Futuh Mosque, Morden
    world_hq = None
    for r in rows:
        nu = (r[2] or "").upper()
        if "BAITUL FUTUH" in nu:
            world_hq = r
            break
    if not world_hq:
        for r in rows:
            nu = (r[2] or "").upper()
            if r[5] == "GB" and "LONDON MOSQUE" in nu:
                world_hq = r
                break
    if not world_hq:
        uk = [r for r in rows if r[5] == "GB"]
        if uk:
            world_hq = uk[0]

    if not world_hq:
        print("ERROR: No world HQ found!")
        return

    print(f"World HQ: rowid={world_hq[0]} | {(world_hq[2] or '').encode('ascii', errors='replace').decode('ascii')} | {world_hq[3] or ''}, {world_hq[5]}")

    # Group by country
    by_country = defaultdict(list)
    for r in rows:
        by_country[r[5] or "??"].append(r)

    # Identify national HQs
    nat_kw = ["CENTER", "CENTRE", "MISSION", "ASSOCIATION", "MOVEMENT", "NATIONAL"]
    national_hqs = {}
    for cc, entries in by_country.items():
        if cc == "GB":
            continue
        candidates = [(r, kw) for r in entries for kw in nat_kw if kw in ((r[2] or "").upper())]
        if candidates:
            national_hqs[cc] = candidates[0][0]
        else:
            national_hqs[cc] = max(entries, key=lambda r: len(r[2] or "") + len(r[3] or "") + len(r[4] or ""))

    # Create table
    c.execute("DROP TABLE IF EXISTS ahmadiyya_hierarchy")
    c.execute("""
        CREATE TABLE ahmadiyya_hierarchy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER REFERENCES ahmadiyya_hierarchy(id),
            church_id INTEGER,
            name TEXT NOT NULL,
            original_name TEXT,
            ahmadiyya_type TEXT NOT NULL CHECK(ahmadiyya_type IN (
                'hq', 'national_hq', 'regional_office', 'mosque', 'mission', 'center', 'school', 'other'
            )),
            ahmadiyya_detail TEXT,
            city TEXT, state TEXT, country TEXT, lat REAL, lon REAL,
            parent_ahmadiyya_type TEXT,
            relationship TEXT CHECK(relationship IN ('affiliated_with', 'administered_by')),
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    print("Created ahmadiyya_hierarchy table on temp DB")

    seen = set()
    def ins(parent_id, church_id, name, a_type, detail, city, state, country, lat, lon, ptype, rel, notes=None):
        key = (church_id, parent_id, rel)
        if key in seen:
            return None
        seen.add(key)
        c.execute("""
            INSERT INTO ahmadiyya_hierarchy
                (parent_id, church_id, name, original_name, ahmadiyya_type, ahmadiyya_detail,
                 city, state, country, lat, lon, parent_ahmadiyya_type, relationship, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (parent_id, church_id, name or "", name or "", a_type, detail,
              city, state, country, lat, lon, ptype, rel, notes))
        return c.lastrowid

    # World HQ
    hq_id = ins(None, world_hq[1], world_hq[2], 'hq',
                'Global HQ - Baitul Futuh Mosque, seat of Khalifatul Masih',
                world_hq[3], world_hq[4], world_hq[5], world_hq[6], world_hq[7],
                None, None, "Ahmadiyya Muslim Community global HQ - London, UK")
    print(f"World HQ: id={hq_id}")

    rowid_map = {world_hq[0]: hq_id}

    # National HQs
    for cc, nr in sorted(national_hqs.items()):
        if nr[0] in rowid_map:
            continue
        hid = ins(hq_id, nr[1], nr[2], 'national_hq', f"National HQ -- {cc}",
                  nr[3], nr[4], nr[5], nr[6], nr[7],
                  'hq', 'administered_by', f"National HQ for {cc}")
        if hid:
            rowid_map[nr[0]] = hid

    # Remaining entries
    ins_count = 0
    for r in rows:
        rowid, cid, name, city, state, country = r[0], r[1], r[2], r[3], r[4], r[5]
        if rowid in rowid_map:
            continue

        is_nat = rowid in [v[0] for v in national_hqs.values()]
        nu = (name or "").upper()
        if "MISSION" in nu:
            a_type = 'mission'
        elif "CENTER" in nu or "CENTRE" in nu:
            a_type = 'center'
        elif "MOSQUE" in nu or "MASJID" in nu:
            a_type = 'mosque'
        elif "SCHOOL" in nu:
            a_type = 'school'
        elif any(kw in nu for kw in ["JAMA", "GEMEINDE", "COMMUNIT", "ASSOCIATION"]):
            a_type = 'center'
        else:
            a_type = 'other'
        if is_nat:
            a_type = 'national_hq'

        if country == "GB" or country not in national_hqs:
            parent_id, ptype, rel = hq_id, 'hq', 'affiliated_with'
            notes = "Affiliated with world HQ"
        else:
            pid = rowid_map.get(national_hqs[country][0], hq_id)
            parent_id, ptype, rel = pid, 'national_hq', 'affiliated_with'
            notes = f"Affiliated with {country} national HQ"

        hid = ins(parent_id, cid, name, a_type, None, city, state, country,
                  r[6], r[7], ptype, rel, notes)
        if hid:
            rowid_map[rowid] = hid
            ins_count += 1

    conn.commit()

    # Verify
    c.execute("SELECT COUNT(*) FROM ahmadiyya_hierarchy")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM ahmadiyya_hierarchy WHERE parent_id IS NULL")
    roots = c.fetchone()[0]
    print(f"\nTotal: {total}, Roots: {roots}, Linked: {total - roots}")

    print("\nBy Type:")
    c.execute("SELECT ahmadiyya_type, COUNT(*) FROM ahmadiyya_hierarchy GROUP BY ahmadiyya_type ORDER BY COUNT(*) DESC")
    for r in c.fetchall():
        print(f"  {r[0]}: {r[1]}")

    print("\nBy Country:")
    c.execute("SELECT country, COUNT(*) FROM ahmadiyya_hierarchy WHERE country != '' GROUP BY country ORDER BY COUNT(*) DESC")
    for r in c.fetchall():
        print(f"  {r[0]:5s}: {r[1]}")

    print("\n=== HQ Chain ===")
    c.execute("""
        SELECT h.id, h.ahmadiyya_type, h.name, h.country, h.city
        FROM ahmadiyya_hierarchy h
        WHERE h.ahmadiyya_type IN ('hq', 'national_hq')
        ORDER BY h.ahmadiyya_type DESC, h.country
    """)
    for r in c.fetchall():
        name_safe = (r[2] or "").encode("ascii", errors="replace").decode("ascii")[:65]
        print(f"  id={r[0]:>3} [{r[1]:12s}] {name_safe:<65} ({r[4] or ''}, {r[3]})")

    conn.close()

    # Swap DBs
    print("\nSwapping temp DB into place...")
    shutil.move(TMP, SRC)
    print("Done! churches.db replaced with temp DB containing hierarchy.")

if __name__ == "__main__":
    main()
