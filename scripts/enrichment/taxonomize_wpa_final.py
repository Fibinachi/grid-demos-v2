"""
Single clean pass: taxonomize ALL WPA churches via OCR bridge.
Uses full synonym map. One UPDATE FROM, one commit.
"""
import sqlite3, re
from collections import Counter

ch = sqlite3.connect('E:/grid/churches.db')
ch.execute('PRAGMA busy_timeout=30000')

# ── Taxonomy index ─────────────────────────────────────────────────
tax_by_id = {}   # id → (name, root_id)
tax_by_name = {} # lower name → id
for r in ch.execute('SELECT id, name, root_id FROM taxonomy').fetchall():
    tax_by_id[r[0]] = (r[1], r[2])
    tax_by_name[r[1].lower().strip()] = r[0]

# ── Complete synonym map ───────────────────────────────────────────
S = {
    'roman catholic': 'catholic', 'catholic': 'catholic',
    'greek catholic': 'eastern catholic', 'ukrainian catholic': 'eastern catholic',
    'polish national catholic': 'polish national catholic church', 'old catholic': 'old catholic',
    'episcopal': 'episcopal', 'protestant episcopal': 'episcopal',
    'protestant episcopal church': 'episcopal', 'anglican': 'anglican',
    'methodist': 'methodist', 'methodist episcopal': 'methodist',
    'methodist episcopal, south': 'methodist', 'methodist protestant': 'methodist',
    'free methodist': 'methodist', 'united methodist': 'methodist',
    'wesleyan methodist': 'methodist', 'primitive methodist': 'methodist',
    'african methodist episcopal': 'african methodist episcopal',
    'african methodist episcopal zion': 'ame zion',
    'colored methodist episcopal': 'christian methodist episcopal',
    'union american methodist episcopal': 'african union first colored methodist protestant church and connection',
    'african union methodist protestant': 'african union first colored methodist protestant church and connection',
    'lutheran': 'lutheran', 'evangelical lutheran': 'lutheran',
    'norwegian lutheran': 'lutheran', 'lutheran free church': 'lutheran',
    'danish lutheran': 'lutheran', 'swedish lutheran': 'lutheran',
    'german lutheran': 'lutheran', 'american lutheran': 'lutheran',
    'united lutheran': 'lutheran', 'united lutheran church in america': 'lutheran',
    'finnish evangelical lutheran church of america (suomi synod)': 'lutheran',
    'finnish apostolic lutheran': 'lutheran', 'icelandic lutheran': 'lutheran',
    'augustana synod': 'lutheran',
    'baptist': 'baptist', 'northern baptist convention': 'american baptist churches usa',
    'southern baptist': 'southern baptist', 'national baptist': 'national baptist',
    'free will baptist': 'baptist', 'missionary baptist': 'baptist',
    'primitive baptist': 'baptist', 'regular baptist': 'baptist',
    'united baptist': 'baptist', 'general baptist': 'baptist',
    'colored baptist': 'baptist', 'old school baptist': 'baptist', 'seventh day baptist': 'baptist',
    'presbyterian': 'presbyterian', 'united presbyterian': 'presbyterian',
    'cumberland presbyterian': 'presbyterian', 'reformed presbyterian': 'presbyterian',
    'presbyterian church in the united states of america': 'presbyterian',
    'presbyterian church in the u.s.a.': 'presbyterian',
    'presbyterian sunday school mission': 'presbyterian',
    'associate reformed presbyterian': 'presbyterian',
    'orthodox presbyterian': 'presbyterian', 'bible presbyterian': 'presbyterian',
    'congregational': 'congregational', 'congregational christian': 'congregational',
    'congregational-christian': 'congregational', 'congregational and christian': 'congregational',
    'congregational\u2014christian': 'congregational',
    'reformed': 'reformed', 'evangelical and reformed': 'reformed',
    'christian reformed': 'reformed', 'reformed church in america': 'reformed',
    'reformed church in the united states': 'reformed',
    'pentecostal': 'pentecostal', 'assemblies of god': 'assemblies of god',
    'independent assemblies of god': 'assemblies of god',
    'pentecostal churches independent': 'pentecostal',
    'church of god in christ': 'cogic', 'church of god': 'church of god',
    'church of god (anderson, indiana)': 'church of god (anderson)',
    'pentecostal holiness': 'pentecostal', 'united pentecostal': 'pentecostal',
    'apostolic faith': 'pentecostal', 'full gospel': 'pentecostal',
    'holy church': 'pentecostal',
    'church of the nazarene': 'church of the nazarene',
    'salvation army': 'salvation army',
    'christian and missionary alliance': 'christian and missionary alliance',
    'seventh-day adventist': 'seventh-day adventist', 'advent christian': 'adventist',
    'adventist': 'adventist',
    'churches of christ': 'churches of christ', 'church of christ': 'churches of christ',
    'disciples of christ': 'disciples of christ',
    'disciples of christ (christian)': 'disciples of christ',
    'christian church': 'disciples of christ',
    'latter-day saints': 'latter-day saints', 'mormon': 'latter-day saints',
    'latter day saints': 'latter-day saints', 'reorganized lds': 'community of christ',
    'christian science': 'christian science (first church of christ, scientist)',
    'church of christ, scientist': 'christian science (first church of christ, scientist)',
    "jehovah's witnesses": "jehovah's witnesses",
    'evangelical': 'evangelical', 'evangelical free': 'evangelical free church of america',
    'independent': 'non-denominational / independent',
    'evangelical covenant': 'evangelical covenant church', 'covenant': 'evangelical covenant church',
    'moravian': 'moravian', 'mennonite': 'mennonite',
    'brethren': 'brethren', 'church of the brethren': 'brethren',
    'united brethren': 'brethren', 'evangelical united brethren': 'brethren',
    'plymouth brethren': 'brethren',
    'quaker': 'quaker/friends', 'friends': 'quaker/friends',
    'friends (quaker)': 'quaker/friends', 'friends (orthodox)': 'quaker/friends',
    'society of friends': 'quaker/friends',
    'unitarian': 'unitarian universalist', 'universalist': 'unitarian universalist',
    'foursquare gospel': 'international church of the foursquare gospel',
    'holiness': 'holiness', 'pilgrim holiness': 'holiness',
    'wesleyan': 'holiness', 'congregational holiness': 'holiness',
    'spiritualist': 'spiritualist', 'christian spiritualist': 'spiritualist',
    'spiritualist, independent': 'spiritualist',
    'greek orthodox': 'eastern orthodox', 'russian orthodox': 'eastern orthodox',
    'eastern orthodox': 'eastern orthodox', 'syrian orthodox': 'oriental orthodox',
    'armenian apostolic': 'oriental orthodox',
    'jewish': 'judaism', 'hebrew': 'judaism',
    'non-sectarian': 'non-denominational', 'undenominational': 'non-denominational',
    'community church': 'community church (unspecified)',
    'union church': 'christian union', 'union': 'christian union',
    'federated': 'federated church', 'interdenominational': 'interdenominational',
    'ymca': 'ymca', 'ywca': 'ymca',
    'community sunday school': 'non-denominational', 'sunday school': 'non-denominational',
    'hospital chapel': 'non-denominational', 'mission': 'non-denominational',
    'new thought': 'new thought', 'unity': 'unity', 'divine science': 'new thought',
    'theosophical': 'theosophical', 'ethical culture': 'ethical culture',
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
    for sfx in [' church', ' churches', ' in america', ' in the u.s.a.']:
        if k.endswith(sfx):
            shorter = k[:-len(sfx)]
            if shorter in tax_by_name: return tax_by_name[shorter]
            if shorter in S and S[shorter] in tax_by_name: return tax_by_name[S[shorter]]
    return None

# ── OCR bridge index ────────────────────────────────────────────────
ocr_idx = {}
for r in ch.execute("SELECT rowid, name, state FROM churches WHERE source='wpa_historical_records_survey' AND (taxonomy_id IS NULL OR taxonomy_id=0)").fetchall():
    ocr_idx[(r[1], (r[2] or '').upper())] = r[0]
print(f"  {len(ocr_idx):,} WPA churches needing taxonomy")

# ── Load bridge ─────────────────────────────────────────────────────
wpa = sqlite3.connect('E:/grid/wpa.db')
bridge = wpa.execute("""
    SELECT d.denomination, r.church_name, r.state
    FROM wpa_deepseek_parsed d JOIN wpa_records r ON d.id = r.id
    WHERE d.denomination IS NOT NULL AND d.denomination != ''
""").fetchall()
wpa.close()
print(f"  {len(bridge):,} bridge records")

# ── Match and map ──────────────────────────────────────────────────
updates = []  # (rowid, tax_id)
unmapped = Counter()
matched = no_ocr = 0

for denom, raw_name, state in bridge:
    state = (state or '').upper()
    rowid = ocr_idx.get((raw_name, state))
    if not rowid:
        no_ocr += 1
        continue
    matched += 1
    tid = find_tax(denom)
    if tid:
        updates.append((rowid, tid))
    else:
        unmapped[denom] += 1

print(f"  Matched: {matched:,} | No OCR match: {no_ocr:,} | To update: {len(updates):,}")

# ── Push ────────────────────────────────────────────────────────────
if updates:
    ch.execute("CREATE TEMP TABLE IF NOT EXISTS _wpa_tax (rowid INTEGER PRIMARY KEY, tax INTEGER)")
    ch.execute("DELETE FROM _wpa_tax")
    ch.executemany("INSERT OR REPLACE INTO _wpa_tax VALUES (?,?)", updates)
    
    ch.execute("UPDATE churches SET taxonomy_id=(SELECT tax FROM _wpa_tax WHERE _wpa_tax.rowid=churches.rowid) WHERE rowid IN (SELECT rowid FROM _wpa_tax)")
    ch.execute("""
        UPDATE churches SET faith=(
            SELECT t2.name FROM taxonomy t1 JOIN taxonomy t2 ON t2.id=t1.root_id
            WHERE t1.id=churches.taxonomy_id
        ) WHERE rowid IN (SELECT rowid FROM _wpa_tax) AND taxonomy_id IS NOT NULL
    """)
    ch.commit()
    
    n = ch.execute("SELECT COUNT(*) FROM churches WHERE rowid IN (SELECT rowid FROM _wpa_tax) AND taxonomy_id IS NOT NULL").fetchone()[0]
    print(f"  Updated: {n:,}")
else:
    n = 0

# ── Final stats ────────────────────────────────────────────────────
total = ch.execute("SELECT COUNT(*) FROM churches WHERE source='wpa_historical_records_survey'").fetchone()[0]
wt = ch.execute("SELECT COUNT(*) FROM churches WHERE source='wpa_historical_records_survey' AND taxonomy_id IS NOT NULL").fetchone()[0]
print(f"\nWPA taxonomy: {wt:,}/{total:,} ({wt/total*100:.1f}%)")

# Top taxonomies
print("\nTop 15:")
for r in ch.execute("""
    SELECT t.name, COUNT(*) n FROM churches c
    JOIN taxonomy t ON c.taxonomy_id=t.id
    WHERE c.source='wpa_historical_records_survey'
    GROUP BY t.name ORDER BY n DESC LIMIT 15
""").fetchall():
    print(f"  {r[0]}: {r[1]:,}")

if unmapped:
    print(f"\nUnmapped denominations ({len(unmapped)} types):")
    for d, n in unmapped.most_common(15):
        print(f"  {d}: {n:,}")

ch.execute("INSERT INTO provenance_log (source,script_name,churches_updated,records_matched,fields_populated,notes,status) VALUES ('wpa_taxonomy_final','taxonomize_wpa.py',?,?,'taxonomy_id,faith','Single-pass WPA taxonomy via OCR bridge','complete')", (n, matched))
ch.commit()
ch.close()
print("Done.")
