"""Bulk-classify Q-number Wikidata entries using landmark_type + country geo-priors.
Targets entries with NULL or generic tradition that the stage1 classifier will skip."""
import sqlite3, sys

DB = r"E:\grid\churches.db"
SOURCE = "q_number_bulk_classify"
CHUNK = 500

TYPE_TO_FAITH = {
    'mosque': 'Islam', 'masjid': 'Islam',
    'church': 'Christian', 'cathedral': 'Christian', 'chapel': 'Christian',
    'abbey': 'Christian', 'monastery': 'Christian', 'basilica': 'Christian',
    'synagogue': 'Judaism', 'gurdwara': 'Sikh',
    'jinja': 'Shinto', 'jingu': 'Shinto',
    'pagoda': 'Buddhist', 'stupa': 'Buddhist',
}

COUNTRY_FAITH = {
    'YE': 'Islam', 'SA': 'Islam', 'AE': 'Islam', 'QA': 'Islam', 'KW': 'Islam',
    'OM': 'Islam', 'BH': 'Islam', 'IQ': 'Islam', 'IR': 'Islam', 'SY': 'Islam',
    'JO': 'Islam', 'LB': 'Islam', 'PS': 'Islam', 'EG': 'Islam', 'LY': 'Islam',
    'TN': 'Islam', 'DZ': 'Islam', 'MA': 'Islam', 'MR': 'Islam', 'SD': 'Islam',
    'SO': 'Islam', 'DJ': 'Islam', 'KM': 'Islam', 'TR': 'Islam', 'AZ': 'Islam',
    'TM': 'Islam', 'UZ': 'Islam', 'KG': 'Islam', 'TJ': 'Islam', 'KZ': 'Islam',
    'AF': 'Islam', 'PK': 'Islam', 'BD': 'Islam', 'MV': 'Islam', 'MY': 'Islam',
    'ID': 'Islam', 'BN': 'Islam',
    'IN': 'Hindu', 'NP': 'Hindu', 'LK': 'Buddhist',
    'TH': 'Buddhist', 'KH': 'Buddhist', 'LA': 'Buddhist', 'MM': 'Buddhist',
    'BT': 'Buddhist', 'MN': 'Buddhist', 'TW': 'Buddhist', 'CN': 'Buddhist',
    'JP': 'Shinto', 'KR': 'Christian',
    'IT': 'Christian', 'ES': 'Christian', 'PT': 'Christian', 'FR': 'Christian',
    'DE': 'Christian', 'AT': 'Christian', 'CH': 'Christian', 'BE': 'Christian',
    'NL': 'Christian', 'PL': 'Christian', 'CZ': 'Christian', 'SK': 'Christian',
    'HU': 'Christian', 'RO': 'Christian', 'BG': 'Christian', 'GR': 'Christian',
    'HR': 'Christian', 'SI': 'Christian', 'LT': 'Christian', 'LV': 'Christian',
    'EE': 'Christian', 'FI': 'Christian', 'SE': 'Christian', 'NO': 'Christian',
    'DK': 'Christian', 'IS': 'Christian', 'IE': 'Christian', 'GB': 'Christian',
    'US': 'Christian', 'CA': 'Christian', 'MX': 'Christian', 'BR': 'Christian',
    'AR': 'Christian', 'CL': 'Christian', 'CO': 'Christian', 'PE': 'Christian',
    'EC': 'Christian', 'VE': 'Christian', 'BO': 'Christian', 'PY': 'Christian',
    'UY': 'Christian', 'PH': 'Christian', 'AU': 'Christian', 'NZ': 'Christian',
    'ZA': 'Christian', 'KE': 'Christian', 'GH': 'Christian',
    'TZ': 'Christian', 'UG': 'Christian', 'RW': 'Christian', 'CD': 'Christian',
    'CM': 'Christian', 'CI': 'Christian', 'AO': 'Christian', 'MZ': 'Christian',
    'ZM': 'Christian', 'ZW': 'Christian', 'MW': 'Christian', 'ET': 'Christian',
    'IL': 'Judaism',
}

