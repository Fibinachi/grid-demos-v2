"""
Canadian church classifier — Rules 1-11 name heuristics + geo-inference.
Columns already exist from spanish_classifier.py.
"""
import sqlite3, re, datetime

conn = sqlite3.connect('churches.db')
conn.execute('PRAGMA journal_mode=WAL')
conn.execute('PRAGMA synchronous=OFF')
conn.execute('PRAGMA busy_timeout=60000')
now = datetime.datetime.now().isoformat()

# ── Rule 2: Catholic ──
catholic_patterns = [
    r'(?i)\bPARISH\b', r'(?i)\bPAROISSE\b',
    r'(?i)\bEGLISE\s+CATHOLIQUE\b', r'(?i)\bCATHOLIC\s+CHURCH\b',
    r'(?i)\bST\.\s+\w+', r'(?i)\bSAINT\s+\w+', r'(?i)\bSTE\.\s+\w+', r'(?i)\bSAINTE\s+\w+',
    r'(?i)\bOUR\s+LADY\b', r'(?i)\bNOTRE.?DAME\b',
    r'(?i)\bHOLY\s+ROSARY\b', r'(?i)\bSACRED\s+HEART\b',
    r'(?i)\bIMMACULATE\b', r'(?i)\bASSUMPTION\b',
    r'(?i)\bCATHEDRAL\b', r'(?i)\bBASILICA\b',
    r'(?i)\bSACRE.?COEUR\b', r'(?i)\bBON\s+PASTEUR\b',
    r'(?i)\bST\.?\s*(JOHN|PAUL|PETER|JAMES|JOSEPH|MICHAEL|ANDREW|PATRICK|THOMAS|GEORGE|MARY|ANN)\b',
]

# ── Rule 3: Mainline Protestant ──
mainline_patterns = [
    (r'(?i)\bUNITED\s+CHURCH\b', 'united_church_of_canada'),
    (r'(?i)\bANGLICAN\b', 'anglican_church_of_canada'),
    (r'(?i)\bPRESBYTERIAN\b', 'presbyterian_church_in_canada'),
    (r'(?i)\bLUTHERAN\b', 'lutheran'),
    (r'(?i)\bREFORMED\s+CHURCH\b', 'reformed'),
    (r'(?i)\bST\.\s+ANDREW', 'presbyterian_church_in_canada'),
]

# ── Rule 4: Evangelical/Pentecostal ──
evangelical_patterns = [
    (r'(?i)\bPENTECOSTAL\b', 'pentecostal'),
    (r'(?i)\bPAOC\b', 'pentecostal'),
    (r'(?i)\bALLIANCE\s+CHURCH\b', 'christian_and_missionary_alliance'),
    (r'(?i)\bEVANGELICAL\b', 'evangelical'),
    (r'(?i)\bVICTORY\s+CHURCH\b', 'evangelical'),
    (r'(?i)\bCALVARY\s+CHAPEL\b', 'evangelical'),
    (r'(?i)\bFELLOWSHIP\s+BAPTIST\b', 'baptist'),
    (r'(?i)\bGOSPEL\s+CHAPEL\b', 'evangelical'),
    (r'(?i)\bTABERNACLE\b', 'evangelical'),
    (r'(?i)\bCHAPEL\b', 'evangelical'),
    (r'(?i)\bMENNONITE\b', 'mennonite'),
    (r'(?i)\bBRETHREN\b', 'brethren'),
    (r'(?i)\bSALVATION\s+ARMY\b', 'salvation_army'),
    (r'(?i)\bNAZARENE\b', 'nazarene'),
    (r'(?i)\bMISSIONARY\s+CHURCH\b', 'evangelical'),
    (r'(?i)\bFREE\s+METHODIST\b', 'free_methodist'),
    (r'(?i)\bWESLEYAN\b', 'wesleyan'),
]

# ── Rule 5: Non-Denom ──
nondenom_patterns = [
    r'(?i)\bCOMMUNITY\s+CHURCH\b', r'(?i)\bCHRISTIAN\s+CHURCH\b',
    r'(?i)\bLIFE\s+CENTRE?\b', r'(?i)\bLIFE\s+CHURCH\b',
    r'(?i)\bHOPE\s+CHURCH\b', r'(?i)\bFAITH\s+CHURCH\b',
    r'(?i)\bHARVEST\b', r'(?i)\bVINEYARD\b',
    r'(?i)\bLIVING\s+WATERS\b', r'(?i)\bNEW\s+LIFE\b',
    r'(?i)\bGATEWAY\b', r'(?i)\bCENTRE\s+CHRETIEN\b',
    r'(?i)\bFELLOWSHIP\s+CHURCH\b', r'(?i)\bCHURCH\s+PLANT\b',
    r'(?i)\bCORNERSTONE\b', r'(?i)\bCROSSROADS\b',
    r'(?i)\bELEVATION\b', r'(?i)\bJOURNEY\s+CHURCH\b',
    r'(?i)\bMEETING\s+HOUSE\b', r'(?i)\bFAMILY\s+CHURCH\b',
]

