"""Fix last remaining issues from Asia scan."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Find the one problematic entry
c.execute("""
    SELECT id, name, city, country, faith, tradition, landmark_type
    FROM churches WHERE faith='Judaism' AND country IN (
        'AF','Afghanistan','AM','Armenia','AZ','Azerbaijan','BH','Bahrain',
        'BD','Bangladesh','BT','Bhutan','BN','Brunei','KH','Cambodia','CN','China',
        'CY','Cyprus','GE','Georgia','IN','India','ID','Indonesia','IR','Iran',
        'IQ','Iraq','JP','Japan','JO','Jordan','KZ','Kazakhstan','KW','Kuwait',
        'KG','Kyrgyzstan','LA','Laos','LB','Lebanon','MY','Malaysia','MV','Maldives',
        'MN','Mongolia','MM','Myanmar','NP','Nepal','KP','North Korea',
        'OM','Oman','PK','Pakistan','PS','Palestine','PH','Philippines','QA','Qatar',
        'RU','Russia','SA','Saudi Arabia','SG','Singapore','KR','South Korea',
        'LK','Sri Lanka','SY','Syria','TW','Taiwan','TJ','Tajikistan',
        'TH','Thailand','TR','Turkey','TM','Turkmenistan','AE','United Arab Emirates',
        'UZ','Uzbekistan','VN','Vietnam','YE','Yemen',
        'HK','Hong Kong','MO','Macau'
    ) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))
""")
for r in c.fetchall():
    print(f"Problematic: #{r[0]} {r[1]} {r[2]} {r[3]} faith={r[4]} trad={r[5]} type={r[6]}")
    c.execute("UPDATE churches SET landmark_type='synagogue' WHERE id=?", (r[0],))
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, 'landmark_type', ?, 'synagogue', 'deepseek_asia_cleanup')", (r[0], r[6]))
    conn.commit()
    print(f"  -> Fixed to synagogue")

# Final verification
asia = [
    'AF','Afghanistan','AM','Armenia','AZ','Azerbaijan','BH','Bahrain',
    'BD','Bangladesh','BT','Bhutan','BN','Brunei','KH','Cambodia','CN','China',
    'CY','Cyprus','GE','Georgia','IN','India','ID','Indonesia','IR','Iran',
    'IQ','Iraq','JP','Japan','JO','Jordan','KZ','Kazakhstan','KW','Kuwait',
    'KG','Kyrgyzstan','LA','Laos','LB','Lebanon','MY','Malaysia','MV','Maldives',
    'MN','Mongolia','MM','Myanmar','NP','Nepal','KP','North Korea',
    'OM','Oman','PK','Pakistan','PS','Palestine','PH','Philippines','QA','Qatar',
    'RU','Russia','SA','Saudi Arabia','SG','Singapore','KR','South Korea',
    'LK','Sri Lanka','SY','Syria','TW','Taiwan','TJ','Tajikistan',
    'TH','Thailand','TR','Turkey','TM','Turkmenistan','AE','United Arab Emirates',
    'UZ','Uzbekistan','VN','Vietnam','YE','Yemen',
    'HK','Hong Kong','MO','Macau'
]
ph = ','.join('?' for _ in asia)
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", asia)
print(f"\nRemaining problematic: {c.fetchone()[0]}")

c.execute(f"SELECT country, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) GROUP BY country ORDER BY COUNT(*) DESC", asia)
print(f"\nBy country:")
for r in c.fetchall():
    print(f"  {r[0]:25s} {r[1]:>5,}")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph})", asia)
print(f"\nTotal: {c.fetchone()[0]:,}")

conn.close()
