"""Audit faith misclassifications within Islam entries used by geo_inference."""
import sqlite3

conn = sqlite3.connect(r'E:\grid\churches.db')
c = conn.cursor()

# 1) Show the specific record
print("=== id=9508 MEE YUAN BUDDHIST ===")
c.execute("SELECT id, name, faith, faith_tradition, country, state, city, source FROM churches WHERE id=9508")
for r in c.fetchall():
    print(f"  id={r[0]} | {r[1]} | faith={r[2]} | trad={r[3]} | country={r[4]} | state={r[5]} | city={r[6]} | src={r[7]}")

# 2) How many geo_inference records have non-Muslim keywords in name?
print("\n=== Geo-inferred records with non-Muslim keywords ===")
non_muslim_keywords = ['buddhist', 'buddha', 'temple', 'hindu', 'church', 'christian',
                       'jesus', 'christ', 'sikh', 'gurdwara', 'jain', 'shinto',
                       'taoist', 'confucian', 'bahai', 'bahá', 'synagogue', 'moshe',
                       'bible', 'gospel', 'st. ', 'saint ', 'our lady', 'shrine',
                       'pagoda', 'monastery', 'convent', 'abbey', 'cathedral',
                       'basilica', 'chapel', 'parish', 'mission', 'presbyterian',
                       'methodist', 'baptist', 'lutheran', 'anglican', 'episcopal',
                       'catholic', 'orthodox', 'pentecostal', 'evangelical',
                       'mormon', 'lds', 'jehovah', 'adventist', 'quaker',
                       'mennonite', 'unitarian', 'salvation army',
                       'association', 'incorporated', 'inc', 'foundation',
                       'school', 'college', 'university', 'academy',
                       'hospital', 'clinic', 'center', 'centre',
                       'cultural', 'community']
where_clause = ' OR '.join([f"LOWER(name) LIKE '%{kw}%'" for kw in non_muslim_keywords])
c.execute(f"""
    SELECT id, name, country, state, muslim_affiliation, muslim_confidence
    FROM churches
    WHERE faith='Islam'
      AND muslim_classification_source='geo_inference'
      AND ({where_clause})
    ORDER BY id
    LIMIT 30
""")
results = c.fetchall()
print(f"  Found {len(results)} matching records (showing first 30):")
for r in results:
    print(f"  id={r[0]}: {str(r[1])[:55]:55s} | {r[2]} | {r[3]} | {r[4]:20s} | conf={r[5]}")

# 3) How many geo_inference records total?
c.execute("""
    SELECT COUNT(*) FROM churches
    WHERE faith='Islam' AND muslim_classification_source='geo_inference'
""")
total_geo = c.fetchone()[0]
print(f"\nTotal geo_inference records: {total_geo:,}")

# 4) Total geo_inference records with non-Muslim keywords
c.execute(f"""
    SELECT COUNT(*) FROM churches
    WHERE faith='Islam'
      AND muslim_classification_source='geo_inference'
      AND ({where_clause})
""")
total_bad = c.fetchone()[0]
print(f"Geo_inference with non-Muslim keywords: {total_bad:,}")

# 5) What about name_pattern and name_pattern_translit?
c.execute("""
    SELECT muslim_classification_source, COUNT(*)
    FROM churches WHERE muslim_affiliation IS NOT NULL AND muslim_affiliation != ''
    GROUP BY muslim_classification_source
""")
print("\n=== Source breakdown ===")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

conn.close()
