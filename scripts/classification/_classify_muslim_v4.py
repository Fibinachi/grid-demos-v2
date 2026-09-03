#!/usr/bin/env python3
"""
_classify_muslim_v4.py — FAST Muslim doctrinal classifier.

Strategy: classify in memory, bulk-load into temp table, single UPDATE FROM.
"""
import sqlite3, re, sys, time

DB = r'E:\grid\churches.db'

PATTERNS = [
    (re.compile(r'\bimam\s*(jaafar|ali|hussein|mahdi|zaman|sadiq|khomeini|khamenei|sadr)\b', re.I), 'Shia (Twelver)', 0.65),
    (re.compile(r'\bja[?]?afari\b', re.I), 'Shia (Twelver)', 0.95),
    (re.compile(r'\b(ahlul[\-\s]?bayt|ahl[\-\s]?al[\-\s]?bayt)\b', re.I), 'Shia (Twelver)', 0.95),
    (re.compile(r'\bimam[\-\s]?(zaman|mahdi)\s*(center|masjid|mosque|islamic)\b', re.I), 'Shia (Twelver)', 0.65),
    (re.compile(r'\bhusayniyya\b', re.I), 'Shia (Twelver)', 0.65),
    (re.compile(r'\bmajlis\b', re.I), 'Shia (Twelver)', 0.65),
    (re.compile(r'\bmuharram\b', re.I), 'Shia (Twelver)', 0.65),
    (re.compile(r'\bimambargha?\b', re.I), 'Shia (Twelver)', 0.65),
    (re.compile(r'\bazakhana\b', re.I), 'Shia (Twelver)', 0.65),
    (re.compile(r'\bqom\b', re.I), 'Shia (Twelver)', 0.65),
    (re.compile(r'\b(imam)\s*al[\-\s]?(sadiq|ridha|kadhim|askari|baqir|hadi)\b', re.I), 'Shia (Twelver)', 0.95),
    (re.compile(r'\bismaili\b', re.I), 'Shia (Ismaili)', 0.95),
    (re.compile(r'\bjamatkhana\b', re.I), 'Shia (Ismaili)', 0.95),
    (re.compile(r'\baga[\-\s]?khan\b', re.I), 'Shia (Ismaili)', 0.95),
    (re.compile(r'\bbohra\b', re.I), 'Shia (Bohra)', 0.95),
    (re.compile(r'\bdawoodi\s*bohra\b', re.I), 'Shia (Bohra)', 0.95),
    (re.compile(r'\bal[\-\s]?jamea\s*al[\-\s]?saifiyah\b', re.I), 'Shia (Bohra)', 0.95),
    (re.compile(r'\bsyedna\b', re.I), 'Shia (Bohra)', 0.95),
    (re.compile(r'\b(sufi|tasawwuf|tariqa[th]?)\b', re.I), 'Sunni (Sufi)', 0.65),
    (re.compile(r'\bnagh?shbandi\b', re.I), 'Sunni (Sufi)', 0.95),
    (re.compile(r'\bqadiri\b', re.I), 'Sunni (Sufi)', 0.95),
    (re.compile(r'\bchishti\b', re.I), 'Sunni (Sufi)', 0.95),
    (re.compile(r'\bsuhrawardi\b', re.I), 'Sunni (Sufi)', 0.95),
    (re.compile(r'\b(mawlana|mevlana)\s*(rumi|roomi)\b', re.I), 'Sunni (Sufi)', 0.85),
    (re.compile(r'\bzawiya\b', re.I), 'Sunni (Sufi)', 0.65),
    (re.compile(r'\b(dergah|dargah)\b', re.I), 'Sunni (Sufi)', 0.65),
    (re.compile(r'\bzikr\s*(center|house|majlis)\b', re.I), 'Sunni (Sufi)', 0.75),
    (re.compile(r'\bbarelvi\b', re.I), 'Sunni (Sufi)', 0.95),
    (re.compile(r'\bahl[\-\s]?al[\-\s]?sunnah\s*(wal[\-\s]?jamaah)?\b', re.I), 'Sunni (Generic)', 0.75),
    (re.compile(r'\bsalafi\b', re.I), 'Sunni (Salafi)', 0.95),
    (re.compile(r'\bahl[\-\s]?al[\-\s]?hadith\b', re.I), 'Sunni (Salafi)', 0.95),
    (re.compile(r'\bminhaj[\-\s]?al[\-\s]?sunnah\b', re.I), 'Sunni (Salafi)', 0.95),
    (re.compile(r'\bdeobandi\b', re.I), 'Sunni (Deobandi)', 0.95),
    (re.compile(r'\btablighi\s*jamaat?\b', re.I), 'Sunni (Deobandi)', 0.85),
    (re.compile(r'\bdarul?\s*ul[ou]m\b', re.I), 'Sunni (Deobandi)', 0.75),
    (re.compile(r'\bmuslim\s*brotherhood\b', re.I), 'Sunni (Ikhwani)', 0.85),
    (re.compile(r'\bikhwan\b', re.I), 'Sunni (Ikhwani)', 0.85),
    (re.compile(r'\bislamic\s*society\b', re.I), 'Sunni (Ikhwani)', 0.65),
    (re.compile(r'\bhanafi\b', re.I), 'Sunni (Hanafi)', 0.95),
    (re.compile(r'\bmaliki\b', re.I), 'Sunni (Maliki)', 0.95),
    (re.compile(r'\bshafi[ie]\b', re.I), 'Sunni (Shafii)', 0.95),
    (re.compile(r'\bhanbali\b', re.I), 'Sunni (Hanbali)', 0.95),
    (re.compile(r'\bnation\s*of\s*islam\b', re.I), 'Nation of Islam', 0.95),
    (re.compile(r'\bmoorish\s*science\b', re.I), 'Nation of Islam', 0.85),
    (re.compile(r'\bmoorish\s*temple\b', re.I), 'Nation of Islam', 0.85),
    (re.compile(r'\bahmadiyya?\b', re.I), 'Ahmadiyya', 0.95),
    (re.compile(r'\bmessiah\s*(masjid|mosque|islamic)\b', re.I), 'Ahmadiyya', 0.85),
    (re.compile(r'\bquran\s*(only|alone|center)\b', re.I), 'Quranist', 0.95),
    (re.compile(r'\bmasjid\s*(al[\-\s])?haram\b', re.I), 'Sunni (Generic)', 0.65),
    (re.compile(r'\bjumat?\s*(mosque|masjid)\b', re.I), 'Sunni (Generic)', 0.65),
    (re.compile(r'\bjumu[ae]ah?\b', re.I), 'Sunni (Generic)', 0.65),
    (re.compile(r'\bdarul?\s*isl[ae]m\b', re.I), 'Sunni (Generic)', 0.65),
    (re.compile(r'\bislamic\s*center\b', re.I), 'Sunni (Generic)', 0.30),
    (re.compile(r'\bmasjid\b', re.I), 'Sunni (Generic)', 0.30),
    (re.compile(r'\bmosque\b', re.I), 'Sunni (Generic)', 0.30),
]

