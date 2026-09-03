"""Canadian classifier — pure Python then batch UPDATE"""
import sqlite3, re, datetime

# ── Pattern library (same as before) ──
catholic_pats = [
    r'(?i)\bPARISH\b', r'(?i)\bPAROISSE\b', r'(?i)\bCATHOLIC\b',
    r'(?i)\bNOTRE.?DAME\b', r'(?i)\bOUR\s+LADY\b',
    r'(?i)\bHOLY\s+ROSARY\b', r'(?i)\bSACRED\s+HEART\b',
    r'(?i)\bIMMACULATE\b', r'(?i)\bASSUMPTION\b',
    r'(?i)\bCATHEDRAL\b', r'(?i)\bBASILICA\b', r'(?i)\bSACRE.?COEUR\b',
]

mainline_pats = [
    (r'(?i)\bUNITED\s+CHURCH\b', 'united_church_of_canada'),
    (r'(?i)\bANGLICAN\b', 'anglican_church_of_canada'),
    (r'(?i)\bPRESBYTERIAN\b', 'presbyterian_church_in_canada'),
    (r'(?i)\bLUTHERAN\b', 'lutheran'),
    (r'(?i)\bREFORMED\s+CHURCH\b', 'reformed'),
]

evangelical_pats = [
    (r'(?i)\bPENTECOSTAL\b', 'pentecostal'),
    (r'(?i)\bPAOC\b', 'pentecostal'),
    (r'(?i)\bALLIANCE\s+CHURCH\b', 'christian_and_missionary_alliance'),
    (r'(?i)\bEVANGELICAL\b', 'evangelical'),
    (r'(?i)\bCALVARY\s+CHAPEL\b', 'evangelical'),
    (r'(?i)\bFELLOWSHIP\s+BAPTIST\b', 'baptist'),
    (r'(?i)\bGOSPEL\s+CHAPEL\b', 'evangelical'),
    (r'(?i)\bTABERNACLE\b', 'evangelical'),
    (r'(?i)\bMENNONITE\b', 'mennonite'),
    (r'(?i)\bSALVATION\s+ARMY\b', 'salvation_army'),
    (r'(?i)\bNAZARENE\b', 'nazarene'),
    (r'(?i)\bBRETHREN\b', 'brethren'),
    (r'(?i)\bFREE\s+METHODIST\b', 'free_methodist'),
]

orthodox_pats = [
    (r'(?i)\bORTHODOX\b', 'orthodox'), (r'(?i)\bCOPTIC\b', 'coptic_orthodox'),
]

jewish_pats = [
    r'(?i)\bSYNAGOGUE\b', r'(?i)\bJEWISH\b', r'(?i)\bCHABAD\b', r'(?i)\bHEBREW\b',
]

muslim_pats = [r'(?i)\bMOSQUE\b', r'(?i)\bMASJID\b', r'(?i)\bISLAMIC\b', r'(?i)\bMUSLIM\b']
sikh_pats = [r'(?i)\bGURDWARA\b', r'(?i)\bSIKH\b', r'(?i)\bKHALSA\b']
hindu_pats = [r'(?i)\bMANDIR\b', r'(?i)\bHINDU\b', r'(?i)\bSANATAN\b']
buddhist_pats = [r'(?i)\bBUDDHIST\b', r'(?i)\bZEN\b', r'(?i)\bSHAMBHALA\b']

nondenom_pats = [
    r'(?i)\bCOMMUNITY\s+CHURCH\b', r'(?i)\bCHRISTIAN\s+CHURCH\b',
    r'(?i)\bLIFE\s+(CENTRE|CHURCH)\b', r'(?i)\bHOPE\s+CHURCH\b',
    r'(?i)\bFAITH\s+CHURCH\b', r'(?i)\bHARVEST\b', r'(?i)\bVINEYARD\b',
    r'(?i)\bNEW\s+LIFE\b', r'(?i)\bGATEWAY\b', r'(?i)\bCENTRE\s+CHRETIEN\b',
    r'(?i)\bFELLOWSHIP\b', r'(?i)\bCORNERSTONE\b', r'(?i)\bCROSSROADS\b',
    r'(?i)\bJOURNEY\b', r'(?i)\bMEETING\s+HOUSE\b',
]