# ── Rule 6: Orthodox ──
orthodox_patterns = [
    (r'(?i)\bORTHODOX\b', 'orthodox'),
    (r'(?i)\bGREEK\s+ORTHODOX\b', 'greek_orthodox'),
    (r'(?i)\bUKRAINIAN\s+ORTHODOX\b', 'ukrainian_orthodox'),
    (r'(?i)\bRUSSIAN\s+ORTHODOX\b', 'russian_orthodox'),
    (r'(?i)\bSERBIAN\s+ORTHODOX\b', 'serbian_orthodox'),
    (r'(?i)\bANTIOCHIAN\b', 'antiochian_orthodox'),
    (r'(?i)\bCOPTIC\b', 'coptic_orthodox'),
]

# ── Rule 7: Jewish ──
jewish_patterns = [
    r'(?i)\bSYNAGOGUE\b', r'(?i)\bTEMPLE\s+ISRAEL\b',
    r'(?i)\bBETH\s+(ISRAEL|TIKVAH|SHALOM|TORAH|EL|ZION|JACOB|DAVID)\b',
    r'(?i)\bCONGREGATION\b', r'(?i)\bJEWISH\b',
    r'(?i)\bCHABAD\b', r'(?i)\bHEBREW\b',
]

# ── Rule 8: Muslim ──
muslim_patterns = [
    r'(?i)\bMOSQUE\b', r'(?i)\bMASJID\b',
    r'(?i)\bISLAMIC\b', r'(?i)\bMUSLIM\b',
    r'(?i)\bISLAM\b',
]

# ── Rule 9: Sikh ──
sikh_patterns = [
    r'(?i)\bGURDWARA\b', r'(?i)\bSIKH\b',
    r'(?i)\bKHALSA\b', r'(?i)\bSINGH\s+SABHA\b',
]

# ── Rule 10: Hindu ──
hindu_patterns = [
    r'(?i)\bMANDIR\b', r'(?i)\bHINDU\b',
    r'(?i)\bSANATAN\b', r'(?i)\bVEDIC\b',
]

# ── Rule 11: Buddhist ──
buddhist_patterns = [
    r'(?i)\bBUDDHIST\b', r'(?i)\bZEN\b',
    r'(?i)\bSHAMBHALA\b', r'(?i)\bFO\s+GUANG\b',
    r'(?i)\bVAJRAYANA\b', r'(?i)\bTHERAVADA\b', r'(?i)\bMAHAYANA\b',
]

# ── Generic Christian markers (used for non-denom fallthrough) ──
generic_christian = [
    r'(?i)\bCHURCH\b', r'(?i)\bEGLISE\b', r'(?i)\bCHAPEL\b',
    r'(?i)\bCHRISTIAN\b', r'(?i)\bCHRETIEN\b', r'(?i)\bJESUS\b', r'(?i)\bCHRIST\b',
    r'(?i)\bMINISTRY\b', r'(?i)\bMINISTERES?\b', r'(?i)\bWORSHIP\b',
    r'(?i)\bGOSPEL\b', r'(?i)\bPASTORAL\b', r'(?i)\bFELLOWSHIP\b',
]

