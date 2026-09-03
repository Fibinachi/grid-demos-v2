"""Debug and re-run the ancient temple fix."""
import sqlite3

DB = r"e:\grid\churches.db"
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

# First, check the actual id values for ancient temples
print("=== Temple of Hera (debug IDs) ===")
c.execute("SELECT id, name, faith FROM churches WHERE name LIKE '%Temple of Hera%'")
for r in c.fetchall():
    print(f"  id={r[0]} (type={type(r[0]).__name__}) | {r[1][:60]} | faith={r[2]}")

# Check all temple entries that might need fixing
print("\n=== All ancient-style temples faith=Hindu by country ===")
c.execute("""
    SELECT id, name, country FROM churches
    WHERE faith='Hindu' AND source='holy_sites_import'
        AND country IN ('GR','IT','TR','EG')
        AND LOWER(name) LIKE '%temple%'
        AND NOT (LOWER(name) LIKE '%mandir%' OR LOWER(name) LIKE '%iskcon%'
            OR LOWER(name) LIKE '%krishna%' OR LOWER(name) LIKE '%shiva%')
    ORDER BY country, name
""")
rows = c.fetchall()
print(f"Total: {len(rows)}")
for r in rows:
    print(f"  id={r[0]} | {r[1][:70]} | {r[2]}")

# NOW re-run the fix properly
print("\n=== Applying fixes ===")
changes = []

# Greece
c.execute("""
    SELECT id, name FROM churches
    WHERE faith='Hindu' AND source='holy_sites_import' AND country='GR'
        AND LOWER(name) LIKE '%temple%'
        AND NOT (LOWER(name) LIKE '%mandir%' OR LOWER(name) LIKE '%iskcon%'
            OR LOWER(name) LIKE '%krishna%' OR LOWER(name) LIKE '%shiva%')
""")
for r in c.fetchall():
    name_lower = (r[1] or "").lower()
    if any(x in name_lower for x in ["temple of hera", "temple of zeus", "temple of athena",
                                       "temple of apollo", "temple of olympian zeus"]):
        c.execute("UPDATE churches SET faith='Hellenism', faith_tradition='Hellenism' WHERE id=?", (r[0],))
        changes.append((r[0], "Hindu", "Hellenism", f"Greek: {r[1][:60]}"))
        print(f"  Fixed GR: id={r[0]} -> Hellenism | {r[1][:60]}")
    else:
        print(f"  UNMATCHED GR: id={r[0]} | {r[1]}")

# Italy - Greek temples (Paestum, Selinunte) -> Hellenism
c.execute("""
    SELECT id, name FROM churches
    WHERE faith='Hindu' AND source='holy_sites_import' AND country='IT'
        AND LOWER(name) LIKE '%temple%'
        AND NOT (LOWER(name) LIKE '%mandir%' OR LOWER(name) LIKE '%iskcon%'
            OR LOWER(name) LIKE '%krishna%' OR LOWER(name) LIKE '%shiva%')
""")
for r in c.fetchall():
    name_lower = (r[1] or "").lower()
    if any(x in name_lower for x in ["temple of hera", "paestum", "selinunte"]):
        c.execute("UPDATE churches SET faith='Hellenism', faith_tradition='Hellenism' WHERE id=?", (r[0],))
        changes.append((r[0], "Hindu", "Hellenism", f"Greek in IT: {r[1][:60]}"))
        print(f"  Fixed IT Greek: id={r[0]} -> Hellenism | {r[1][:60]}")
    elif any(x in name_lower for x in ["temple of minerva"]):
        c.execute("UPDATE churches SET faith='Roman', faith_tradition='Roman' WHERE id=?", (r[0],))
        changes.append((r[0], "Hindu", "Roman", f"Roman: {r[1][:60]}"))
        print(f"  Fixed IT Roman: id={r[0]} -> Roman | {r[1][:60]}")
    elif "san miserino" in name_lower:
        c.execute("UPDATE churches SET faith='Christian', faith_tradition='Christianity' WHERE id=?", (r[0],))
        changes.append((r[0], "Hindu", "Christian", f"Church: {r[1][:60]}"))
        print(f"  Fixed IT Christian: id={r[0]} -> Christian | {r[1][:60]}")
    else:
        print(f"  UNMATCHED IT: id={r[0]} | {r[1]}")

# Turkey - Roman temples -> Roman
c.execute("""
    SELECT id, name FROM churches
    WHERE faith='Hindu' AND source='holy_sites_import' AND country='TR'
        AND LOWER(name) LIKE '%temple%'
        AND NOT (LOWER(name) LIKE '%mandir%' OR LOWER(name) LIKE '%iskcon%'
            OR LOWER(name) LIKE '%krishna%' OR LOWER(name) LIKE '%shiva%')
""")
for r in c.fetchall():
    name_lower = (r[1] or "").lower()
    if any(x in name_lower for x in ["agora", "nymphaeum"]):
        c.execute("UPDATE churches SET faith='Roman', faith_tradition='Roman' WHERE id=?", (r[0],))
        changes.append((r[0], "Hindu", "Roman", f"Roman in TR: {r[1][:60]}"))
        print(f"  Fixed TR: id={r[0]} -> Roman | {r[1][:60]}")
    elif "illuminati" in name_lower or "masonic" in name_lower:
        c.execute("UPDATE churches SET faith='Other', faith_tradition='Masonic' WHERE id=?", (r[0],))
        changes.append((r[0], "Hindu", "Other", f"Masonic: {r[1][:60]}"))
        print(f"  Fixed TR Masonic: id={r[0]} -> Other | {r[1][:60]}")
    elif any(x in name_lower for x in ["varageeswarar"]):
        # This IS a Hindu temple (actual Tamil temple in Turkey/diaspora)
        print(f"  SKIPPED (likely Hindu): id={r[0]} | {r[1]}")
    else:
        print(f"  UNMATCHED TR: id={r[0]} | {r[1]}")

conn.commit()

print(f"\n=== Total changes: {len(changes)} ===")
for r in changes:
    print(f"  id={r[0]} | {r[1]:10s} -> {r[2]:12s} | {r[3]}")

# Verify
print("\n=== Verification ===")
for faith in ['Hellenism', 'Roman']:
    c.execute("SELECT COUNT(*) FROM churches WHERE faith=?", (faith,))
    print(f"  {faith}: {c.fetchone()[0]}")
c.execute("SELECT name, faith FROM churches WHERE name LIKE '%Temple of Hera%'")
for r in c.fetchall():
    print(f"  {r[0][:60]} -> {r[1]}")

conn.close()
