#!/usr/bin/env python3
"""Fast in-memory Muslim doctrinal classifier — load, classify, write, done."""
import sqlite3, re, sys

DB = "churches.db"
NAME_RULES = [
    # ── Shia ──
    (r'\bimam\s*(jaafar|ali|hussein|mahdi|zaman|sadiq|khomeini|khamenei|sadr)\b', 'Shia (Twelver)', 0.65, 'imam_pattern'),
    (r'\bja?afari\b', 'Shia (Twelver)', 0.95, 'jafari_keyword'),
    (r'\b(ahlul[-\s]?bayt|ahl[-\s]?al[-\s]?bayt)\b', 'Shia (Twelver)', 0.95, 'ahlulbayt'),
    (r'\bimam[-\s]?(zaman|mahdi)\s*(center|masjid|mosque|islamic)\b', 'Shia (Twelver)', 0.65, 'imam_mahdi'),
    (r'\bhusayniyya\b', 'Shia (Twelver)', 0.65, 'husayniyya'),
    (r'\bmajlis\b', 'Shia (Twelver)', 0.65, 'majlis_term'),
    (r'\bmuharram\b', 'Shia (Twelver)', 0.65, 'muharram'),
    (r'\bimambargha?\b', 'Shia (Twelver)', 0.65, 'imambargah'),
    (r'\bazakhana\b', 'Shia (Twelver)', 0.65, 'azakhana'),
    (r'\bqom\b', 'Shia (Twelver)', 0.65, 'qom_reference'),
    (r'\b(imam|imam)\s*al[-\s]?(sadiq|ridha|kadhim|askari|baqir|hadi)\b', 'Shia (Twelver)', 0.95, 'imam_name'),
    (r'\bismaili\b', 'Shia (Ismaili)', 0.95, 'ismaili_name'),
    (r'\bjamatkhana\b', 'Shia (Ismaili)', 0.95, 'jamatkhana'),
    (r'\baga[-\s]?khan\b', 'Shia (Ismaili)', 0.95, 'aga_khan'),
    (r'\bbohra\b', 'Shia (Bohra)', 0.95, 'bohra_name'),
    (r'\bdawoodi\s*bohra\b', 'Shia (Bohra)', 0.95, 'dawoodi_bohra'),
    (r'\bal[-\s]?jamea\s*al[-\s]?saifiyah\b', 'Shia (Bohra)', 0.95, 'jamea_saifiyah'),
    (r'\bsyedna\b', 'Shia (Bohra)', 0.95, 'syedna'),
    # ── Sufi ──
    (r'\b(sufi|tasawwuf|tariqa[th]?)\b', 'Sunni (Sufi)', 0.65, 'sufi_name'),
    (r'\bnaqshbandi\b', 'Sunni (Sufi)', 0.95, 'naqshbandi'),
    (r'\bqadiri\b', 'Sunni (Sufi)', 0.95, 'qadiri'),
    (r'\bchishti\b', 'Sunni (Sufi)', 0.95, 'chishti'),
    (r'\bsuhrawardi\b', 'Sunni (Sufi)', 0.95, 'suhrawardi'),
    (r'\bnimatullahi\b', 'Sunni (Sufi)', 0.95, 'nimatullahi'),
    (r'\bdargah\b', 'Sunni (Sufi)', 0.65, 'dargah'),
    (r'\bziarat\b', 'Sunni (Sufi)', 0.65, 'ziarat'),
    (r'\b(mawlid|milad)\s*(un[-\s]?nabi|nabi|program|celebration)\b', 'Sunni (Sufi)', 0.75, 'mawlid'),
    (r'\bdhikr\b', 'Sunni (Sufi)', 0.65, 'dhikr'),
    (r'\b(shah|peer|pir|wali)\b', 'Sunni (Sufi)', 0.50, 'sufi_title'),
    (r'\b(urs|khanqah|ribat|zawiya)\b', 'Sunni (Sufi)', 0.65, 'sufi_institution'),
    # ── Salafi ──
    (r'\bsalafi\b', 'Sunni (Salafi)', 0.95, 'salafi_name'),
    (r'\bahl[-\s]?al[-\s]?hadith\b', 'Sunni (Salafi)', 0.95, 'ahl_hadith'),
    (r'\bminhaj[-\s]?al[-\s]?sunnah\b', 'Sunni (Salafi)', 0.95, 'minhaj_sunnah'),
    (r'\bdar[-\s]?ul[-\s]?(hadith|hadis)\b', 'Sunni (Salafi)', 0.65, 'dar_ul_hadith'),
    # ── Other ──
    (r'\b(masjid|mosque|musallah|musalla|jami[ae])\b', 'Sunni (Generic)', 0.30, 'mosque_term'),
    (r'\bislamic\s*(center|society|council|foundation|association)\b', 'Sunni (Generic)', 0.30, 'islamic_org'),
    (r'\bnur\b', 'Sunni (Generic)', 0.30, 'nur_mosque'),
    (r'\bfaraj\b', 'Sunni (Generic)', 0.30, 'faraj'),
    (r'\b(muslim|islam)\b', 'Sunni (Generic)', 0.15, 'generic_muslim'),
]

# Compile patterns once
PATTERNS = [(re.compile(p, re.IGNORECASE), aff, conf, src) for p, aff, conf, src in NAME_RULES]

def classify(name):
    if not name:
        return None
    for pattern, aff, conf, src in PATTERNS:
        if pattern.search(name):
            return (aff, conf, src)
    return None

# Load — use busy timeout to handle transient locks
conn = sqlite3.connect(DB, timeout=60)
c = conn.cursor()
c.execute("PRAGMA busy_timeout=30000")
rows = c.execute("SELECT id, name FROM churches WHERE faith='Islam' AND (muslim_affiliation IS NULL OR muslim_affiliation='')").fetchall()
print(f"Loaded {len(rows):,} unclassified Islam records")

# Classify in memory — batch of 50K for progress
total = len(rows)
updates = []
for i, (cid, name) in enumerate(rows):
    result = classify(name)
    if result:
        aff, conf, src = result
        updates.append((aff, conf, src, cid))
    if i > 0 and i % 50000 == 0:
        print(f"  ... {i:,}/{total:,} processed, {len(updates):,} matched")

print(f"Matched: {len(updates):,} / {total:,}")

# Write in one transaction
c.execute("BEGIN TRANSACTION")
c.executemany(
    "UPDATE churches SET muslim_affiliation=?, muslim_confidence=?, muslim_classification_source=?, muslim_updated=datetime('now') WHERE id=?",
    updates
)
conn.commit()
print(f"Written: {len(updates):,} records")

# Verify
aff_count = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND muslim_affiliation IS NOT NULL AND muslim_affiliation!=''").fetchone()[0]
print(f"\nTotal Islam with doctrinal affiliation: {aff_count:,}")
print(f"Total Islam without: {total - len(updates):,}")

# Breakdown
c.execute("SELECT muslim_affiliation, COUNT(*) FROM churches WHERE faith='Islam' AND muslim_affiliation!='' AND muslim_affiliation IS NOT NULL GROUP BY muslim_affiliation ORDER BY COUNT(*) DESC")
print("\nDoctrinal breakdown:")
for row in c.fetchall():
    print(f"  {row[0]}: {row[1]:,}")

conn.close()
