"""Assess Judaism entries in Asia (excluding Israel)."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Asia countries (excluding Israel)
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
    # Territories
    'HK','Hong Kong','MO','Macau'
]

placeholders = ','.join('?' for _ in asia)
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders})", asia)
total = c.fetchone()[0]
print(f"Total Judaism in Asia (ex-Israel): {total:,}")

if total > 0:
    # By country
    c.execute(f"SELECT country, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) GROUP BY country ORDER BY COUNT(*) DESC", asia)
    print(f"\nBy country:")
    for r in c.fetchall():
        print(f"  {r[0]:25s} {r[1]:>6,}")
    
    # By landmark_type
    c.execute(f"SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) GROUP BY landmark_type ORDER BY COUNT(*) DESC", asia)
    print(f"\nBy landmark_type:")
    for r in c.fetchall():
        marker = "  PROBLEM" if r[0] in ('church','chapel','cathedral','mosque','abbey','shrine','NULL','') else ""
        print(f"  {r[0]:25s} {r[1]:>6,}{marker}")
    
    # Problematic
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", asia)
    prob = c.fetchone()[0]
    print(f"\nProblematic: {prob}")
    if prob > 0:
        c.execute(f"SELECT id, name, city, country, landmark_type FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine')) ORDER BY country LIMIT 30", asia)
        for r in c.fetchall():
            print(f"  #{r[0]:>8} {str(r[1] or '')[:40]:40s} {str(r[2] or '')[:20]:20s} {str(r[3] or '')[:12]:12s} type={r[4]}")

    # By tradition
    c.execute(f"SELECT tradition, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) GROUP BY tradition ORDER BY COUNT(*) DESC", asia)
    print(f"\nBy tradition:")
    for r in c.fetchall():
        print(f"  {r[0] or 'NULL':30s} {r[1]:>5,}")

# Also check Israel separately
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel')")
israel = c.fetchone()[0]
print(f"\nIsrael (excluded): {israel:,}")

conn.close()
