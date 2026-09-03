"""Fix non-Catholic GoodLands diocese assignments.
Bucket approach:
  1. Catholic buildings misclassified as Christian → fix faith_tradition to Catholic, keep diocese
  2. Eastern Orthodox → keep diocese (valid episcopal structure)
  3. Truly non-Catholic → clear GoodLands-set fields from church_enrichment
"""
import sqlite3, json, sys
from datetime import datetime

DB = 'churches.db'
NOW = datetime.utcnow().isoformat()
SCRIPT = 'scripts/geodata/spatial_tag_dioceses.py'  # Same source for provenance
SOURCE = 'goodlands_diocesan_boundaries_v2_2019'

CATHOLIC_INDICATORS = [
    'basilica', 'basilique', 'cathedral', 'cathédrale', 'cathedrale',
    'oratory', 'oratoire', 'oratorio',
    'archdiocese', 'archdiocèse', 'archévêché', 'archevêché',
    'monsignor', 'monseigneur',
    'saint patrick', 'st patrick',
    'saint joseph', 'st joseph', 'san giuseppe',
    'santa maria', 'holy name',
    'mary, queen',
    'uspenski',
]

GOODLANDS_FIELDS = ['diocese', 'archdiocese', 'province', 'rite',
                    'catholic_hierarchy_source', 'diocese_detail', 'province_detail']


def classify(rec):
    """Classify a record into: 'catholic_misclass', 'orthodox_keep', 'clear_diocese'"""
    rid, name, faith, faith_trad, denom, country, lat, lon, dio = rec
    name_lower = (name or '').lower()
    denom_lower = (denom or '').lower()

    # Already has Roman Catholic denom but wrong faith_tradition → misclassified
    if 'roman catholic' in denom_lower:
        return 'catholic_misclass'

    # Eastern Orthodox → keep diocese (valid)
    if faith_trad == 'Orthodox' or 'orthodox' in denom_lower or \
       ('eastern orthodox' in name_lower and 'cathedral' in name_lower):
        return 'orthodox_keep'

    # Name-based Catholic indicators
    if any(ind in name_lower for ind in CATHOLIC_INDICATORS):
        return 'catholic_misclass'

    # Roman churches in Rome with generic faith=Christian → likely Catholic
    # (Pantheon, San Clemente, basilicas in Rome — all Catholic)
    # These come from Wikipedia datasets with generic denomination
    if country == 'IT' and dio == 'Diocese of Rome' and \
       faith == 'Christian' and (denom or '') in ('Christian', '', None, 'Other'):
        return 'catholic_misclass'

    # Anglican → keep diocese (valid)
    if faith_trad == 'Anglican':
        return 'anglican_keep'

    return 'clear_diocese'


def main():
    conn = sqlite3.connect(DB)
    conn.execute("PRAGMA journal_mode=WAL")
    c = conn.cursor()

    # Get all non-Catholic records with GoodLands-format diocese
    c.execute("""
        SELECT ch.id, ch.name, ch.faith, ch.faith_tradition, ch.denomination,
               ch.country, ch.latitude, ch.longitude,
               ce.diocese
        FROM churches ch
        JOIN church_enrichment ce ON ch.id = ce.church_id
        WHERE ch.faith_tradition != 'Catholic'
          AND ce.diocese IS NOT NULL AND ce.diocese != ''
          AND (ce.diocese LIKE 'Diocese of%' OR ce.diocese LIKE 'Archdiocese of%')
    """)
    rows = c.fetchall()
    print(f"\nTotal non-Catholic GoodLands records: {len(rows)}")

    buckets = {'catholic_misclass': [], 'orthodox_keep': [], 'anglican_keep': [], 'clear_diocese': []}
    for r in rows:
        cat = classify(r)
        buckets[cat].append(r[0])  # church_id

    print(f"  Catholic misclassified:    {len(buckets['catholic_misclass'])} → fix faith_tradition, keep diocese")
    print(f"  Eastern Orthodox (keep):   {len(buckets['orthodox_keep'])} → keep diocese")
    print(f"  Anglican (keep):           {len(buckets['anglican_keep'])} → keep diocese")
    print(f"  Truly non-Catholic (clear): {len(buckets['clear_diocese'])} → clear diocese fields")

    # --- Step 1: Fix faith_tradition for misclassified Catholic ---
    cat_ids = buckets['catholic_misclass']
    if cat_ids:
        placeholders = ','.join('?' * len(cat_ids))
        c.execute(f"UPDATE churches SET faith_tradition='Catholic', faith='Catholic' WHERE id IN ({placeholders})", cat_ids)
        print(f"\n  ✅ Fixed faith_tradition for {c.rowcount} misclassified Catholic records")

        # Log to provenance
        c.execute("""INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, churches_updated,
             fields_populated, parameters, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (SOURCE, SCRIPT, NOW, NOW, len(cat_ids),
             'faith_tradition,faith', '{"fix":"faith_tradition→Catholic for misclassified Catholic buildings"}',
             'completed', f'Fixed faith_tradition for {len(cat_ids)} Catholic buildings that were tagged as Christian'))
        print("  ✅ Provenance logged for faith fix")

    # --- Step 2: Clear diocese fields for truly non-Catholic ---
    clear_ids = buckets['clear_diocese']
    if clear_ids:
        placeholders = ','.join('?' * len(clear_ids))
        # Clear GoodLands-set fields
        set_null = ', '.join(f"{f}=NULL" for f in GOODLANDS_FIELDS)
        c.execute(f"UPDATE church_enrichment SET {set_null} WHERE church_id IN ({placeholders})", clear_ids)
        print(f"\n  ✅ Cleared diocese fields for {c.rowcount} truly non-Catholic records")

        # Log to provenance
        c.execute("""INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, churches_updated,
             fields_populated, parameters, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (SOURCE, SCRIPT, NOW, NOW, len(clear_ids),
             ','.join(GOODLANDS_FIELDS),
             '{"fix":"clear diocese for non-Catholic records"}',
             'completed',
             f'Cleared GoodLands diocese fields for {len(clear_ids)} non-Catholic records'))
        print("  ✅ Provenance logged for clear")

    # --- Step 3: Anglican records → set catholic_hierarchy_source to "anglican_diocese" ---
    ang_ids = buckets['anglican_keep']
    if ang_ids:
        placeholders = ','.join('?' * len(ang_ids))
        c.execute(f"""UPDATE church_enrichment
            SET catholic_hierarchy_source='anglican_diocese',
                last_updated=?
            WHERE church_id IN ({placeholders})""", (NOW,) + tuple(ang_ids))
        print(f"\n  ✅ Tagged {c.rowcount} Anglican diocese as 'anglican_diocese'")

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"Done. DB committed.")
    print(f"BUCKETS: catholic_misclass={len(cat_ids)} | orthodox_keep={len(buckets['orthodox_keep'])} | anglican={len(ang_ids)} | cleared={len(clear_ids)}")


if __name__ == '__main__':
    main()
