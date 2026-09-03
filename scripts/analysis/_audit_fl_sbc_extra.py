"""Analyze FL churches tagged as SBC but NOT in the FLBaptist directory."""
import json, sqlite3

db = sqlite3.connect('churches.db')
c = db.cursor()

# Load FLBaptist directory church names (for name-based matching too)
with open("data/flbaptist_directory.json") as f:
    fl_churches = json.load(f)

dir_names_lower = {ch["name"].strip().lower() for ch in fl_churches}
dir_cities = {ch.get("city", "").strip().lower() for ch in fl_churches}

# Get all FL SBC churches not matched by the import's haversine check
# The import already avoided 1,839 that were within 500m of directory entries
# So ALL 4,281 FL SBC churches minus 1,839 matched = 2,442 were considered
# 806 were imported new, so 4,281 - 806 imported - 1,839 already matched = 1,636

# Get all FL SBC churches
all_fl_sbc = c.execute("""
    SELECT id, name, address, city, state, zip, latitude, longitude, source, 
           denomination, landmark_type, tradition
    FROM churches 
    WHERE state = 'FL' AND LOWER(denomination) LIKE '%southern baptist%'
    ORDER BY name
""").fetchall()

print(f"Total FL SBC in DB: {len(all_fl_sbc)}")

# Separate into "in directory" vs "extra"
in_dir = []
extra = []
for row in all_fl_sbc:
    ch_id, name, address, city, state, zip_, lat, lon, source, denom, lm, ft = row
    name_lower = name.strip().lower() if name else ""
    # Check if name appears in directory
    if name_lower in dir_names_lower:
        in_dir.append(row)
    else:
        extra.append(row)

print(f"Name-matched to directory: {len(in_dir)}")
print(f"Extra (not name-matched): {len(extra)}")

# Source breakdown of extras
from collections import Counter
source_counts = Counter()
for row in extra:
    source_counts[row[8]] += 1

print("\n=== Source breakdown of extra FL SBC ===")
for src, cnt in source_counts.most_common():
    print(f"  {src}: {cnt}")

# Denomination variety
denom_counts = Counter()
for row in extra:
    denom_counts[row[9]] += 1

print("\n=== Denomination values of extras ===")
for d, cnt in denom_counts.most_common(20):
    print(f"  '{d}': {cnt}")

# Name patterns that might indicate misclassification
print("\n=== Name patterns suggesting non-SBC ===")
patterns = [
    ("Catholic", "Catholic"),
    ("Methodist", "Methodist"),
    ("Lutheran", "Lutheran"),
    ("Episcopal", "Episcopal"),
    ("Presbyterian", "Presbyterian"),
    ("Pentecostal", "Pentecostal"),
    ("Assembly of God", "Assembly of God"),
    ("Church of God", "Church of God"),
    ("Jehovah", "Jehovah"),
    ("Mormon|LDS|Latter.day", "LDS"),
    ("Adventist", "Adventist"),
    ("Buddhist|Temple", "Buddhist/Temple"),
    ("Mosque|Islamic|Muslim", "Islamic"),
    ("Synagogue|Jewish", "Jewish"),
    ("7th Day|Seventh.day", "Seventh Day"),
    ("Christian Church", "Christian Church (generic)"),
    ("Church of Christ", "Church of Christ"),
    ("Non.Denominational|NonDenom|Nondenom", "Non-denom"),
    ("Bible Church", "Bible Church"),
    ("Community Church", "Community Church"),
    ("Chapel", "Chapel"),
    ("Ministry|Ministries", "Ministry"),
    ("Fellowship", "Fellowship"),
]
for pattern, label in patterns:
    import re
    matches = [r for r in extra if re.search(pattern, r[1], re.IGNORECASE)]
    if matches:
        print(f"  {label}: {len(matches)} e.g. {', '.join(m[1][:40] for m in matches[:5])}")

# Check for churches with associations to other states' conventions
print("\n=== Extra churches with non-FL convention associations ===")
assoc = c.execute("""
    SELECT c.id, c.name, b.name, b.state, b.baptist_type 
    FROM churches c
    JOIN baptist_hierarchy b ON b.church_id = c.id
    WHERE c.state = 'FL' 
      AND LOWER(c.denomination) LIKE '%southern baptist%'
      AND b.baptist_type IN ('state_convention', 'local_association')
      AND (b.state IS NOT NULL AND b.state != 'FL')
""").fetchall()
if assoc:
    for row in assoc:
        print(f"  #{row[0]} {row[1][:40]} → {row[2][:40]} ({row[3]}, {row[4]})")
else:
    print("  None found")

# City distribution of extras vs directory-listed
print("\n=== Top 15 cities for extras ===")
extra_cities = Counter()
for row in extra:
    extra_cities[row[3]] += 1
for city, cnt in extra_cities.most_common(15):
    print(f"  {city}: {cnt}")

# Faith tradition of extras
ft_counts = Counter()
for row in extra:
    ft_counts[row[11] or "NULL"] += 1
print("\n=== Faith tradition of extras ===")
for ft, cnt in ft_counts.most_common(10):
    print(f"  {ft}: {cnt}")

# Deep dive into non-Baptist named extras
print("\n=== NON-BAPTIST EXTRAS - Deep Dive ===")
import re
non_bap = [r for r in extra if not re.search(r'\bBaptist\b', r[1], re.IGNORECASE)]
print(f"Total non-Baptist-named extras: {len(non_bap)}")

