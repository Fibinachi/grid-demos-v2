"""
Spanish/Mexico church classifier implementing the specified rule set.
Phase 2: Add columns + run Rule 1 (OSM tags) + Rules 2-7 (name heuristics).
"""
import sqlite3, re, json
from datetime import datetime

conn = sqlite3.connect('churches.db')
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA synchronous=OFF')
conn.execute('PRAGMA busy_timeout=60000')
now = datetime.now().isoformat()

# ── Ensure schema columns ──
existing_cols = [r[1] for r in conn.execute('PRAGMA table_info(churches)')]

for col, col_type in [
    ('subtradition', 'TEXT'),
    ('confidence_score', 'REAL'),
    ('classification_timestamp', 'TEXT'),
    ('classification_version', 'TEXT'),
    ('manual_override_flag', 'INTEGER DEFAULT 0'),
]:
    if col not in existing_cols:
        conn.execute(f'ALTER TABLE churches ADD COLUMN {col} {col_type}')
        print(f'  Added column: {col}')

conn.commit()

# ── Rule 1: OSM tag classification ──
# We use Overture categories.alternate as OSM tag proxy
# and brand data for denomination hints
print('\n=== Rule 1: OSM Tags (via Overture categories + brand) ===')

# 1A: religion tag mapping from categories
# alternate categories like "catholic_church", "religious_organization"
cat_map = {
    'catholic_church': ('christian', 'catholic'),
    'religious_organization': (None, None),  # ambiguous, fall through
    'church_cathedral': (None, None),
}

# 1B: denomination from brand name patterns
brand_patterns = [
    (r'(?i)adventista', 'christian', 'adventist'),
    (r'(?i)metodista', 'christian', 'methodist'),
    (r'(?i)bautista', 'christian', 'baptist'),
    (r'(?i)pentecost', 'christian', 'pentecostal'),
    (r'(?i)presbiterian', 'christian', 'presbyterian'),
    (r'(?i)nazareno', 'christian', 'nazarene'),
    (r'(?i)asamblea.*dios', 'christian', 'assemblies_of_god'),
    (r'(?i)luz.*mundo', 'christian', 'luz_del_mundo'),
    (r'(?i)testigo.*jehov|jehovah', 'christian', 'jehovahs_witness'),
    (r'(?i)mormon|latter.day|santos.*ultimos', 'christian', 'latter_day_saints'),
    (r'(?i)anglican|episcopal', 'christian', 'anglican'),
    (r'(?i)luteran', 'christian', 'lutheran'),
    (r'(?i)ortodox', 'christian', 'orthodox'),
]

updated_r1 = 0
# Process MX churches from overture_full (they may have Overture data)
mx_churches = conn.execute("""
    SELECT id, name, city, state 
    FROM churches WHERE country='MX' 
    AND (faith_tradition IS NULL OR faith_tradition = '')
""").fetchall()
print(f'  MX churches to classify: {len(mx_churches):,}')

# We don't have Overture tags in SQLite, so Rule 1 is limited for now.
# Apply brand-based rules from what we can infer from the name
# (The actual brand field from Overture isn't in our SQLite - it wasn't imported)

# For now, apply Rules 2-7 (name heuristics) since we have names
print('\n=== Rules 2-7: Name Heuristics ===')

# Rule 2: Catholic markers
catholic_patterns = [
    r'(?i)\bPARROQUIA\b', r'(?i)\bCATEDRAL\b', r'(?i)\bBASILICA\b',
    r'(?i)\bSANTUARIO\b', r'(?i)\bCAPILLA\b',
    r'(?i)\bIGLESIA\s+CATOLICA\b', r'(?i)\bTEMPLO\s+CATOLICO\b',
    r'(?i)\bSAGRADO\s+CORAZON\b', r'(?i)\bGUADALUPE\b',
    r'(?i)\bSAN\s+(JUAN|PEDRO|PABLO|JOSE|MIGUEL|FRANCISCO|ANTONIO|LUIS|RAFAEL|DIEGO|AGUSTIN)\b',
    r'(?i)\bSANTA\s+(MARIA|ANA|ROSA|CRUZ|CATARINA|TERESA|LUCIA|ISABEL|MONICA)\b',
    r'(?i)\bVIRGEN\b', r'(?i)\bINMACULADA\b', r'(?i)\bASUNCION\b',
    r'(?i)\bROSARIO\b', r'(?i)\bPERPETUO\s+SOCORRO\b',
    r'(?i)\bDIVINA\s+PROVIDENCIA\b', r'(?i)\bSANTO\s+(DOMINGO|TOMAS|CRISTO)\b',
    r'(?i)\bNUESTRA\s+SE.O?RA\b',
]