generic_christian = [
    r'(?i)\bCHURCH\b', r'(?i)\bEGLISE\b', r'(?i)\bCHAPEL\b',
    r'(?i)\bCHRISTIAN\b', r'(?i)\bCHRETIEN\b', r'(?i)\bJESUS\b', r'(?i)\bCHRIST\b',
    r'(?i)\bMINISTRY\b', r'(?i)\bWORSHIP\b', r'(?i)\bGOSPEL\b',
]

def classify_ca(name, prov):
    for p in jewish_pats:
        if re.search(p, name): return ('jewish', None, 0.95, 'ca_name_jewish')
    for p in muslim_pats:
        if re.search(p, name): return ('muslim', None, 0.95, 'ca_name_muslim')
    for p in sikh_pats:
        if re.search(p, name): return ('sikh', None, 0.95, 'ca_name_sikh')
    for p in hindu_pats:
        if re.search(p, name): return ('hindu', None, 0.95, 'ca_name_hindu')
    for p in buddhist_pats:
        if re.search(p, name): return ('buddhist', None, 0.90, 'ca_name_buddhist')
    for p in catholic_pats:
        if re.search(p, name): return ('christian', 'catholic', 0.90, 'ca_name_catholic')
    for p, sub in orthodox_pats:
        if re.search(p, name): return ('christian', sub, 0.95, 'ca_name_orthodox')
    for p, sub in mainline_pats:
        if re.search(p, name): return ('christian', sub, 0.85, 'ca_name_mainline')
    for p, sub in evangelical_pats:
        if re.search(p, name): return ('christian', sub, 0.80, 'ca_name_evangelical')
    if re.search(r'(?i)\bBAPTIST\b', name):
        return ('christian', 'baptist', 0.85, 'ca_name_baptist')
    if re.search(r'(?i)\bMETHODIST\b', name):
        return ('christian', 'methodist', 0.85, 'ca_name_methodist')
    
    is_christian = any(re.search(p, name) for p in generic_christian)
    is_nondenom = any(re.search(p, name) for p in nondenom_pats)
    if is_nondenom and is_christian:
        return ('christian', 'non_denominational', 0.70, 'ca_name_nondenom')
    if is_christian:
        if prov == 'QC': return ('christian', 'catholic', 0.55, 'ca_geo_quebec')
        if prov in ('SK','MB'): return ('christian', 'united_church_of_canada', 0.60, 'ca_geo_prairie')
        if prov in ('AB','BC'): return ('christian', 'evangelical', 0.60, 'ca_geo_west')
        return ('christian', None, 0.50, 'ca_name_generic')
    return ('unknown', None, 0.10, 'ca_name_unknown')

# ── Main ──
conn = sqlite3.connect('churches.db')
conn.execute('PRAGMA journal_mode=DELETE')
conn.execute('PRAGMA synchronous=OFF')
now = datetime.datetime.now().isoformat()

print('Loading...')
data = conn.execute("SELECT id, name, state FROM churches WHERE country='CA' AND (faith_tradition IS NULL OR faith_tradition='') AND name!=''").fetchall()
print(f'{len(data):,} churches to classify')

print('Classifying...')
results = []
for i, (id_, nm, st) in enumerate(data):
    results.append(classify_ca(nm, st) + (now, '1.0', id_))
    if (i+1) % 20000 == 0: print(f'  {i+1:,}...', flush=True)

print(f'Updating {len(results):,} rows...')
for i in range(0, len(results), 5000):
    conn.executemany("UPDATE churches SET faith_tradition=?,subtradition=?,confidence_score=?,classification_source=?,classification_timestamp=?,classification_version=? WHERE id=?", results[i:i+5000])
    conn.commit()
    if (i+5000) % 25000 == 0: print(f'  {min(i+5000, len(results)):,}', flush=True)

# Stats
for r in conn.execute("SELECT faith_tradition, subtradition, COUNT(*) n, ROUND(AVG(confidence_score),2) c FROM churches WHERE country='CA' GROUP BY 1,2 ORDER BY 3 DESC LIMIT 18"):
    print(f'  {r[0] or "?":20s} {r[1] or "?":22s} {r[2]:>8,}  conf={r[3]}')

c = conn.execute("SELECT COUNT(*) FROM churches WHERE country='CA' AND faith_tradition!=''").fetchone()[0]
t = conn.execute("SELECT COUNT(*) FROM churches WHERE country='CA'").fetchone()[0]
print(f'Classified: {c:,} / {t:,} ({100*c/t:.1f}%)')
conn.close()
print('Done.')
