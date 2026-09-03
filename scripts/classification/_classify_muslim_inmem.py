#!/usr/bin/env python3
"""In-memory Muslim doctrinal classifier — fast, no concurrent DB lock risk."""
import sqlite3, re, sys

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
    'IR': ('Shia (Twelver)', 0.50),
    'IQ': ('Shia (Twelver)', 0.40),
    'BH': ('Shia (Twelver)', 0.45),
    'LB': ('Shia (Twelver)', 0.45),
    'AZ': ('Shia (Twelver)', 0.50),
    'YE': ('Shia (Zaydi)', 0.40),
    'OM': ('Shia (Ibadi)', 0.40),
    'SA': ('Sunni (Salafi)', 0.30),
    'QA': ('Sunni (Salafi)', 0.30),
    'AE': ('Sunni (Salafi)', 0.30),
    'PK': ('Sunni (Hanafi)', 0.40),
    'BD': ('Sunni (Hanafi)', 0.40),
    'IN': ('Sunni (Hanafi)', 0.30),
    'AF': ('Sunni (Hanafi)', 0.35),
    'TR': ('Sunni (Hanafi)', 0.40),
    'ID': ('Sunni (Shafii)', 0.40),
    'MY': ('Sunni (Shafii)', 0.40),
    'EG': ('Sunni (Maliki)', 0.30),
    'NG': ('Sunni (Maliki)', 0.30),
    'SN': ('Sunni (Sufi)', 0.35),
    'MA': ('Sunni (Sufi)', 0.30),
    'DZ': ('Sunni (Maliki)', 0.30),
}

SHIA_CITIES = {
    'qom': ('Shia (Twelver)', 0.85),
    'karachi': ('Shia (Twelver)', 0.35),
    'lucknow': ('Shia (Twelver)', 0.50),
    'najaf': ('Shia (Twelver)', 0.75),
    'karbala': ('Shia (Twelver)', 0.75),
}

conn = sqlite3.connect(DB, timeout=60)
conn.execute('PRAGMA journal_mode=WAL')
c = conn.cursor()

# Ensure columns exist
existing = {r[1] for r in c.execute('PRAGMA table_info(churches)').fetchall()}
for col, dtype in [('muslim_affiliation', 'TEXT'), ('muslim_confidence', 'REAL'),
                   ('muslim_classification_source', 'TEXT'), ('muslim_updated', 'TEXT')]:
    if col not in existing:
        c.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')

# Load all Islam records into memory
print('Loading Islam records into memory...')
rows = c.execute("""
    SELECT id, name, COALESCE(name_transliterated, name), city, state, country
    FROM churches
    WHERE faith = 'Islam'
      AND (muslim_affiliation IS NULL OR muslim_affiliation = '')
    ORDER BY id
""").fetchall()
print(f'Loaded {len(rows):,} records')

# Classify in memory
updates = []  # (affiliation, confidence, source, id)
name_matches = 0
city_matches = 0
state_matches = 0

for row in rows:
    rid, name, translit, city, state, country = row
    name_lower = (name or '').lower()
    translit_lower = (translit or '').lower()
    city_lower = (city or '').lower()
    matched = False
    
    # Name rules — check original name first, then transliterated
    for pattern, affiliation, confidence in NAME_RULES:
        if pattern.search(name_lower):
            updates.append((affiliation, confidence, 'name_pattern', rid))
            name_matches += 1
            matched = True
            break
        elif translit_lower != name_lower and pattern.search(translit_lower):
            updates.append((affiliation, confidence, 'name_pattern_translit', rid))
            name_matches += 1
            matched = True
            break
    
    if matched:
        continue
    
    # City-based Shia clusters
    if city_lower in SHIA_CITIES:
        affiliation, confidence = SHIA_CITIES[city_lower]
        updates.append((affiliation, confidence, 'city_cluster', rid))
        city_matches += 1
        continue
    
    # State/country ethnic inference
    state_or_country = (state or '').upper() or (country or '').upper()
    if state_or_country in STATE_ETHNIC:
        affiliation, confidence = STATE_ETHNIC[state_or_country]
        updates.append((affiliation, confidence, 'geo_inference', rid))
        state_matches += 1

print(f'Name matches: {name_matches:,} | City matches: {city_matches:,} | Geo matches: {state_matches:,}')
print(f'Total to update: {len(updates):,}')

if not updates:
    print('Nothing to update')
    sys.exit(0)

# ── Fast bulk write via temp table ──────────────────────────────
print(f'Writing {len(updates):,} classifications to DB via temp table...', flush=True)
c.execute("DROP TABLE IF EXISTS _muslim_updates")
c.execute("CREATE TEMP TABLE _muslim_updates(id INTEGER, affiliation TEXT, confidence REAL, source TEXT)")

BATCH_SIZE = 100000
for i in range(0, len(updates), BATCH_SIZE):
    batch = updates[i:i+BATCH_SIZE]
    conn.executemany(
        "INSERT INTO _muslim_updates(id, affiliation, confidence, source) VALUES (?, ?, ?, ?)",
        [(r[3], r[0], r[1], r[2]) for r in batch]
    )
    conn.commit()
    print(f'  ... {i+len(batch):,} written to temp table', flush=True)

# Single bulk UPDATE
print('Executing bulk UPDATE...', flush=True)
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
print(f'Updated: {c.rowcount:,} records', flush=True)

c.execute("DROP TABLE IF EXISTS _muslim_updates")
conn.commit()

# Report
print()
print('Doctrinal breakdown:')
report = c.execute("""
    SELECT muslim_affiliation, COUNT(*) as cnt,
           ROUND(AVG(muslim_confidence), 3) as avg_conf
    FROM churches
    WHERE muslim_affiliation IS NOT NULL AND muslim_affiliation != ''
    GROUP BY muslim_affiliation
    ORDER BY cnt DESC
""").fetchall()
for aff, cnt, conf in report:
    print(f'  {aff}: {cnt:,} (avg conf={conf})')

total_classified = sum(r[1] for r in report)
print(f'\nTotal classified: {total_classified:,}')
print(f'Unclassified: {len(rows) - len(updates):,}')
conn.close()