FAITH_TAX = {'Christian': 2, 'Islam': 4, 'Hindu': 3, 'Buddhist': 1, 'Judaism': 5,
             'Sikh': 55, 'Jain': 46, 'Shinto': 7, 'Taoist': 59, 'Confucian': 45,
             'Bahai': 695, 'Zoroastrian': 61, 'Pagan': 53, 'Animist': 39, 'Other': 52}
FAITH_CIV = {'Christian': 'ABRAHAMIC', 'Islam': 'ABRAHAMIC', 'Judaism': 'ABRAHAMIC',
             'Bahai': 'ABRAHAMIC', 'Hindu': 'DHARMIC', 'Buddhist': 'DHARMIC',
             'Sikh': 'DHARMIC', 'Jain': 'DHARMIC', 'Shinto': 'TAOIC',
             'Taoist': 'TAOIC', 'Confucian': 'TAOIC'}

GENERIC = ['Christian','Muslim','Jewish','Hindu','Buddhist','Sikh','Jain','Taoist','Shinto','Bahai','Other','']

def resolve_faith(landmark_type, existing_faith, country):
    if existing_faith and existing_faith in FAITH_TAX and existing_faith not in ('Other', 'Non-Religious'):
        return existing_faith
    lt = (landmark_type or '').lower()
    if lt in TYPE_TO_FAITH and TYPE_TO_FAITH[lt]:
        return TYPE_TO_FAITH[lt]
    return COUNTRY_FAITH.get(country, 'Other')

db = sqlite3.connect(DB, timeout=30)
db.execute("PRAGMA journal_mode=WAL")

print("Querying Q-number candidates...", end=" ", flush=True)
ph = ','.join(['?' for _ in GENERIC])

null_rows = db.execute("""
    SELECT id, name, country, landmark_type, faith
    FROM churches WHERE name LIKE 'Q%' AND CAST(substr(name,2) AS INTEGER) > 0
    AND tradition IS NULL ORDER BY country, id
""").fetchall()

generic_rows = db.execute(f"""
    SELECT id, name, country, landmark_type, faith
    FROM churches WHERE name LIKE 'Q%' AND CAST(substr(name,2) AS INTEGER) > 0
    AND tradition IN ({ph}) ORDER BY country, id
""", GENERIC).fetchall()

rows = null_rows + generic_rows
print(f"{len(rows):,} ({len(null_rows):,} NULL + {len(generic_rows):,} generic)")

if not rows:
    print("Nothing to do.")
    db.close()
    sys.exit(0)

updates = []
for church_id, name, country, ltype, faith in rows:
    nf = resolve_faith(ltype, faith, country)
    updates.append((church_id, nf, FAITH_CIV.get(nf, 'OTHER'), FAITH_TAX.get(nf, 52), nf.lower()))

print(f"Resolved: {len(updates):,} entries")

counts = {}
for i in range(0, len(updates), CHUNK):
    batch = updates[i:i+CHUNK]
    for church_id, nf, civ, tax, trad in batch:
        db.execute("UPDATE churches SET faith=?, civilizational_family=?, taxonomy_id=?, tradition=? WHERE id=?",
                   (nf, civ, tax, trad, church_id))
        db.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?,?,?,?,?)",
                   (church_id, 'faith_classification', 'Q-number', f'{nf} via type/country', SOURCE))
        counts[nf] = counts.get(nf, 0) + 1
    db.commit()
    done = min(i + CHUNK, len(updates))
    print(f"\r  {done:,}/{len(updates):,} ({done/len(updates)*100:.1f}%)", end="")

print(f"\n\nDone. {len(updates):,} Q-number entries classified.")
for faith, cnt in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {faith:15s}: {cnt:,}")
db.close()
