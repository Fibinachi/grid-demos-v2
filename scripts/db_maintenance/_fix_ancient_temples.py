"""Fix ancient temple misclassifications → Hellenism / Roman.
Handles: Greek temples (GR + Greek colonies in IT), Roman temples (IT + TR),
         Masonic temples, Christian temples mis-ID'd, actual Hindu temples in diaspora.
"""
import sqlite3, datetime

DB = r"e:\grid\churches.db"
TS = datetime.datetime.now().isoformat()

conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

changes = []

def classify_and_fix(country, greek_ind, roman_ind, christian_ind, masonic_ind, hindu_ind):
    q = """
        SELECT id, name, country FROM churches
        WHERE faith='Hindu' AND source='holy_sites_import'
            AND country=?
            AND LOWER(name) LIKE '%temple%'
    """
    c.execute(q, (country,))
    for row in c.fetchall():
        cid, name, ctry = row
        name_lower = name.lower() if name else ""

        if any(ind in name_lower for ind in hindu_ind):
            continue  # Already correctly tagged

        if any(ind in name_lower for ind in masonic_ind):
            c.execute("UPDATE churches SET faith='Other', faith_tradition='Masonic' WHERE id=?", (cid,))
            changes.append((cid, "faith", "Hindu", "Other", f"Masonic: {name[:60]}"))

        elif any(ind in name_lower for ind in christian_ind):
            c.execute("UPDATE churches SET faith='Christian', faith_tradition='Christianity' WHERE id=?", (cid,))
            changes.append((cid, "faith", "Hindu", "Christian", f"Church: {name[:60]}"))

        elif any(ind in name_lower for ind in greek_ind):
            c.execute("UPDATE churches SET faith='Hellenism', faith_tradition='Hellenism' WHERE id=?", (cid,))
            changes.append((cid, "faith", "Hindu", "Hellenism", f"Greek temple: {name[:60]} ({ctry})"))

        elif any(ind in name_lower for ind in roman_ind):
            c.execute("UPDATE churches SET faith='Roman', faith_tradition='Roman' WHERE id=?", (cid,))
            changes.append((cid, "faith", "Hindu", "Roman", f"Roman temple: {name[:60]} ({ctry})"))

        else:
            print(f"  UNCLASSIFIED: ID={cid} | {name[:70]:70s} | {ctry}")

HINDU_IND = [
    "mandir", "iskcon", "krishna", "shiva", "vishnu", "ganesh", "ram ",
    "swami", "sai", "amman", "murugan", "devi", "lakshmi", "durga", "kali",
    "ayyappa", "hanuman", "sri ", "shri", "varageeswarar",
    "pooja", "satsang", "bhagwan", "baba", "mandapam", "swamy",
    "jagannath", "radha", "govind", "gopala", "narayan",
]

GREEK_IND = [
    "temple of hera", "temple of zeus", "temple of athena",
    "temple of apollo", "temple of artemis", "temple of poseidon",
    "temple of demeter", "temple of dionysus", "temple of hephaestus",
    "temple of aphrodite", "temple of olympian zeus",
    "temple of athena nike",
    "selinunte",
    "paestum",
]

ROMAN_IND = [
    "temple of minerva", "temple of juno", "temple of jupiter",
    "temple of mars", "temple of venus", "temple of saturn",
    "temple of vesta", "temple of romulus", "temple of mercury",
    "temple of concord", "temple of divus", "temple of hadrian",
    "temple of antoninus", "temple of faustina",
    "temple of all gods", "temple of portunus",
    "temple of hercules", "temple of bacchus", "temple of janus",
    "temple of bellona", "temple of isis", "temple of sera",
    "agora", "nymphaeum",
    "temple of minerva medica",
]

CHRISTIAN_IND = [
    "san miserino",
]

MASONIC_IND = [
    "illuminati", "masonic",
]

print("=== Greece ===")
classify_and_fix("GR", GREEK_IND, ROMAN_IND, CHRISTIAN_IND, MASONIC_IND, HINDU_IND)

print("\n=== Italy ===")
classify_and_fix("IT", GREEK_IND, ROMAN_IND, CHRISTIAN_IND, MASONIC_IND, HINDU_IND)

print("\n=== Turkey ===")
classify_and_fix("TR", GREEK_IND, ROMAN_IND, CHRISTIAN_IND, MASONIC_IND, HINDU_IND)

print("\n=== Egypt (skipped - no faith category) ===")
c.execute("""
    SELECT id, name FROM churches
    WHERE faith='Hindu' AND source='holy_sites_import'
        AND country='EG' AND LOWER(name) LIKE '%temple%'
""")
for row in c.fetchall():
    print(f"  ID={row[0]} | {row[1][:70]}")

conn.commit()
conn.close()

print(f"\n=== Changes applied: {len(changes)} ===")
for cid, field, old, new, details in changes:
    print(f"  {str(cid):>10s} | {field:10s} | {old:10s} -> {new:12s} | {details}")
