"""
Detailed pattern analysis for Afro-diasporic reclassification.
Queries each keyword group and shows current faith/faith_tradition distribution.
"""
import sqlite3

conn = sqlite3.connect('E:\\grid\\churches.db')
c = conn.cursor()

groups = {
    "Umbanda": ["%umbanda%"],
    "Candomble": ["%candombl%", "%candomble%"],
    "Santeria": ["%santeria%", "%santera%"],
    "Macumba": ["%macumba%"],
    "Terreiro": ["%terreiro%"],
    "Vodou": ["%vodou%", "%voodoo%", "%voudou%"],
    "Peristyle": ["%peristyle%"],
    "Yoruba": ["%yoruba%"],
    "Orisha": ["%orisha%", "%orixa%", "%oricha%"],
    "Babalawo": ["%babalawo%"],
}

# Orixa deity names (be more specific to avoid false positives)
deities = {
    "Xango": ["%xango%", "%xangô%", "%chango%"],
    "Iemanja": ["%iemanja%", "%iemanjá%"],
    "Oxala": ["%oxala%", "%oxalá%"],
    "Oxossi": ["%oxossi%", "%oxóssi%"],
    "Ogum": ["%ogum%"],
    "Iansa": ["%iansa%", "%iansã%"],
}

for name, patterns in sorted(groups.items()):
    where = " OR ".join(["name LIKE ?" for _ in patterns])
    params = [p for p in patterns]
    cnt = c.execute("SELECT COUNT(*) FROM churches WHERE " + where, params).fetchone()[0]
    if cnt == 0:
        continue
    faiths = c.execute("SELECT COALESCE(faith,'NULL'), COUNT(*) FROM churches WHERE " + where + " GROUP BY faith ORDER BY COUNT(*) DESC", params).fetchall()
    faith_str = " | ".join([f"{r[0]}:{r[1]}" for r in faiths])
    print(f"{name:12s}: {cnt:>4} — {faith_str}")
    
    # Show names
    if cnt <= 15:
        rows = c.execute("SELECT name, faith, faith_tradition FROM churches WHERE " + where + " LIMIT 15", params).fetchall()
    else:
        rows = c.execute("SELECT name, faith, faith_tradition FROM churches WHERE " + where + " LIMIT 5", params).fetchall()
        print(f"  (First {len(rows)})")
    for r in rows:
        print(f'  -> faith={str(r[1] or ""):12s} trad={str(r[2] or ""):15s} "{str(r[0] or "")[:70]}"')

print()
print("--- Deity names ---")
for name, patterns in sorted(deities.items()):
    where = " OR ".join(["name LIKE ?" for _ in patterns])
    params = [p for p in patterns]
    cnt = c.execute("SELECT COUNT(*) FROM churches WHERE " + where, params).fetchone()[0]
    if cnt == 0:
        continue
    faiths = c.execute("SELECT COALESCE(faith,'NULL'), COUNT(*) FROM churches WHERE " + where + " GROUP BY faith ORDER BY COUNT(*) DESC", params).fetchall()
    faith_str = " | ".join([f"{r[0]}:{r[1]}" for r in faiths])
    print(f"{name:12s}: {cnt:>4} — {faith_str}")
    rows = c.execute("SELECT name, faith, faith_tradition FROM churches WHERE " + where + " LIMIT 3", params).fetchall()
    for r in rows:
        print(f'  -> faith={str(r[1] or ""):12s} trad={str(r[2] or ""):15s} "{str(r[0] or "")[:70]}"')

conn.close()