GEO = {
    'IR': ('Shia (Twelver)', 0.50), 'IQ': ('Shia (Twelver)', 0.40),
    'BH': ('Shia (Twelver)', 0.45), 'LB': ('Shia (Twelver)', 0.45),
    'AZ': ('Shia (Twelver)', 0.50), 'YE': ('Shia (Zaydi)', 0.40),
    'OM': ('Shia (Ibadi)', 0.40), 'SA': ('Sunni (Salafi)', 0.30),
    'QA': ('Sunni (Salafi)', 0.30), 'AE': ('Sunni (Salafi)', 0.30),
    'PK': ('Sunni (Hanafi)', 0.40), 'BD': ('Sunni (Hanafi)', 0.40),
    'IN': ('Sunni (Hanafi)', 0.30), 'AF': ('Sunni (Hanafi)', 0.35),
    'TR': ('Sunni (Hanafi)', 0.40), 'ID': ('Sunni (Shafii)', 0.40),
    'MY': ('Sunni (Shafii)', 0.40), 'EG': ('Sunni (Maliki)', 0.30),
    'NG': ('Sunni (Maliki)', 0.30), 'SN': ('Sunni (Sufi)', 0.35),
    'MA': ('Sunni (Sufi)', 0.30), 'DZ': ('Sunni (Maliki)', 0.30),
}

CITIES = {
    'qom': ('Shia (Twelver)', 0.85), 'karachi': ('Shia (Twelver)', 0.35),
    'lucknow': ('Shia (Twelver)', 0.50), 'najaf': ('Shia (Twelver)', 0.75),
    'karbala': ('Shia (Twelver)', 0.75),
}

