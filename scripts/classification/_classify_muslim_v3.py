#!/usr/bin/env python3
"""
_classify_muslim_v3.py — In-memory Muslim doctrinal classifier.

Loads all Islam records, classifies by name (incl. transliterated),
city, and geo, then writes via simple batched UPDATEs.
"""
import sqlite3, re, sys, time

DB = r'E:\grid\churches.db'

NAME_RULES = [
    # Shia (Twelver)
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
    # Shia (Ismaili)
    (re.compile(r'\bismaili\b', re.I), 'Shia (Ismaili)', 0.95),
    (re.compile(r'\bjamatkhana\b', re.I), 'Shia (Ismaili)', 0.95),
    (re.compile(r'\baga[\-\s]?khan\b', re.I), 'Shia (Ismaili)', 0.95),
    (re.compile(r'\bismaili\s*tariqah\b', re.I), 'Shia (Ismaili)', 0.95),
    # Shia (Bohra)
    (re.compile(r'\bbohra\b', re.I), 'Shia (Bohra)', 0.95),
    (re.compile(r'\bdawoodi\s*bohra\b', re.I), 'Shia (Bohra)', 0.95),
    (re.compile(r'\bal[\-\s]?jamea\s*al[\-\s]?saifiyah\b', re.I), 'Shia (Bohra)', 0.95),
    (re.compile(r'\bsyedna\b', re.I), 'Shia (Bohra)', 0.95),
    # Sunni (Sufi)
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
    # Sunni (Salafi)
    (re.compile(r'\bsalafi\b', re.I), 'Sunni (Salafi)', 0.95),
    (re.compile(r'\bahl[\-\s]?al[\-\s]?hadith\b', re.I), 'Sunni (Salafi)', 0.95),
    (re.compile(r'\bminhaj[\-\s]?al[\-\s]?sunnah\b', re.I), 'Sunni (Salafi)', 0.95),
    (re.compile(r'\bdeobandi\b', re.I), 'Sunni (Deobandi)', 0.95),
    (re.compile(r'\btablighi\s*jamaat?\b', re.I), 'Sunni (Deobandi)', 0.85),
    (re.compile(r'\bdarul?\s*ul[ou]m\b', re.I), 'Sunni (Deobandi)', 0.75),
    # Sunni (Ikhwani/Revivalist)
    (re.compile(r'\bmuslim\s*brotherhood\b', re.I), 'Sunni (Ikhwani)', 0.85),
    (re.compile(r'\bikhwan\b', re.I), 'Sunni (Ikhwani)', 0.85),
    (re.compile(r'\bislamic\s*society\b', re.I), 'Sunni (Ikhwani)', 0.65),
    # Ethnic/regional Sunni
    (re.compile(r'\bhanafi\b', re.I), 'Sunni (Hanafi)', 0.95),
    (re.compile(r'\bmaliki\b', re.I), 'Sunni (Maliki)', 0.95),
    (re.compile(r'\bshafi[ie]\b', re.I), 'Sunni (Shafii)', 0.95),
    (re.compile(r'\bhanbali\b', re.I), 'Sunni (Hanbali)', 0.95),
    # Nation of Islam / Afro-American
    (re.compile(r'\bnation\s*of\s*islam\b', re.I), 'Nation of Islam', 0.95),
    (re.compile(r'\bmoorish\s*science\b', re.I), 'Nation of Islam', 0.85),
    (re.compile(r'\bmoorish\s*temple\b', re.I), 'Nation of Islam', 0.85),
    # Ahmadiyya
    (re.compile(r'\bahmadiyya?\b', re.I), 'Ahmadiyya', 0.95),
    (re.compile(r'\bmessiah\s*(masjid|mosque|islamic)\b', re.I), 'Ahmadiyya', 0.85),
    # Quranist
    (re.compile(r'\bquran\s*(only|alone|center)\b', re.I), 'Quranist', 0.95),
    # Generic Sunni strong signals
    (re.compile(r'\bmasjid\s*(al[\-\s])?haram\b', re.I), 'Sunni (Generic)', 0.65),
    (re.compile(r'\bjumat?\s*(mosque|masjid)\b', re.I), 'Sunni (Generic)', 0.65),
    (re.compile(r'\bjumu[ae]ah?\b', re.I), 'Sunni (Generic)', 0.65),
    (re.compile(r'\bdarul?\s*isl[ae]m\b', re.I), 'Sunni (Generic)', 0.65),
    (re.compile(r'\bislamic\s*center\b', re.I), 'Sunni (Generic)', 0.30),
    (re.compile(r'\bmasjid\b', re.I), 'Sunni (Generic)', 0.30),
    (re.compile(r'\bmosque\b', re.I), 'Sunni (Generic)', 0.30),
]

