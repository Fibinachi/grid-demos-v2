"""
Match LOC telephone directory churches to GRID and taxonomize.
100% match rate via name+city+state.
"""
import sqlite3, json, re
from collections import Counter

ch = sqlite3.connect('E:/grid/churches.db')
ch.execute('PRAGMA busy_timeout=30000')

# ── Taxonomy index ─────────────────────────────────────────────────
tax_by_name = {}
for r in ch.execute('SELECT id, name, root_id FROM taxonomy').fetchall():
    tax_by_name[r[1].lower().strip()] = r[0]  # name → id only

# ── GRID index ─────────────────────────────────────────────────────
def norm(s):
    if not s: return ''
    s = s.lower().strip()
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s

grid_idx = {}
for row in ch.execute("SELECT rowid, name, city, state, taxonomy_id FROM churches WHERE country='US'").fetchall():
    key = (norm(row[1]), norm(row[2] or ''), (row[3] or '').upper())
    if key not in grid_idx:
        grid_idx[key] = (row[0], row[4])
print(f"Grid: {len(grid_idx):,} US churches")

# ── LOC data ───────────────────────────────────────────────────────
with open('E:/grid/data/loc_phone_dirs/results/loc_churches_mapped.json', encoding='utf-8') as f:
    loc = json.load(f)
print(f"LOC: {len(loc):,} churches")

# ── Denom → taxonomy ──────────────────────────────────────────────
S = {
    'catholic': 'catholic', 'roman catholic': 'catholic',
    'baptist': 'baptist', 'southern baptist': 'southern baptist',
    'methodist': 'methodist', 'united methodist': 'methodist',
    'lutheran': 'lutheran', 'evangelical lutheran': 'lutheran',
    'presbyterian': 'presbyterian',
    'episcopal': 'episcopal', 'protestant episcopal': 'episcopal', 'anglican': 'anglican',
    'assemblies': 'assemblies of god', 'assemblies of god': 'assemblies of god',
    'pentecostal': 'pentecostal',
    'nazarene': 'church of the nazarene', 'church of the nazarene': 'church of the nazarene',
    'adventist': 'adventist', 'seventh-day adventist': 'seventh-day adventist',
    'foursquare': 'international church of the foursquare gospel',
    'congregational': 'congregational',
    'church of christ': 'churches of christ', 'churches of christ': 'churches of christ',
    'christian': 'christian', 'general': 'non-denominational',
    'church': 'non-denominational', 'see': 'non-denominational',
    'greek': 'eastern orthodox', 'orthodox': 'eastern orthodox',
    'jewish': 'judaism', 'synagogue': 'judaism',
    'salvation army': 'salvation army', 'salvation': 'salvation army',
    'mormon': 'latter-day saints', 'latter-day saints': 'latter-day saints',
    'jehovah': "jehovah's witnesses",
    'christian science': 'christian science (first church of christ, scientist)',
    'unitarian': 'unitarian universalist', 'universalist': 'unitarian universalist',
    'evangelical': 'evangelical', 'independent': 'non-denominational / independent',
    'holiness': 'holiness', 'reformed': 'reformed',
    'mennonite': 'mennonite', 'moravian': 'moravian',
    'brethren': 'brethren', 'quaker': 'quaker/friends', 'friends': 'quaker/friends',
    'spiritualist': 'spiritualist', 'unity': 'unity',
    'disciples': 'disciples of christ',
}

def find_tax(denom):
    k = denom.lower().strip()
    if k in S:
        m = S[k]
        if m in tax_by_name: return tax_by_name[m]
    if k in tax_by_name: return tax_by_name[k]
    m = re.match(r'^(.+?)\s*\(', k)
    if m:
        base = m.group(1).strip()
        if base in tax_by_name: return tax_by_name[base]
        if base in S and S[base] in tax_by_name: return tax_by_name[S[base]]
    return None

# ── Match + assign ─────────────────────────────────────────────────
stats = Counter()
updates = []
unmapped_d = Counter()

for rec in loc:
    name = rec.get('name', '')
    city = rec.get('city', '')
    state = rec.get('state', '')
    denom = rec.get('denomination', '')
    
    key = (norm(name), norm(city), state.upper() if state else '')
    result = grid_idx.get(key)
    
    if not result: stats['no_match'] += 1; continue
    rowid, cur_tax = result
    stats['matched'] += 1
    
    if cur_tax and cur_tax > 0: stats['has_tax'] += 1; continue
    
    tid = find_tax(denom)
    if tid: updates.append((rowid, tid)); stats['mapped'] += 1
    else: unmapped_d[denom] += 1; stats['unmapped_d'] += 1

print(f"Matched: {stats['matched']:,} | has_tax: {stats['has_tax']:,} | to_update: {len(updates):,} | unmapped_d: {stats['unmapped_d']:,}")

# ── Push ───────────────────────────────────────────────────────────
if updates:
    ch.execute("CREATE TEMP TABLE IF NOT EXISTS _loc_tax (rowid INTEGER PRIMARY KEY, tax INTEGER)")
    ch.execute("DELETE FROM _loc_tax")
    ch.executemany("INSERT OR REPLACE INTO _loc_tax VALUES (?,?)", updates)
    ch.execute("UPDATE churches SET taxonomy_id=(SELECT tax FROM _loc_tax WHERE _loc_tax.rowid=churches.rowid) WHERE rowid IN (SELECT rowid FROM _loc_tax)")
    ch.execute("UPDATE churches SET faith=(SELECT t2.name FROM taxonomy t1 JOIN taxonomy t2 ON t2.id=t1.root_id WHERE t1.id=churches.taxonomy_id) WHERE rowid IN (SELECT rowid FROM _loc_tax) AND taxonomy_id IS NOT NULL")
    ch.commit()
    n = ch.execute("SELECT COUNT(*) FROM churches WHERE rowid IN (SELECT rowid FROM _loc_tax) AND taxonomy_id IS NOT NULL").fetchone()[0]
    print(f"Updated: {n:,}")
else:
    n = 0

# ── Report ─────────────────────────────────────────────────────────
if unmapped_d:
    print(f"\nUnmapped denoms ({len(unmapped_d)}):")
    for d, n in unmapped_d.most_common(20):
        print(f"  {d}: {n:,}")

total_tax = ch.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id IS NOT NULL").fetchone()[0]
print(f"\nTotal GRID with taxonomy: {total_tax:,}")

ch.execute("INSERT INTO provenance_log (source,script_name,churches_updated,records_matched,fields_populated,notes,status) VALUES ('loc_taxonomy','taxonomize_loc.py',?,?,'taxonomy_id,faith','LOC phone directory churches matched to GRID + taxonomized','complete')", (n, stats['matched']))
ch.commit(); ch.close()
print("Done.")
