"""Find and tag Pagan / Neo-Pagan records."""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

# ── Check existing ──────────────────────────────────────────────────────────
print("=== Existing Pagan tags ===")
c.execute("SELECT faith, religion_type, COUNT(*) FROM churches WHERE LOWER(faith) LIKE '%pagan%' OR LOWER(religion_type) LIKE '%pagan%' GROUP BY faith, religion_type")
for r in c.fetchall():
    print(f"  faith={r[0]} rel_type={r[1]}: {r[2]:,}")

# ── Find candidates across all NULL-faith records ───────────────────────────
pagan_patterns = [
    # Wicca / Witchcraft
    '%wicca%', '%wiccan%', '%witch%', '%witchcraft%',
    # Druid
    '%druid%', '%druidry%', '%druidism%',
    # Norse / Heathen
    '%asatru%', '%heathen%', '%odin%', '%odinism%', '%norse pagan%',
    # Hellenic / Kemetic / Reconstructionist
    '%hellenic%', '%kemetic%', '%reconstructionist%',
    # General Pagan / Neo-Pagan
    '%pagan%', '%neo-pagan%', '%neopagan%',
    # Goddess spirituality
    '%goddess temple%', '%goddess spirituality%', '%goddess worship%',
    # Shamanic (some, not indigenous — careful)
    '%neo-shaman%', '%core shaman%',
    # Earth-based
    '%earth-centered%', '%earth based spirituality%',
    # Circle sanctuary / nature religion
    '%circle sanctuary%', '%nature religion%',
    # Order of Bards, Ovates & Druids
    '%obod%', '%order of bards%',
]

print("\n=== Searching NULL-faith records ===")
total_found = 0
for pattern in pagan_patterns:
    c.execute(f"""
        SELECT COUNT(*) FROM churches 
        WHERE faith IS NULL AND LOWER(name) LIKE '{pattern}'
    """)
    cnt = c.fetchone()[0]
    if cnt > 0:
        total_found += cnt
        print(f"  '{pattern}': {cnt}")

print(f"\nTotal Pagan candidates: {total_found}")

# ── Show samples ────────────────────────────────────────────────────────────
print("\n=== Sample candidates ===")
c.execute(f"""
    SELECT name, city, state, country, source FROM churches 
    WHERE faith IS NULL AND (
        {' OR '.join([f"LOWER(name) LIKE '{p}'" for p in pagan_patterns])}
    )
    LIMIT 40
""")
for name, city, state, country, source in c.fetchall():
    n = str(name)[:65] if name else ''
    print(f"  {n:<65} | {str(source or '')[:35]}")

# ── Apply the tag ───────────────────────────────────────────────────────────
print("\n=== Applying faith='Pagan' ===")
where_clause = " OR ".join([f"LOWER(name) LIKE '{p}'" for p in pagan_patterns])
c.execute(f"""
    UPDATE churches SET faith='Pagan', religion_type='pagan'
    WHERE faith IS NULL AND ({where_clause})
""")
applied = c.rowcount
print(f"Tagged: {applied}")

# Also fix existing druid/pagan records that have wrong faith
c.execute("""
    UPDATE churches SET faith='Pagan', religion_type='pagan'
    WHERE faith IS NULL AND religion_type IN ('druid', 'wicca', 'pagan')
""")
print(f"Fixed by existing religion_type: {c.rowcount}")
applied += c.rowcount

conn.commit()

# ── Log ──────────────────────────────────────────────────────────────────────
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_tag_pagan.py', TS, TS,
      applied, 0, 'faith,religion_type', 'completed',
      f'Tagged {applied} Pagan/Neo-Pagan/Wicca/Druid records'))

conn.commit()

# ── Also check: records already tagged as other faith that should be Pagan ──
print("\n=== Cross-check: non-NULL faith records with Pagan names ===")
c.execute(f"""
    SELECT faith, COUNT(*) FROM churches
    WHERE faith IS NOT NULL AND faith != 'Pagan' AND faith != 'Other'
      AND ({where_clause})
    GROUP BY faith ORDER BY COUNT(*) DESC
""")
for faith, cnt in c.fetchall():
    print(f"  faith={faith}: {cnt} (should review)")

conn.close()
print(f"\nDone! Tagged {applied} as Pagan.")
