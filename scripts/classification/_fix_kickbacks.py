"""
Fix all wrongly-kicked Stage 2 entries. Reclassifies Non-Religious kickbacks
to their correct faith based on name patterns instead of metadata.
"""
import sqlite3, re

DB = r"E:\grid\churches.db"
SOURCE = "stage2_kickback_fix"
CHUNK = 500

# ── Name pattern → correct faith ──
PATTERN_FAITH = [
    # Christian (most common)
    (r'\b(church|chapel|cathedral|parish|saint|st\.|anglican|methodist|baptist|presbyterian|lutheran|pentecostal|charismatic|evangelical|gospel|ministry|worship|fellowship|jesus|christ|catholic|episcopal|diocese|christian)\b', 'Christian'),
    (r'\b(eglise|eglises|paroisse|catholique|chretien|iglesia|igreja|kirche|kerk|iglesya)\b', 'Christian'),
    (r'\b(assembly|assemblies|apostolic|prayer|praying|bible|biblical|gospel|kingdom|zion|covenant|calvary|grace|mercy|glory|redemption|salvation|resurrection)\b', 'Christian'),
    (r'\b(adoracao|adoração|ad\b|adm\b|adni\b|igreja|comunidade|ministerio|ministério)\b', 'Christian'),
    (r'\b(acts\s*\d|corinth|galatian|ephes|philipp|coloss|thessalon|timothy)\b', 'Christian'),
    (r'\b(restoration|redeem|redeemer|tabernacle|sanctuary|temple.*christ|temple.*lord)\b', 'Christian'),
    # Islam
    (r'\b(mosque|masjid|islamic|muslim|jamaat|jami)\b', 'Islam'),
    # Hindu
    (r'\b(mandir|temple|hindu|swami|kovil|devi|shiva|krishna)\b', 'Hindu'),
    # Buddhist
    (r'\b(buddhist|buddha|wat\b|vihara|pagoda|zen|theravada|mahayana)\b', 'Buddhist'),
    # Sikh
    (r'\b(sikh|gurdwara|khalsa|singh)\b', 'Sikh'),
    # Judaism
    (r'\b(synagogue|shul|jewish|beit|torah|chabad|lubavitch)\b', 'Judaism'),
    # Jain
    (r'\b(jain|derasar)\b', 'Jain'),
    # Bahai
    (r'\b(baha.?i|bahai)\b', 'Bahai'),
    # Shinto
    (r'\b(shinto|jinja|jingu|taisha)\b', 'Shinto'),
    # Taoist
    (r'\b(taoist|daoist|tao\b|dao\b)\b', 'Taoist'),
    # Sikh (gurdwara already caught above)
]

CIVILIZATION = {
    'Christian': 'ABRAHAMIC', 'Islam': 'ABRAHAMIC', 'Judaism': 'ABRAHAMIC', 'Bahai': 'ABRAHAMIC',
    'Hindu': 'DHARMIC', 'Buddhist': 'DHARMIC', 'Sikh': 'DHARMIC', 'Jain': 'DHARMIC',
    'Shinto': 'TAOIC', 'Taoist': 'TAOIC', 'Confucian': 'TAOIC',
}

def resolve_faith(name):
    if not name: return None
    n = name.lower()
    for pattern, faith in PATTERN_FAITH:
        if re.search(pattern, n):
            return faith
    return None

db = sqlite3.connect(DB, timeout=30)
db.execute("PRAGMA journal_mode=WAL")
c = db.cursor()

# Get all entries kicked to Non-Religious by stage2 today
rows = c.execute("""
    SELECT c.id, c.name, c.faith, c.tradition, h.reasoning
    FROM churches c 
    JOIN classification_history h ON c.id = h.church_id 
    WHERE h.action = 'kickback' AND h.stage LIKE 'stage2_%' 
    AND c.faith = 'Non-Religious' AND c.tradition = 'non_religious'
""").fetchall()

print(f"Total kicked to Non-Religious: {len(rows):,}")

fixed = 0
still_kicked = 0
counts = {}

for i in range(0, len(rows), CHUNK):
    batch = rows[i:i+CHUNK]
    for cid, name, old_faith, old_trad, reasoning in batch:
        new_faith = resolve_faith(name)
        if new_faith:
            civ = CIVILIZATION.get(new_faith, 'OTHER')
            db.execute("UPDATE churches SET faith=?, tradition=?, civilizational_family=? WHERE id=?",
                       (new_faith, new_faith.lower(), civ, cid))
            db.execute("""INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source)
                          VALUES (?,?,?,?,?)""",
                       (cid, 'faith', 'Non-Religious', new_faith, SOURCE))
            db.execute("""INSERT INTO classification_history (church_id, stage, action, field_name, old_value, new_value, confidence, reasoning, batch_id)
                              VALUES (?,'stage2_kickback_fix','classified','faith',?,?,0.85,?,?)""",
                       (cid, old_faith, new_faith, f'Name pattern redirect: {reasoning}', 'stage2_kickback_fix_20260705'))
            counts[new_faith] = counts.get(new_faith, 0) + 1
            fixed += 1
        else:
            still_kicked += 1
    db.commit()
    print(f"\r  {min(i+CHUNK, len(rows)):,}/{len(rows):,} | fixed: {fixed:,} | still kicked: {still_kicked:,}", end="")

print(f"\n\nDone. {fixed:,} redirected, {still_kicked:,} remain as Non-Religious.")
print("\nRedirected to:")
for faith, cnt in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {faith:15s}: {cnt:,}")

# Show remaining still-kicked entries
if still_kicked > 0:
    print(f"\nSample of {still_kicked:,} still-kicked (no clear pattern):")
    for r in c.execute("""SELECT c.name, c.city, c.country FROM churches c 
        JOIN classification_history h ON c.id = h.church_id 
        WHERE h.action = 'kickback' AND h.stage LIKE 'stage2_%' 
        AND c.faith = 'Non-Religious' ORDER BY c.name LIMIT 15"""):
        print(f"  {r[0][:60]} | {r[1]} | {r[2]}")

db.close()
