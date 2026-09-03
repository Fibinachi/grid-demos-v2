"""Assess non-US North America Judaism entries."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# North America countries (excluding US)
na_countries = [
    'CA', 'Canada', 'MX', 'Mexico', 'GT', 'Guatemala', 'BZ', 'Belize',
    'SV', 'El Salvador', 'HN', 'Honduras', 'NI', 'Nicaragua', 'CR', 'Costa Rica',
    'PA', 'Panama', 'CU', 'Cuba', 'JM', 'Jamaica', 'HT', 'Haiti', 'DO', 'Dominican Republic',
    'BS', 'Bahamas', 'BB', 'Barbados', 'TT', 'Trinidad and Tobago',
    'GD', 'Grenada', 'LC', 'Saint Lucia', 'VC', 'Saint Vincent',
    'DM', 'Dominica', 'AG', 'Antigua', 'KN', 'Saint Kitts',
    'PR', 'Puerto Rico', 'VI', 'Virgin Islands', 'KY', 'Cayman Islands',
    'BM', 'Bermuda', 'AW', 'Aruba', 'CW', 'Curacao', 'GL', 'Greenland',
    'MQ', 'Martinique', 'GP', 'Guadeloupe'
]

# Get all distinct non-US countries with faith='Judaism'
c.execute("SELECT DISTINCT country FROM churches WHERE faith='Judaism' ORDER BY country")
all_countries = [r[0] for r in c.fetchall()]
print(f"All countries with Judaism entries: {len(all_countries)}")

# Filter to North America
print(f"\n=== North American countries (non-US) ===")
na_total = 0
na_states = {}
for country in na_countries:
    c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country=?", (country,))
    n = c.fetchone()[0]
    if n > 0:
        # Also check by state/province
        c.execute("SELECT COALESCE(state,''), COUNT(*) FROM churches WHERE faith='Judaism' AND country=? GROUP BY state ORDER BY COUNT(*) DESC", (country,))
        states = c.fetchall()
        na_states[country] = states
        print(f"\n  {country}: {n:,} entries")
        for s in states:
            print(f"    {s[0] or 'N/A':25s} {s[1]:>5,}")
        na_total += n

print(f"\nTotal non-US North America Judaism: {na_total:,}")

# Check landmark_type distribution
print(f"\n=== Landmark type issues ===")
for country in na_countries:
    c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country=?", (country,))
    n = c.fetchone()[0]
    if n > 0:
        c.execute("""
            SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches 
            WHERE faith='Judaism' AND country=? 
            GROUP BY landmark_type ORDER BY COUNT(*) DESC
        """, (country,))
        types = c.fetchall()
        problematic = sum(t[1] for t in types if t[0] in ('church','chapel','cathedral','mosque','abbey','shrine','NULL',''))
        if problematic > 0 or n > 0:
            print(f"\n  {country} ({n:,} total):")
            for t in types:
                marker = " ⚠" if t[0] in ('church','chapel','cathedral','mosque','abbey','shrine','NULL','') else ""
                print(f"    {t[0]:25s} {t[1]:>5,}{marker}")

# Also check tradition
print(f"\n=== Tradition distribution ===")
for country in na_countries:
    c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country=?", (country,))
    n = c.fetchone()[0]
    if n > 0:
        c.execute("SELECT COALESCE(tradition,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country=? GROUP BY tradition ORDER BY COUNT(*) DESC", (country,))
        print(f"\n  {country}:")
        for t in c.fetchall():
            print(f"    {t[0]:25s} {t[1]:>5,}")

conn.close()