# Rule 3: Protestant/Evangelical markers
protestant_patterns = [
    (r'(?i)\bIGLESIA\s+EVANGELICA\b', 'evangelical'),
    (r'(?i)\bIGLESIA\s+BAUTISTA\b', 'baptist'),
    (r'(?i)\bIGLESIA\s+METODISTA\b', 'methodist'),
    (r'(?i)\bIGLESIA\s+PENTECOSTAL\b', 'pentecostal'),
    (r'(?i)\bIGLESIA\s+DE\s+DIOS\b', 'church_of_god'),
    (r'(?i)\bASAMBLEA.*DIOS\b', 'assemblies_of_god'),
    (r'(?i)\bIGLESIA\s+DEL\s+NAZARENO\b', 'nazarene'),
    (r'(?i)\bIGLESIA\s+PRESBITERIANA\b', 'presbyterian'),
    (r'(?i)\bIGLESIA\s+ADVENTISTA\b', 'adventist'),
    (r'(?i)\bIGLESIA\s+BIBLICA\b', 'evangelical'),
    (r'(?i)\bIGLESIA\s+APOSTOLICA\b', 'apostolic'),
    (r'(?i)\bIGLESIA\s+LUTERANA\b', 'lutheran'),
    (r'(?i)\bIGLESIA\s+ANGLICANA\b', 'anglican'),
]

# Rule 4: Non-denom markers (Mexico specific)
nondenom_patterns = [
    r'(?i)\bCOMUNIDAD\s+CRISTIANA\b', r'(?i)\bCENTRO\s+CRISTIANO\b',
    r'(?i)\bCASA\s+DE\s+ORACION\b', r'(?i)\bMINISTERIO\s+CRISTIANO\b',
    r'(?i)\bCENTRO\s+DE\s+FE\b', r'(?i)\bCENTRO\s+DE\s+VIDA\b',
    r'(?i)\bNUEVA\s+VIDA\b', r'(?i)\bVIDA\s+ABUNDANTE\b',
    r'(?i)\bROCA\s+ETERNA\b', r'(?i)\bEL\s+BUEN\s+PASTOR\b',
    r'(?i)\bCENTRO\s+FAMILIAR\b',
]

# Rule 5: Jewish markers
jewish_patterns = [
    r'(?i)\bSINAGOGA\b', r'(?i)\bCOMUNIDAD\s+JUDIA\b',
    r'(?i)\bCENTRO\s+ISRAELITA\b', r'(?i)\bTEMPLO\s+JUDIO\b',
]

# Rule 6: Muslim markers
muslim_patterns = [
    r'(?i)\bMEZQUITA\b', r'(?i)\bCENTRO\s+ISLAMICO\b',
    r'(?i)\bCOMUNIDAD\s+MUSULMANA\b',
]

# Rule 7: Indigenous/Syncretic markers
syncretic_patterns = [
    r'(?i)\bTEMAZCAL\b', r'(?i)\bCENTRO\s+CEREMONIAL\b',
    r'(?i)\bDANZA\s+AZTECA\b', r'(?i)\bTEMPLO\s+MAYA\b',
]

