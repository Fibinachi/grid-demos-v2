"""Match messy OCR diocese names to Wikipedia canonical list."""
import sqlite3, json, re
from pathlib import Path
from collections import defaultdict

DIR_DB = Path("E:/grid/data/catholic_directory.db")
WIKI_FILE = Path("E:/grid/data/directories/wikipedia_dioceses.json")

# Load canonical list
wiki = json.loads(WIKI_FILE.read_text())
canonical = {d.upper().strip(): d for d in wiki['current'] + wiki['former']}

# Also build city-only keys (e.g. "BALTIMORE" from "Archdiocese of Baltimore")
city_keys = {}
for canon_name in canonical:
    # Extract the city portion
    city = canon_name.upper().strip()
    for prefix in ['ARCHDIOCESE OF ', 'DIOCESE OF ', 'EPARCHY OF ', 'ARCHEPARCHY OF ', 'ROMAN CATHOLIC ']:
        if city.startswith(prefix):
            city = city[len(prefix):]
    # Clean: remove state disambiguators
    city = re.sub(r',\s*(TEXAS|LOUISIANA|KANSAS|MICHIGAN|ILLINOIS|INDIANA|SOUTH DAKOTA|OREGON|CALIFORNIA|MISSOURI)\s*$', '', city)
    city = city.strip()
    if city and len(city) > 2:
        if city not in city_keys:
            city_keys[city] = canon_name
        elif 'ARCHDIOCESE' in city_keys[city].upper() and 'ARCHDIOCESE' not in canon_name.upper():
            pass  # Keep archdiocese as primary
        else:
            city_keys[city] = canon_name  # Overwrite with latest

# Load all unique diocese names from our DB
db = sqlite3.connect(str(DIR_DB))
all_dioceses = defaultdict(set)
for yr in [1865, 1868, 2021]:
    for r in db.execute(f"SELECT DISTINCT diocese FROM dir_entries WHERE directory_year={yr} AND diocese IS NOT NULL"):
        raw = r[0].strip()
        if raw and len(raw) > 1:
            all_dioceses[yr].add(raw)

# Normalize function for OCR names
def norm_ocr(d):
    d = d.upper().strip()
    # Fix known OCR variants
    d = d.replace('NEW-YORK', 'NEW YORK')
    d = d.replace('NEW-ORLEANS', 'NEW ORLEANS')
    d = d.replace('PIITSBURGH', 'PITTSBURGH')
    d = d.replace('SAULT STE. MARIE', 'SAULT SAINTE MARIE')
    d = d.replace('TROIS RIVIERES', 'TROIS-RIVIERES')
    d = re.sub(r'[Â€™\']', '', d)  # strip unicode junk
    # Strip trailing single/double uppercase letters (page markers)
    d = re.sub(r'\s+[A-Z]{1,2}$', '', d)
    d = re.sub(r'\s+\d+$', '', d)  
    # Known OCR name fixes
    d = re.sub(r'^(NEW YORKS)$', 'NEW YORK', d)
    d = re.sub(r'^(MARQUETTE AND SAUT).*', 'MARQUETTE', d)
    # Strip trailing punctuation LAST
    d = re.sub(r'[\.\:\;\|\}\~\{\*\-,\s]+$', '', d)
    return re.sub(r'\s+', ' ', d).strip()

# Additional fuzzy aliases for known historical variants
ALIASES = {
    'HALIFAX': 'Halifax–Yarmouth',
    'HALIFAX. MAYS': 'Halifax–Yarmouth',
    'HAMILTON': 'Hamilton, Ontario',
    'KINGSTON': 'Kingston, Ontario',
    'KINGSTON  CA': 'Kingston, Ontario',
    'OTTAWA': 'Ottawa–Cornwall',
    'OTTAWA, U': 'Ottawa–Cornwall',
    'TORONTO': 'Toronto',
    'TORONTO, C': 'Toronto',
    'QUEBEC': 'Quebec',
    'MONTREAL': 'Montreal',
    'SAINT JOHN, N': 'Saint John, New Brunswick',
    'SAINT JOHN': 'Saint John, New Brunswick',
    'ST. JOHN': 'Saint John, New Brunswick',
    'ST. JOHN\'S': "St. John's, Newfoundland",
    "ST. JOHN'S, N": "St. John's, Newfoundland",
    'ST. BONIFACE': 'Saint Boniface',
    'ST. BONIFACE. COL': 'Saint Boniface',
    'VANCOUVER ISLAND': 'Victoria in Canada',
    'RIMOUSKI': 'Rimouski',
    'ST. GERMAIN OF RIMOUSKI': 'Rimouski',
    'ST. HYACINTH': 'Saint-Hyacinthe',
    'ST. HYACINTH.': 'Saint-Hyacinthe',
    'ARICHAT': 'Antigonish',
    'CHATHAM': 'Saint John, New Brunswick',
    'SANDWICH': 'London, Ontario',
    'SAULT STE MARIE': 'Sault Sainte Marie, Ontario',
    'MARQUETTE AND SAUT-': 'Marquette',
    'MONTEREY AND LOS': 'Monterey in California',
    'MONTEREY AND LOS ANGELES': 'Monterey in California',
    'FORT WAYNE': 'Fort Wayne–South Bend',
    'FORT WAYNE. PR': 'Fort Wayne–South Bend',
    'GALVESTON': 'Galveston–Houston',
    'WHEELING': 'Wheeling–Charleston',
    'SANTA FE': 'Santa Fe',
    'NESQUALY': 'Nesqually',
    'ALTON': 'Alton',
    'NATCHITOCHES': 'Natchitoches',
    'NATCHEZ': 'Natchez',
    'OREGON CITY': 'Oregon City',
    'VINCENNES': 'Vincennes, Indiana',
    'ST. PAUL': 'Saint Paul and Minneapolis',
    'ST. PAUL. (ES': 'Saint Paul and Minneapolis',
    'ST. LOUIS': 'Saint Louis',
    'ST. LOUIS. A': 'Saint Louis',
    'ST. LOUIS. EO': 'Saint Louis',
    'NEW-YORKS': 'New York',
    'NEW-YORK. -': 'New York',
    'NEW ORLEANS': 'New Orleans',
    'PIITSBURGH. 231. -': 'Pittsburgh',
    'PITTSBURGH': 'Pittsburgh',
    'CINCINNATI': 'Cincinnati',
    'DETROIT': 'Detroit',
    'MILWAUKEE': 'Milwaukee',
    'PHILADELPHIA': 'Philadelphia',
    'SAN FRANCISCO': 'San Francisco',
    'BOSTON': 'Boston',
    'BOSTON. EAS': 'Boston',
    'CHICAGO': 'Chicago',
    'NEWARK': 'Newark',
    'HARTFORD': 'Hartford',
    'PORTLAND': 'Portland in Oregon',
    'SANTA': 'Santa Fe',
    'RICHMOND': 'Richmond',
    'SAVANNAH': 'Savannah',
    'MOBILE': 'Mobile',
    'NASHVILLE': 'Nashville',
    'LITTLE ROCK': 'Little Rock',
    'LOUISVILLE': 'Louisville',
    'TROIS RIVIERES': 'Trois-Rivières',
    'TROIS-RIVIERES': 'Trois-Rivières',
    'SAINT JOHN, N': 'Saint John, New Brunswick',
    'OTTAWA, U': 'Ottawa–Cornwall',
    'TORONTO, C': 'Toronto',
    'NEW YORKS': 'New York',
    'MARQUETTE AND SAUT': 'Marquette',
    'ST. JOHNÂ€™S, N': "St. John's, Newfoundland",
    'ST. JOHNS': "St. John's, Newfoundland",
    'ST. LOUIS.': 'Saint Louis',
}

