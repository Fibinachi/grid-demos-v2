"""Full scope of Jewish misclassification issues."""
import sqlite3

c = sqlite3.connect(r'E:\grid\churches.db')

# === ISSUE 1: osm_import country code errors ===
# SA entries with Israel coordinates
sa_israel = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='SA' AND source='osm_import'
    AND latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0
""").fetchone()[0]

# JO entries with Israel coordinates  
jo_israel = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='JO' AND source='osm_import'
    AND latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0
""").fetchone()[0]

# SA entries with Iran coordinates (lon ~48-64, lat ~25-40)
sa_iran = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='SA' AND source='osm_import'
    AND (latitude BETWEEN 25.0 AND 40.0 AND longitude BETWEEN 44.0 AND 64.0)
    AND NOT (latitude BETWEEN 29.0 AND 34.0 AND longitude BETWEEN 34.0 AND 37.0)
""").fetchone()[0]

print("=== ISSUE 1: osm_import country code errors ===")
print(f"  SA entries at Israel coordinates (→IL): {sa_israel:,}")
print(f"  JO entries at Israel coordinates (→IL): {jo_israel:,}")
print(f"  SA entries at Iran coordinates (→IR): {sa_iran:,}")
total_country = sa_israel + jo_israel + sa_iran
print(f"  TOTAL country code fixes: {total_country:,}")

# === ISSUE 2: holy_sites_import misclassifications ===
# Strategy: Count landscape/holy sites with name patterns that clearly aren't Jewish

# 2a. Thailand Buddhist temples
th_buddhist = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='TH' AND source='holy_sites_import'
    AND (name LIKE '%วัด%' OR name LIKE '%ศาล%' OR name LIKE '%สำนัก%' OR name LIKE '%สถูป%' OR name LIKE '%กุฏิ%' OR name LIKE '%สวน%')
""").fetchone()[0]
th_remaining = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='TH' AND source='holy_sites_import'
    AND name NOT LIKE '%วัด%' AND name NOT LIKE '%ศาล%' AND name NOT LIKE '%สำนัก%' AND name NOT LIKE '%สถูป%' AND name NOT LIKE '%กุฏิ%' AND name NOT LIKE '%สวน%'
""").fetchone()[0]

# 2b. ST: all have QID names or vague names - likely misclassified
st_likely_bad = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='ST' AND source='holy_sites_import'
""").fetchone()[0]

# 2c. ID: Hindu/Chinese temple names misclassified
id_bad = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='ID' AND source='holy_sites_import'
    AND (name LIKE '%Pura%' OR name LIKE '%Klenteng%' OR name LIKE '%Makam%' OR name LIKE '%Panti%' OR name LIKE '%Vihara%')
""").fetchone()[0]
id_total = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='ID' AND source='holy_sites_import'
""").fetchone()[0]

# 2d. CN: check for Chinese Buddhist names
cn_bad = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='CN' AND source='holy_sites_import'
    AND (name LIKE '%寺%' OR name LIKE '%庙%' OR name LIKE '%祠%' OR name LIKE '%庵%')
""").fetchone()[0]
cn_total = c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith='Jewish' AND country='CN' AND source='holy_sites_import'
""").fetchone()[0]

# 2e. BR: entries that are clearly NOT Jewish (Christian names, random businesses)
br_sample = c.execute("""
    SELECT name FROM churches 
    WHERE faith='Jewish' AND country='BR' AND source='holy_sites_import'
    AND (name LIKE '%Igreja%' OR name LIKE '%Matriz%' OR name LIKE '%Djoy%' OR name LIKE '%Tattoo%' OR name LIKE '%Mahikari%' OR name LIKE '%Osun%' OR name LIKE '%Assembleia%' OR name LIKE '%Geracao%' OR name LIKE '%Evangelica%')
""").fetchall()
br_bad_names = len(br_sample)

# 2f. Broad check: holy_sites_import Jewish entries NOT in core Jewish countries that have suspicious names
# Let's check all non-core countries for QID-only names
non_core_qids = c.execute("""
    SELECT country, COUNT(*) as cnt
    FROM churches 
    WHERE faith='Jewish' AND source='holy_sites_import'
      AND country NOT IN ('US','IL')
      AND name LIKE 'Q%'
    GROUP BY country
    HAVING cnt >= 3
    ORDER BY cnt DESC
""").fetchall()
print(f"\n=== Non-core countries with QID-named holy_sites Jewish entries ===")
for r in non_core_qids:
    print(f"  {r[0]:4s}: {r[1]:>5,}")

# 2g. Summary
print(f"\n=== ISSUE 2: holy_sites_import misclassifications (partial, sampling) ===")
print(f"  TH Buddhist temples misclassified: {th_buddhist:,} (+ ~{th_remaining} uncertain)")
print(f"  ST São Tomé (all likely bad): {st_likely_bad:,}")
print(f"  ID Hindu temples misclassified: {id_bad:,}/{id_total:,}")
print(f"  CN Buddhist names: {cn_bad:,}/{cn_total:,}")
print(f"  BR Christian/business names: {br_bad_names:,}")

# 3. Let's do the comprehensive holy_sites check: 
# Any entry with landmark_type=synagogue AND faith_tradition=Jewish AND faith=Jewish
# may be correct IF it's a real synagogue. But entries where:
# - The name contains non-Jewish religious keywords
# - OR name is just a QID with no context
# - OR country has tiny/nonexistent Jewish population
# are suspicious.

# Count holy_sites_import Jewish entries in countries with < 100 known Jews
low_jew_countries = c.execute("""
    SELECT country, COUNT(*) as cnt
    FROM churches 
    WHERE faith='Jewish' AND source='holy_sites_import'
      AND country NOT IN (
        'US','IL','DE','PL','FR','GB','UA','CA','NL','HU','CZ','AT','GR','AU',
        'IT','ZA','AR','MX','BR','RU','BY','SK','LT','LV','CH','BE','ES','PT',
        'RO','BG','RS','HR','BA','MD','SI','SE','LU','CY','GE'
      )
    GROUP BY country
    HAVING cnt >= 3
    ORDER BY cnt DESC
""").fetchall()
print(f"\n=== holy_sites_import Jewish in unexpected countries ===")
for r in low_jew_countries:
    print(f"  {r[0]:4s}: {r[1]:>5,}")

# 4. PS — check if these are real Palestinian synagogues or country-code errors
print(f"\n=== PS Jewish entries — source breakdown ===")
rows = c.execute("SELECT source, COUNT(*) FROM churches WHERE faith='Jewish' AND country='PS' GROUP BY source ORDER BY COUNT(*) DESC").fetchall()
for r in rows:
    print(f"  {r[0]:35s}: {r[1]:>5,}")

# 5. Total estimate of wrong faith=Jewish
print(f"\n=== TOTAL ESTIMATED FIXABLE ===")
print(f"  osm_import country codes: {total_country:,}")
print(f"  TH Buddhist reclassify: {th_buddhist:,}")
print(f"  ST likely reclassify (all): {st_likely_bad:,}")
print(f"  ID reclassify: {id_bad:,}")
print(f"  Grand estimate: {total_country + th_buddhist + st_likely_bad + id_bad:,}")

c.close()