# Check for obvious misclassifications: other denominations in name
denom_keywords = {
    'Methodist|UMC|United Methodist': 'Methodist',
    'Catholic': 'Catholic',
    'Lutheran|ELCA|LCMS|Missouri Synod': 'Lutheran',
    'Episcopal|Anglican': 'Episcopal/Anglican',
    'Presbyterian|PCUSA|PCA|ARP': 'Presbyterian',
    'Pentecostal|Assemblies of God|AOG': 'Pentecostal',
    'Church of God|COG|COGOP': 'Church of God',
    'Jehovah|Witnesses': 'JW',
    'LDS|Latter.day|Mormon|CHIRST': 'LDS',
    'Adventist|SDA|Seventh.day': 'Adventist',
    'Mosque|Islamic|Muslim|Allah': 'Islamic',
    'Synagogue|Jewish|Congregation|Rabbi|Temple Beth|Temple Israel|B\'nai|Bnai': 'Jewish',
    'Buddhist|Wat |Wat_': 'Buddhist',
    'Hindu|Mandir|Sanatan|Sai|Krishna|Shiva|Devi|Ganesh|Durga|Ram|Laxmi': 'Hindu',
    'Sikh|Gurdwara': 'Sikh',
    'Bahai|Baha': 'Bahai',
    'Shinto|Jinja': 'Shinto',
    'Quaker|Friends': 'Quaker',
    'Salvation Army': 'Salvation Army',
    'Christian Science|Scientist|Reading Room': 'Christian Science',
    'Unitarian|Universalist|UU ': 'Unitarian',
    'Nazarene': 'Nazarene',
    'Wesleyan': 'Wesleyan',
    'Christian and Missionary Alliance|CMA|C&MA|Alliance Church|Alliance Bible': 'CMA',
    'Evangelical Free|EFCA|E Free': 'Evangelical Free',
    'Mennonite|Amish|Brethren': 'Mennonite/Brethren',
    'Orthodox': 'Orthodox',
    'Reformed|CRC|RCA|URC': 'Reformed',
    'Calvary Chapel': 'Calvary Chapel',
    'Church of Christ': 'Church of Christ',
    'Christian Church|Disciples of Christ': 'Christian Church/Disciples',
    'Zionist|Zion': 'Zion',
    'Russian|Tserkov|Blagodaty|Pravoslavnaya': 'Russian/Eastern',
}

for r in non_bap[:50]:
    name = r[1]
    for pattern, label in sorted(denom_keywords.items()):
        if re.search(pattern, name, re.IGNORECASE):
            print(f"  [{label}] #{r[0]} '{name[:55]}' | {r[3] or '-'}, {r[4]} | src={r[8][:25]} | lm={r[10] or '-'}")
            break
    else:
        # No denom keyword match
        pass

# List all without any denom keyword (pure unknown)
unknown = []
for r in non_bap:
    name = r[1]
    matched = False
    for pattern, label in denom_keywords.items():
        if re.search(pattern, name, re.IGNORECASE):
            matched = True
            break
    if not matched:
        unknown.append(r)

print(f"\n=== PURELY UNKNOWN (no denom keyword in name): {len(unknown)} ===")
for r in unknown[:30]:
    print(f"  #{r[0]} '{r[1][:55]}' | {r[3] or '-'}, {r[4]} | src={r[8][:25]} | lm={r[10] or '-'}")

# Check corrupted city names
print("\n=== City corruption in extras ===")
bad_cities = ['', 'Tokyo', 'Hong Kong', 'Osaka', 'Kyoto', 'Putrajaya', 'Kuala Lumpur', 
              'Ambon', 'Jakarta', 'Singapore', 'Sandakan', 'Ibadan', 'Lagos', 'Accra']
for city in bad_cities:
    if city == '':
        cnt = len([r for r in extra if not r[3]])
        print(f"  empty: {cnt}")
    else:
        cnt = len([r for r in extra if r[3] and city in r[3]])
        print(f"  {city}: {cnt}")

# Churches that are clearly NOT SBC
print("\n=== CLEAR MISCLASSIFICATIONS (should not be SBC) ===")
clearly_not = []
for r in extra:
    name = r[1]
    for pattern, label in [('UMC', 'Methodist'), ('United Methodist', 'Methodist'),
                           ('Catholic', 'Catholic'),
                           ('Episcopal', 'Episcopal'),
                           ('LDS|CHIRST', 'LDS'),
                           ('Lutheran.*ELCA|ELCA|LCMS|Missouri Synod', 'Lutheran'),
                           ('Mosque', 'Islamic'),
                           ('Synagogue|Temple Beth|Temple Israel|B\'nai|Bnai|Congregation Beth', 'Jewish'),
                           ('Hindu|Mandir|Sanatan|Sai', 'Hindu'),
                           ('Buddhist|Wat ', 'Buddhist'),
                           ('Seventh.day', 'Adventist'),
                           ('Presbyterian.*PCA|PCA$|ARP', 'Presbyterian'),
                           ('Salvation Army', 'Salvation Army')]:
        if re.search(pattern, name, re.IGNORECASE):
            clearly_not.append((label, r))
            break

for label, r in clearly_not[:30]:
    print(f"  [{label}] #{r[0]} '{r[1][:55]}' | {r[3] or '-'}, {r[4]} | src={r[8][:25]}")

# Also check overture_full sources with weird names
print("\n=== Overture/OSM/holy_sites with weird names ===")
weird_sources = ['overture_full', 'osm_import', 'holy_sites_import']
for r in non_bap:
    if r[8].startswith(tuple(weird_sources)):
        print(f"  #{r[0]} '{r[1][:55]}' | {r[3] or '-'}, {r[4]} | src={r[8][:25]} | lm={r[10] or '-'}")

db.close()

