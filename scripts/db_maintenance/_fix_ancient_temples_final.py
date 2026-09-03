"""Fix ancient temples: faith=Other, faith_tradition=Hellenism/Roman/Masonic/Christian.
Using name as identifier since id=NULL for these rows.
"""
import sqlite3

DB = r"e:\grid\churches.db"
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

changes = []

# Mapping: name patterns -> (faith, faith_tradition)
classifications = [
    # Greece — Hellenic polytheism
    ("Temple of Hera, Olympia",           "Other", "Hellenism"),
    ("Second Temple of Hera in Paestum",   "Other", "Hellenism"),
    ("Temple of Hera, Paestum",            "Other", "Hellenism"),
    ("Temple E at Selinunte",              "Other", "Hellenism"),
    # Italy — Roman polytheism
    ("Temple of Minerva Medica",           "Other", "Roman"),
    # Italy — mislabeled church
    ("Temple of San Miserino",             "Christian", "Christianity"),
    # Turkey — Roman era
    ("Temple on the State Agora (Ephesus)","Other", "Roman"),
    ("Temple Nymphaeum",                   "Other", "Roman"),
    # Turkey — Masonic lodge
    ("Illuminati Masonic Temple",          "Other", "Masonic"),
]

print("=== Applying fixes ===")
for name, faith, tradition in classifications:
    c.execute("""
        UPDATE churches 
        SET faith=?, faith_tradition=?
        WHERE name LIKE ? AND source='holy_sites_import' AND faith='Hindu'
    """, (faith, tradition, f"%{name}%"))
    affected = c.rowcount
    if affected > 0:
        changes.append((name[:60], faith, tradition, affected))
        print(f"  OK: {name[:60]:60s} -> faith={faith:12s} tradition={tradition}")
    else:
        print(f"  --: {name[:60]:60s} -> NOT FOUND (already fixed?)")

conn.commit()

print(f"\n=== Summary: {len(changes)} changes ===")
for name, faith, trad, count in changes:
    print(f"  {name:60s} {faith:12s} {trad:15s} ({count} row(s))")

# Verify
print("\n=== Verification ===")
for name, faith, tradition in classifications:
    c.execute("SELECT name, faith, faith_tradition FROM churches WHERE name LIKE ?", (f"%{name}%",))
    for r in c.fetchall():
        print(f"  {r[0][:65]:65s} | {r[1]:12s} | {r[2]:15s}")

conn.close()