def classify_spanish(name):
    """Apply Rules 2-7 to a Spanish church name. Returns (faith_tradition, subtradition, confidence, source)."""
    
    # Rule 2: Catholic
    for pat in catholic_patterns:
        if re.search(pat, name):
            return ('christian', 'catholic', 0.90, 'spanish_name_heuristic_catholic')
    
    # Rule 5: Jewish
    for pat in jewish_patterns:
        if re.search(pat, name):
            return ('jewish', None, 0.95, 'spanish_name_heuristic_jewish')
    
    # Rule 6: Muslim
    for pat in muslim_patterns:
        if re.search(pat, name):
            return ('muslim', None, 0.95, 'spanish_name_heuristic_muslim')
    
    # Rule 7: Syncretic
    for pat in syncretic_patterns:
        if re.search(pat, name):
            return ('indigenous_syncretic', None, 0.70, 'spanish_name_heuristic_syncretic')
    
    # Rule 3: Protestant/Evangelical
    for pat, subtrad in protestant_patterns:
        if re.search(pat, name):
            return ('christian', subtrad, 0.85, 'spanish_name_heuristic_protestant')
    
    # Luz del Mundo (specific denomination - check before non-denom)
    if re.search(r'(?i)\bLUZ\s+DEL\s+MUNDO\b', name) and not re.search(r'(?i)\bIGLESIA\s+LUZ\s+DEL\s+MUNDO\b', name):
        return ('christian', 'luz_del_mundo', 0.85, 'spanish_name_heuristic')
    
    # Rule 4: Non-denominational (has Christian marker but no specific denomination)
    # Check if generally Christian first
    generic_christian = [
        r'(?i)\bIGLESIA\b', r'(?i)\bCRISTIAN[AO]\b', r'(?i)\bEVANGELIO\b',
        r'(?i)\bJESUS\b', r'(?i)\bCRISTO\b', r'(?i)\bPASTORAL\b',
        r'(?i)\bMINISTERIO\b', r'(?i)\bMISION\b',
    ]
    
    is_christian = any(re.search(p, name) for p in generic_christian)
    is_nondenom = any(re.search(p, name) for p in nondenom_patterns)
    
    if is_nondenom and is_christian:
        return ('christian', 'non_denominational', 0.70, 'spanish_name_heuristic_nondenom')
    
    # Generic Christian
    if is_christian:
        # Has "Iglesia" but no other markers → try to detect more specific
        return ('christian', None, 0.50, 'spanish_name_heuristic_generic_christian')
    
    # Fallback
    return ('unknown', None, 0.10, 'spanish_name_heuristic_unknown')

# Apply to ALL unclassified MX churches in batches
print('  Classifying...')
batch = []
classified = 0
for id_, name, city, state in mx_churches:
    if not name: continue
    ft, sub, conf, source = classify_spanish(name)
    batch.append((ft, sub, conf, source, now, '1.0', id_))
    classified += 1
    
    # Commit every 5000 rows
    if len(batch) >= 5000:
        conn.executemany("""
            UPDATE churches SET 
                faith_tradition=?, subtradition=?, confidence_score=?,
                classification_source=?, classification_timestamp=?, classification_version=?
            WHERE id=?
        """, batch)
        conn.commit()
        print(f'    {classified:,} committed...', flush=True)
        batch = []

# Final batch
if batch:
    conn.executemany("""
        UPDATE churches SET 
            faith_tradition=?, subtradition=?, confidence_score=?,
            classification_source=?, classification_timestamp=?, classification_version=?
        WHERE id=?
    """, batch)
    conn.commit()
print(f'  Classified: {classified:,}')

# ── Stats ──
print('\n=== CLASSIFICATION RESULTS (Mexico) ===')
for r in conn.execute("""
    SELECT faith_tradition, subtradition, COUNT(*) n, ROUND(AVG(confidence_score),2) avg_conf
    FROM churches WHERE country='MX'
    GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 15
"""):
    print(f'  {r[0] or "?":25s} {r[1] or "?":25s} {r[2]:>8,}  conf={r[3]}')

# Total classified
total_mx = conn.execute("SELECT COUNT(*) FROM churches WHERE country='MX'").fetchone()[0]
classified_mx = conn.execute("SELECT COUNT(*) FROM churches WHERE country='MX' AND faith_tradition IS NOT NULL AND faith_tradition != ''").fetchone()[0]
print(f'\n  Total MX: {total_mx:,} | Classified: {classified_mx:,} ({100*classified_mx/total_mx:.1f}%)')

conn.close()
print('Done.')