# Match each OCR diocese to canonical
mapping = {}
unmatched = []

for yr in [1865, 1868]:
    for raw in sorted(all_dioceses[yr]):
        if raw in mapping:
            continue
        norm = norm_ocr(raw)
        if not norm or len(norm) < 2:
            continue
        
        match = None
        method = ""
        
        # Check aliases first
        if norm in ALIASES:
            match = ALIASES[norm]
            method = "alias"
        # Try exact match on canonical
        elif norm in canonical:
            match = canonical[norm]
            method = "exact"
        elif norm.replace('.', '') in canonical:
            match = canonical[norm.replace('.', '')]
            method = "exact_nodot"
        # Try city-only match
        elif norm in city_keys:
            match = city_keys[norm]
            method = "city"
        # Try fuzzy: remove "DIOCESE OF" / "ARCHDIOCESE OF" prefixes
        else:
            for prefix in ['ARCHDIOCESE OF ', 'DIOCESE OF ', 'ARCHDIOCESE ', 'DIOCESE ']:
                if norm.startswith(prefix):
                    short = norm[len(prefix):].strip()
                    if short in canonical:
                        match = canonical[short]
                        method = "strip_prefix"
                        break
                    if short in city_keys:
                        match = city_keys[short]
                        method = "strip_prefix_city"
                        break
        
        if match:
            mapping[raw] = (match, method)
        else:
            unmatched.append((yr, raw, norm))

# Print results
print("=" * 70)
print(f"DIOCESE MAPPING: {len(mapping)} matched, {len(unmatched)} unmatched")
print("=" * 70)

# By method
methods = defaultdict(list)
for raw, (match, method) in mapping.items():
    methods[method].append((raw, match))
for method, pairs in sorted(methods.items()):
    print(f"\n{method} ({len(pairs)}):")
    for raw, match in pairs[:5]:
        print(f"  {raw:40s} -> {match}")
    if len(pairs) > 5:
        print(f"  ... and {len(pairs)-5} more")

# Unmatched
if unmatched:
    print(f"\nUNMATCHED ({len(unmatched)}):")
    for yr, raw, norm in unmatched[:20]:
        print(f"  [{yr}] {raw:45s} (norm: {norm})")

# Save mapping
mapping_data = {}
for raw, (match, method) in mapping.items():
    mapping_data[raw] = {"canonical": match, "method": method}

with open("E:/grid/data/directories/diocese_mapping.json", "w") as f:
    json.dump({"mapping": mapping_data, "unmatched": [{"year": yr, "raw": raw, "norm": norm} for yr, raw, norm in unmatched]}, f, indent=2)
print(f"\nMapping saved to data/directories/diocese_mapping.json")

# Now apply to DB
print("\n" + "=" * 70)
print("Applying diocese normalization to DB...")
print("=" * 70)

# Create/update normalized diocese column
try:
    db.execute("ALTER TABLE dir_entries ADD COLUMN diocese_canonical TEXT")
except:
    pass

updated = 0
for raw, (canon, _) in mapping.items():
    result = db.execute("UPDATE dir_entries SET diocese_canonical=? WHERE diocese=?", (canon, raw))
    updated += result.rowcount
db.commit()

print(f"Updated {updated:,} entries with canonical diocese names")

# Show before/after
print("\nSample normalizations:")
for r in db.execute("""
    SELECT DISTINCT diocese, diocese_canonical FROM dir_entries
    WHERE diocese_canonical IS NOT NULL AND diocese != diocese_canonical
    LIMIT 15
"""):
    print(f"  {r[0][:40]:40s} -> {r[1]}")

db.close()
print("\nDone.")
