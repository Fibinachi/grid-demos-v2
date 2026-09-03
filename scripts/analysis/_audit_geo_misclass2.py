"""Audit geo_inference state/country collision and faith misclassifications."""
import sqlite3

conn = sqlite3.connect(r'E:\grid\churches.db')
c = conn.cursor()

# 1) State/country collision analysis
print("=== Geo inference: State vs Country collision ===")
c.execute("""
    SELECT state, country, COUNT(*) as cnt
    FROM churches
    WHERE faith='Islam' AND muslim_classification_source='geo_inference'
    GROUP BY state, country
    ORDER BY cnt DESC
""")
for r in c.fetchall():
    state, country, cnt = r
    collision = "← STATE/COUNTRY COLLISION" if state and len(state) == 2 and state.upper() != country else ""
    print(f"  state={state}, country={country}: {cnt:,} {collision}")

# 2) How many have state that looks like a country code
print("\n=== Non-null state values in geo_inference ===")
c.execute("""
    SELECT COUNT(*) FROM churches
    WHERE faith='Islam' AND muslim_classification_source='geo_inference'
      AND state IS NOT NULL AND state != ''
""")
with_state = c.fetchone()[0]
print(f"  With state: {with_state:,}")

# 3) Faith misclassifications - non-Muslim keywords in Islam entries
print("\n=== Faith misclassifications in Islam entries ===")
non_muslim_kw = [
    ('buddhist', 'Buddhist'), ('buddha', 'Buddhist'), ('temple', 'Buddhist/Hindu'),
    ('hindu', 'Hindu'), ('sikh', 'Sikh'), ('gurdwara', 'Sikh'),
    ('jain', 'Jain'), ('shinto', 'Shinto'), ('taoist', 'Taoist'),
    ('confucian', 'Confucian'), ('synagogue', 'Jewish'),
    ('church', 'Christian'), ('christian', 'Christian'), ('jesus', 'Christian'),
    ('christ', 'Christian'), ('bible', 'Christian'), ('gospel', 'Christian'),
    ('st. ', 'Christian'), ('saint ', 'Christian'), ('our lady', 'Christian'),
    ('cathedral', 'Christian'), ('basilica', 'Christian'), ('chapel', 'Christian'),
    ('parish', 'Christian'), ('presbyterian', 'Christian'), ('methodist', 'Christian'),
    ('baptist', 'Christian'), ('lutheran', 'Christian'), ('anglican', 'Christian'),
    ('episcopal', 'Christian'), ('catholic', 'Christian'), ('orthodox', 'Christian'),
    ('pentecostal', 'Christian'), ('evangelical', 'Christian'),
    ('mormon', 'Christian'), ('jehovah', 'Christian'), ('adventist', 'Christian'),
    ('mennonite', 'Christian'), ('unitarian', 'Christian'),
]

for kw, suggested_faith in non_muslim_kw:
    c.execute("""
        SELECT COUNT(*) FROM churches
        WHERE faith='Islam' AND LOWER(name) LIKE ?
    """, (f'%{kw}%',))
    cnt = c.fetchone()[0]
    if cnt > 0:
        print(f"  '{kw}' ({suggested_faith}): {cnt:,}")

# 4) Total Islam entries with clearly non-Muslim names
print("\n=== Total potentially misclassified ===")
all_conditions = ' OR '.join([f"LOWER(name) LIKE '%{kw}%'" for kw, _ in non_muslim_kw])
c.execute(f"""
    SELECT COUNT(*) FROM churches
    WHERE faith='Islam' AND ({all_conditions})
""")
print(f"  {c.fetchone()[0]:,}")

conn.close()
