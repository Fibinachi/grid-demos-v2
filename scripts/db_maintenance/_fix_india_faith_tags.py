"""
Fix misclassified faith tags for India holy_sites_import records.

Issues found:
  1. 48 Hindu temples → tagged as Jewish
  2. 16 churches/gurudwaras/mosques → tagged as Hindu
  3. ~3,037 Hindu/Jain temples/mandirs → tagged as Christian
  4. 1 "Muslim Temple" → tagged as Islam (actually Hindu)
  
Approach: Name-based keyword reclassification, with provenance logging.
"""
import sqlite3
import datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()

conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

changes = []  # Track all changes for logging

# ── Helper: check name for keywords ─────────────────────────────────────────
def has_kw(name, keywords):
    """Case-insensitive keyword match."""
    n = str(name).lower() if name else ''
    return any(kw in n for kw in keywords)

def classify_faith(name):
    """Classify a holy site name to a faith based on keywords."""
    n = str(name).lower() if name else ''
    
    # Order matters - check most specific first
    if has_kw(n, ['synagogue', 'synagog', 'chabad', 'jewish congregation',
                   'beit knesset', 'beth israel', 'beyth yisrael']):
        return 'Jewish'
    if has_kw(n, ['gurudwara', 'gurdwara']):
        return 'Sikh'
    if has_kw(n, ['mosque', 'masjid', 'islamic', 'muslim']):
        return 'Islam'
    if has_kw(n, ['church', 'cathedral', 'basilica', 'chapel', 'masihi mandir',
                   'orthodox', 'catholic', 'protestant', 'presbyterian',
                   'baptist', 'methodist', 'lutheran', 'pentecostal']):
        return 'Christian'
    if has_kw(n, ['buddhist', 'buddha', 'vihara', 'pagoda', 'wat ']):
        return 'Buddhist'
    if has_kw(n, ['temple', 'mandir', 'kovil', 'mandapam', 'swamy', 'ganpati',
                   'ganesh', 'shiva', 'vishnu', 'durga', 'kali', 'krishna',
                   'hanuman', 'lakshmi', 'saraswati', 'ayyappa', 'ayyapa',
                   'devi', 'mataji', 'haveli', 'siddhatek', 'jyotirling',
                   'shakti', 'panchalingeswar', 'parvathamalai', 'arapaleeswarar',
                   'sai baba', 'vrajbhumi', 'andheshwar', 'pahari wala',
                   'annadana', 'vishwavandita', 'bhikardas', 'hari ka patan',
                   'vishvambhari', 'tirupati', 'baba nirankar', 'panchamuki',
                   'kashi vishwanatha', 'kankroli', 'sector 19 temple',
                   'onyx', 'jain']):
        return 'Hindu'
    if has_kw(n, ['jain']):
        return 'Hindu'  # No Jain category, default to Hindu
    
    return None  # Can't determine

# ── 1. Fix Jewish → Hindu misclassifications ─────────────────────────────────
print("=== 1. Fixing Jewish → Hindu ===")
c.execute("""
    SELECT id, name FROM churches 
    WHERE country='IN' AND faith='Jewish' AND source='holy_sites_import'
""")
jewish = c.fetchall()
synagogue_kw = ['synagogue', 'synagog', 'chabad', 'jewish', 'israel', 
                'magen', 'keneseth', 'paradesi', 'succath', 'judah', 
                'beyth', 'beit', 'beth el', 'tiphaereth', 'shiloh fellowship',
                'gate of mercy', 'mala jewish']

fixed_jewish = 0
for cid, name in jewish:
    if not has_kw(name, synagogue_kw):
        c.execute("UPDATE churches SET faith='Hindu', faith_tradition='Hinduism' WHERE id=?", (cid,))
        changes.append((cid, 'faith', 'Jewish', 'Hindu', f'Misclassified Hindu temple: {name}'))
        fixed_jewish += 1

print(f"  Fixed {fixed_jewish} Jewish→Hindu")
conn.commit()

# ── 2. Fix Hindu → Christian/Islam/Sikh misclassifications ──────────────────
print("=== 2. Fixing Hindu → Christian/Islam/Sikh ===")
c.execute("""
    SELECT id, name FROM churches 
    WHERE country='IN' AND faith='Hindu' AND source='holy_sites_import'
""")
hindu = c.fetchall()

fixed_hindu = {'Christian': 0, 'Sikh': 0, 'Islam': 0}
for cid, name in hindu:
    new_faith = None
    if has_kw(name, ['church', 'cathedral', 'basilica', 'masihi mandir']):
        if not has_kw(name, ['temple', 'mandir']):  # Avoid "Church Temple" edge case
            new_faith = 'Christian'
    elif has_kw(name, ['gurudwara', 'gurdwara']):
        new_faith = 'Sikh'
    elif has_kw(name, ['mosque', 'masjid', 'muslim']):
        new_faith = 'Islam'
    
    if new_faith:
        c.execute("UPDATE churches SET faith=?, faith_tradition=? WHERE id=?", 
                  (new_faith, new_faith, cid))
        changes.append((cid, 'faith', 'Hindu', new_faith, f'Reclassified: {name}'))
        fixed_hindu[new_faith] += 1