STATE_ETHNIC = {
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

SHIA_CITIES = {
    'qom': ('Shia (Twelver)', 0.85), 'karachi': ('Shia (Twelver)', 0.35),
    'lucknow': ('Shia (Twelver)', 0.50), 'najaf': ('Shia (Twelver)', 0.75),
    'karbala': ('Shia (Twelver)', 0.75),
}

conn = sqlite3.connect(DB, timeout=120)
conn.execute('PRAGMA journal_mode=WAL')
c = conn.cursor()

# Ensure columns exist
existing = {r[1] for r in c.execute('PRAGMA table_info(churches)').fetchall()}
for col, dtype in [('muslim_affiliation', 'TEXT'), ('muslim_confidence', 'REAL'),
                   ('muslim_classification_source', 'TEXT'), ('muslim_updated', 'TEXT')]:
    if col not in existing:
        c.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')

# Load
print('Loading Islam records into memory...', flush=True)
rows = c.execute("""
    SELECT id, name, COALESCE(name_transliterated, name), city, state, country
    FROM churches
    WHERE faith = 'Islam'
      AND (muslim_affiliation IS NULL OR muslim_affiliation = '')
    ORDER BY id
""").fetchall()
print(f'Loaded {len(rows):,} records', flush=True)

# Classify
updates = []  # (id, affiliation, confidence, source)
name_matches = city_matches = state_matches = 0

for row in rows:
    rid, name, translit, city, state, country = row
    name_lower = (name or '').lower()
    translit_lower = (translit or '').lower()
    city_lower = (city or '').lower()
    matched = False

    for pat, aff, conf in NAME_RULES:
        if pat.search(name_lower):
            updates.append((rid, aff, conf, 'name_pattern'))
            name_matches += 1
            matched = True
            break
        elif translit_lower != name_lower and pat.search(translit_lower):
            updates.append((rid, aff, conf, 'name_pattern_translit'))
            name_matches += 1
            matched = True
            break

    if matched:
        continue

    if city_lower in SHIA_CITIES:
        aff, conf = SHIA_CITIES[city_lower]
        updates.append((rid, aff, conf, 'city_cluster'))
        city_matches += 1
        continue

    sc = (state or '').upper() or (country or '').upper()
    if sc in STATE_ETHNIC:
        aff, conf = STATE_ETHNIC[sc]
        updates.append((rid, aff, conf, 'geo_inference'))
        state_matches += 1

print(f'Name matches: {name_matches:,} | City matches: {city_matches:,} | Geo matches: {state_matches:,}', flush=True)
print(f'Total to update: {len(updates):,}', flush=True)

if not updates:
    print('Nothing to update')
    sys.exit(0)

# Write in batches using simple UPDATE
BATCH = 5000
print(f'Writing {len(updates):,} records in batches of {BATCH:,}...', flush=True)
t0 = time.time()
for i in range(0, len(updates), BATCH):
    batch = updates[i:i+BATCH]
    t_batch = time.time()
    for rid, aff, conf, src in batch:
        c.execute("""
            UPDATE churches SET
                muslim_affiliation = ?,
                muslim_confidence = ?,
                muslim_classification_source = ?,
                muslim_updated = datetime('now')
            WHERE id = ?
        """, (aff, conf, src, rid))
    conn.commit()
    elapsed = time.time() - t_batch
    if (i + BATCH) % 50000 == 0 or (i + BATCH) >= len(updates):
        print(f'  ... {min(i+BATCH, len(updates)):,}/{len(updates):,} written ({elapsed:.1f}s for batch)', flush=True)

print(f'Total write time: {time.time() - t0:.1f}s', flush=True)

# Report
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