# ── Connect ──────────────────────────────────────────────────
conn = sqlite3.connect(DB, timeout=120)
conn.execute('PRAGMA journal_mode=WAL')
c = conn.cursor()

# Ensure columns
existing = {r[1] for r in c.execute('PRAGMA table_info(churches)').fetchall()}
for col, dtype in [('muslim_affiliation', 'TEXT'), ('muslim_confidence', 'REAL'),
                   ('muslim_classification_source', 'TEXT'), ('muslim_updated', 'TEXT')]:
    if col not in existing:
        c.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')

# ── Load ─────────────────────────────────────────────────────
print('Loading Islam records...', flush=True)
rows = c.execute("""
    SELECT id, name, COALESCE(name_transliterated, name), city, state, country
    FROM churches
    WHERE faith = 'Islam'
      AND (muslim_affiliation IS NULL OR muslim_affiliation = '')
    ORDER BY id
""").fetchall()
print(f'Loaded {len(rows):,} records', flush=True)

# ── Classify ─────────────────────────────────────────────────
print('Classifying...', flush=True)
name_m = city_m = geo_m = 0
tmp = []  # (id, aff, conf, src)
d = {}    # dedup by id

for row in rows:
    rid, name, translit, city, state, country = row
    nl = (name or '').lower()
    tl = (translit or '').lower()
    cl = (city or '').lower()
    hit = None

    for pat, aff, conf in PATTERNS:
        if pat.search(nl):
            hit = (aff, conf, 'name_pattern')
            name_m += 1
            break
        elif tl != nl and pat.search(tl):
            hit = (aff, conf, 'name_pattern_translit')
            name_m += 1
            break

    if not hit and cl in CITIES:
        hit = (CITIES[cl][0], CITIES[cl][1], 'city_cluster')
        city_m += 1

    if not hit:
        sc = (state or '').upper() or (country or '').upper()
        if sc in GEO:
            hit = (GEO[sc][0], GEO[sc][1], 'geo_inference')
            geo_m += 1

    if hit:
        d[rid] = hit  # dedup by id

print(f'Name: {name_m:,} | City: {city_m:,} | Geo: {geo_m:,}', flush=True)
print(f'Unique to write: {len(d):,}', flush=True)

if not d:
    print('Nothing to update')
    sys.exit(0)

# ── Write via temp table + single UPDATE FROM ───────────────
print('Writing to temp table...', flush=True)
c.execute('DROP TABLE IF EXISTS _muslim_updates')
c.execute('CREATE TEMP TABLE _muslim_updates(id INTEGER, affiliation TEXT, confidence REAL, source TEXT)')

batch = []
for rid, (aff, conf, src) in d.items():
    batch.append((rid, aff, conf, src))
    if len(batch) >= 100000:
        conn.executemany('INSERT INTO _muslim_updates VALUES (?,?,?,?)', batch)
        conn.commit()
        batch = []
if batch:
    conn.executemany('INSERT INTO _muslim_updates VALUES (?,?,?,?)', batch)
    conn.commit()
print(f'  {len(d):,} rows in temp table', flush=True)

print('Bulk UPDATE FROM...', flush=True)
t0 = time.time()
c.execute("""
    UPDATE churches SET
        muslim_affiliation = u.affiliation,
        muslim_confidence = u.confidence,
        muslim_classification_source = u.source,
        muslim_updated = datetime('now')
    FROM _muslim_updates u
    WHERE churches.id = u.id
""")
conn.commit()
print(f'  Updated {c.rowcount:,} records in {time.time()-t0:.1f}s', flush=True)

c.execute('DROP TABLE IF EXISTS _muslim_updates')
conn.commit()

# ── Report ───────────────────────────────────────────────────
print('\nDoctrinal breakdown:')
report = c.execute("""
    SELECT muslim_affiliation, COUNT(*) as cnt, ROUND(AVG(muslim_confidence), 3) as avg_conf
    FROM churches WHERE muslim_affiliation IS NOT NULL AND muslim_affiliation != ''
    GROUP BY muslim_affiliation ORDER BY cnt DESC
""").fetchall()
for aff, cnt, conf in report:
    print(f'  {aff}: {cnt:,} (avg conf={conf})')

total_c = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND muslim_affiliation IS NOT NULL AND muslim_affiliation != ''").fetchone()[0]
print(f'\nTotal Islam classified: {total_c:,}')
conn.close()
print('Done!', flush=True)