def classify_canadian(name, state_prov):
    """Apply Rules 2-11 to a Canadian church name."""
    
    # Rule 7: Jewish (high confidence, check early)
    for pat in jewish_patterns:
        if re.search(pat, name):
            return ('jewish', None, 0.95, 'canadian_name_heuristic_jewish')
    
    # Rule 8: Muslim
    for pat in muslim_patterns:
        if re.search(pat, name):
            return ('muslim', None, 0.95, 'canadian_name_heuristic_muslim')
    
    # Rule 9: Sikh
    for pat in sikh_patterns:
        if re.search(pat, name):
            return ('sikh', None, 0.95, 'canadian_name_heuristic_sikh')
    
    # Rule 10: Hindu
    for pat in hindu_patterns:
        if re.search(pat, name):
            return ('hindu', None, 0.95, 'canadian_name_heuristic_hindu')
    
    # Rule 11: Buddhist
    for pat in buddhist_patterns:
        if re.search(pat, name):
            return ('buddhist', None, 0.90, 'canadian_name_heuristic_buddhist')
    
    # Rule 2: Catholic
    for pat in catholic_patterns:
        if re.search(pat, name):
            return ('christian', 'catholic', 0.90, 'canadian_name_heuristic_catholic')
    
    # Rule 6: Orthodox
    for pat, subtrad in orthodox_patterns:
        if re.search(pat, name):
            return ('christian', subtrad, 0.95, 'canadian_name_heuristic_orthodox')
    
    # Rule 3: Mainline Protestant
    for pat, subtrad in mainline_patterns:
        if re.search(pat, name):
            return ('christian', subtrad, 0.85, 'canadian_name_heuristic_mainline')
    
    # Rule 4: Evangelical/Pentecostal (check before generic)
    for pat, subtrad in evangelical_patterns:
        if re.search(pat, name):
            return ('christian', subtrad, 0.80, 'canadian_name_heuristic_evangelical')
    
    # Baptist (generic catch after specific Baptist patterns)
    if re.search(r'(?i)\bBAPTIST\b', name):
        return ('christian', 'baptist', 0.85, 'canadian_name_heuristic_baptist')
    
    # Methodist (generic)
    if re.search(r'(?i)\bMETHODIST\b', name):
        return ('christian', 'methodist', 0.85, 'canadian_name_heuristic_methodist')
    
    # Rule 5: Non-Denom
    is_christian = any(re.search(p, name) for p in generic_christian)
    is_nondenom = any(re.search(p, name) for p in nondenom_patterns)
    
    if is_nondenom and is_christian:
        return ('christian', 'non_denominational', 0.70, 'canadian_name_heuristic_nondenom')
    
    # Generic Christian
    if is_christian:
        # Geo-inference (Rules 12-14) - lightweight version
        if state_prov == 'QC':
            return ('christian', 'catholic', 0.55, 'canadian_geo_heuristic_quebec')
        if state_prov in ('SK', 'MB'):
            return ('christian', 'united_church_of_canada', 0.60, 'canadian_geo_heuristic_prairie')
        if state_prov in ('AB', 'BC'):
            return ('christian', 'evangelical', 0.60, 'canadian_geo_heuristic_west')
        return ('christian', None, 0.50, 'canadian_name_heuristic_generic_christian')
    
    # Fallback
    return ('unknown', None, 0.10, 'canadian_name_heuristic_unknown')

# ── Apply ──
print('=== Canadian Classifier ===')
ca_churches = conn.execute("""
    SELECT id, name, state FROM churches 
    WHERE country='CA' 
    AND (faith_tradition IS NULL OR faith_tradition = '')
    AND name != ''
""").fetchall()
print(f'  CA churches to classify: {len(ca_churches):,}')

batch = []
classified = 0
for id_, name, state in ca_churches:
    ft, sub, conf, source = classify_canadian(name, state)
    batch.append((ft, sub, conf, source, now, '1.0', id_))
    classified += 1
    if len(batch) >= 5000:
        conn.executemany("""UPDATE churches SET 
            faith_tradition=?, subtradition=?, confidence_score=?,
            classification_source=?, classification_timestamp=?, classification_version=?
            WHERE id=?""", batch)
        conn.commit()
        print(f'    {classified:,} committed...', flush=True)
        batch = []

if batch:
    conn.executemany("""UPDATE churches SET 
        faith_tradition=?, subtradition=?, confidence_score=?,
        classification_source=?, classification_timestamp=?, classification_version=?
        WHERE id=?""", batch)
    conn.commit()

# ── Stats ──
print(f'\n=== CLASSIFICATION RESULTS (Canada) ===')
for r in conn.execute("""
    SELECT faith_tradition, subtradition, COUNT(*) n, ROUND(AVG(confidence_score),2) avg_conf
    FROM churches WHERE country='CA'
    GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 20
"""):
    print(f'  {r[0] or "?":20s} {r[1] or "?":25s} {r[2]:>8,}  conf={r[3]}')

total = conn.execute("SELECT COUNT(*) FROM churches WHERE country='CA'").fetchone()[0]
classified_ca = conn.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND faith_tradition IS NOT NULL AND faith_tradition != ''").fetchone()[0]
print(f'\n  Total CA: {total:,} | Classified: {classified_ca:,} ({100*classified_ca/total:.1f}%)')

# ── Samples ──
print('\n=== SAMPLES ===')
for ft, sub in [('christian','catholic'), ('christian','united_church_of_canada'),
                ('christian','anglican_church_of_canada'), ('christian','baptist'),
                ('christian','pentecostal'), ('christian','non_denominational'),
                ('jewish',None), ('muslim',None), ('sikh',None)]:
    row = conn.execute("""
        SELECT name, city, state, confidence_score FROM churches 
        WHERE country='CA' AND faith_tradition=? AND COALESCE(subtradition,'')=COALESCE(?, '')
        LIMIT 2
    """, (ft, sub or '')).fetchall()
    if row:
        print(f'  {ft}/{sub or "none"}:')
        for r in row:
            print(f'    "{r[0][:50]:50s}" {r[1]:15s} {r[2]}  conf={r[3]}')

conn.close()
print('Done.')