for faith, cnt in fixed_hindu.items():
    print(f"  Fixed Hindu→{faith}: {cnt}")
conn.commit()

# ── 3. Fix Christian → Hindu misclassifications ─────────────────────────────
print("=== 3. Fixing Christian → Hindu ===")
c.execute("""
    SELECT id, name FROM churches 
    WHERE country='IN' AND faith='Christian' AND source='holy_sites_import'
""")
christian = c.fetchall()
christian_keep_kw = ['church', 'cathedral', 'basilica', 'chapel', 'orthodox',
                      'catholic', 'protestant', 'presbyterian', 'baptist',
                      'methodist', 'lutheran', 'pentecostal', 'evangelical',
                      'adventist', 'assembly of god', 'salvation army',
                      'jesuit', 'franciscan', 'dominican', 'carmelite',
                      'sacred heart', 'holy cross', 'holy family', 'holy trinity',
                      'st. ', 'saint ', 'santa ', 'notre dame', 'our lady',
                      'good shepherd', 'redeemer', 'saviour', 'savior',
                      'christ the', 'jesus', 'christian', 'christ ', 'messiah',
                      'immaculate', 'rosary', 'cristo', 'cristu', 'yeshu',
                      'mar thoma', 'csi ', 'cn i', 'malankara', 'jacobite',
                      'syrian', 'syro-malabar', 'syro-malankara']

# Hindu/Jain keywords (things that are NOT Christian)
hindu_kw = ['temple', 'mandir', 'kovil', 'mandapam', 'haveli', 'swamy', 'swami',
            'ganpati', 'ganesh', 'shiva', 'vishnu', 'durga', 'kali', 'krishna',
            'hanuman', 'lakshmi', 'saraswati', 'ayyappa', 'ayyapa', 'devi',
            'mataji', 'siddhatek', 'shakti', 'jyotirling', 'panchalingeswar',
            'parvathamalai', 'sai baba', 'vrajbhumi', 'jain', 'matha', 'math ',
            'baba ', 'dham ', 'dhaam', 'peeth', 'ashram', 'gaddi', 'akharo',
            'shankar', 'mahadev', 'lingam', 'linga', 'nath ', 'pir ', 'dargah',
            'samadhi', 'sansthan', 'matham', 'mutt', 'guruji', 'sadhu']

fixed_christian = 0
for cid, name in christian:
    # Keep if it has Christian keywords
    if has_kw(name, christian_keep_kw):
        continue
    # Reclassify if it has Hindu keywords but NOT Christian keywords
    if has_kw(name, hindu_kw):
        c.execute("UPDATE churches SET faith='Hindu', faith_tradition='Hinduism' WHERE id=?", (cid,))
        changes.append((cid, 'faith', 'Christian', 'Hindu', f'Misclassified as Christian, actually Hindu: {name}'))
        fixed_christian += 1

print(f"  Fixed Christian→Hindu: {fixed_christian}")
conn.commit()

# ── 4. Fix "Muslim Temple" → Hindu ──────────────────────────────────────────
print("=== 4. Fixing edge cases ===")
c.execute("""
    SELECT id, name FROM churches 
    WHERE country='IN' AND faith='Islam' AND source='holy_sites_import'
      AND name LIKE '%Temple%'
""")
for cid, name in c.fetchall():
    if not has_kw(name, ['mosque', 'masjid']):
        c.execute("UPDATE churches SET faith='Hindu', faith_tradition='Hinduism' WHERE id=?", (cid,))
        changes.append((cid, 'faith', 'Islam', 'Hindu', f'"Muslim Temple" likely Hindu: {name}'))
        print(f"  Fixed Islam→Hindu: {name}")

conn.commit()

# ── 5. Log all changes in provenance_log ────────────────────────────────────
print(f"\n=== Total changes: {len(changes)} ===")

c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_fix_india_faith_tags.py', TS, TS,
      len(changes), 0, 'faith,faith_tradition', 'completed',
      f'Fixed {len(changes)} misclassified faith tags for India holy_sites_import records'))

conn.commit()

# ── 6. Summary ──────────────────────────────────────────────────────────────
print("\n=== Final India faith breakdown ===")
c.execute("""
    SELECT faith, COUNT(*) FROM churches WHERE country='IN'
    GROUP BY faith ORDER BY COUNT(*) DESC
""")
for faith, cnt in c.fetchall():
    print(f"  {faith or 'NULL':<15} {cnt:>8,}")

conn.close()
print("\nDone!")
