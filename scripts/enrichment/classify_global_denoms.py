"""Classify hidden denominations found in global scan."""
import sqlite3

DB = "E:/grid/churches.db"

# (prefix, full_name, parent_node, country)
DENOMS = [
    # Indonesia (continued)
    ("GMAHK", "Gereja Masehi Advent Hari Ketujuh", "Adventist", "ID"),
    ("GBKP", "Gereja Batak Karo Protestan", "Reformed", "ID"),
    ("GSJA", "Gereja Sidang-Sidang Jemaat Allah", "Pentecostal", "ID"),
    ("GKPI", "Gereja Kristen Protestan Indonesia", "Protestant", "ID"),
    ("GKPS", "Gereja Kristen Protestan Simalungun", "Protestant", "ID"),
    ("GKII", "Gereja Kemah Injil Indonesia", "Protestant", "ID"),
    ("GPI", "Gereja Protestan Indonesia", "Protestant", "ID"),
    ("GMI", "Gereja Methodist Indonesia", "Methodist", "ID"),
    # Brazil
    ("IASD", "Igreja Adventista do Setimo Dia", "Adventist", "BR"),
    ("IEQ", "Igreja do Evangelho Quadrangular", "Pentecostal", "BR"),
    ("CCB", "Congregacao Crista no Brasil", "Pentecostal", "BR"),
    ("IIGD", "Igreja Internacional da Graca de Deus", "Pentecostal", "BR"),
    ("IEAD", "Igreja Evangelica Assembleia de Deus", "Pentecostal", "BR"),
    # India
    ("CSI", "Church of South India", "Protestant", "IN"),
    ("IPC", "Indian Pentecostal Church", "Pentecostal", "IN"),
    # Philippines
    ("UCCP", "United Church of Christ in the Philippines", "Protestant", "PH"),
    # Nigeria
    ("ECWA", "Evangelical Church Winning All", "Protestant", "NG"),
    # Madagascar
    ("FJKM", "Fiangonan'i Jesoa Kristy eto Madagasikara", "Reformed", "MG"),
    # Colombia
    ("IPUC", "Iglesia Pentecostal Unida de Colombia", "Pentecostal", "CO"),
    # DR Congo
    ("ENA", "Eglise Nationale", "Protestant", "CD"),
]

db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row

# Make sure necessary parent taxonomy nodes exist
needed_parents = set(d[2] for d in DENOMS)
parent_ids = {}
for pname in needed_parents:
    r = db.execute("SELECT id FROM taxonomy WHERE name=? LIMIT 1", (pname,)).fetchone()
    if r:
        parent_ids[pname] = r["id"]
    else:
        # Create under Protestant if it doesn't exist
        prot = db.execute("SELECT id FROM taxonomy WHERE name='Protestant' LIMIT 1").fetchone()
        if not prot:
            print(f"ERROR: Protestant node not found!")
            exit()
        pinfo = db.execute("SELECT * FROM taxonomy WHERE id=?", (prot["id"],)).fetchone()
        max_id = db.execute("SELECT MAX(id) FROM taxonomy").fetchone()[0]
        new_id = max_id + 1
        db.execute("""
            INSERT INTO taxonomy (id, name, parent_id, full_path, depth, root_id, tradition_id, family_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (new_id, pname, prot["id"], pinfo["full_path"] + "/" + pname,
              pinfo["depth"] + 1, pinfo["root_id"], pinfo["tradition_id"], pinfo["family_id"]))
        parent_ids[pname] = new_id
        print(f"  Created parent: {pname} (id={new_id})")

db.commit()

total = 0
for prefix, full_name, parent_name, country in DENOMS:
    pid = parent_ids[parent_name]
    
    r = db.execute("SELECT id FROM taxonomy WHERE name=? AND parent_id=?", (full_name, pid)).fetchone()
    if r:
        tax_id = r["id"]
    else:
        parent = db.execute("SELECT * FROM taxonomy WHERE id=?", (pid,)).fetchone()
        max_id = db.execute("SELECT MAX(id) FROM taxonomy").fetchone()[0]
        tax_id = max_id + 1
        db.execute("""
            INSERT INTO taxonomy (id, name, parent_id, full_path, depth, root_id, tradition_id, family_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (tax_id, full_name, pid, parent["full_path"] + "/" + full_name,
              parent["depth"] + 1, parent["root_id"], parent["tradition_id"], parent["family_id"]))
    
    before = db.total_changes
    db.execute("""
        UPDATE churches SET taxonomy_id=?, last_updated=datetime('now')
        WHERE country=? AND name LIKE ? AND taxonomy_id IN (2,3,6)
    """, (tax_id, country, f"{prefix} %"))
    count = db.total_changes - before
    total += count
    if count:
        print(f"  {prefix} ({country}): {count:,} -> {full_name}")

db.commit()

# Verify
print(f"\nTotal: {total:,}")
for prefix, full_name, _, country in DENOMS:
    r = db.execute("SELECT COUNT(1) FROM churches WHERE country=? AND name LIKE ? AND taxonomy_id IN (2,3,6)", (country, f"{prefix} %")).fetchone()
    if r[0] > 0:
        print(f"  STILL GENERIC: {prefix} ({country}): {r[0]}")

db.close()
