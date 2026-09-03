"""
Fix 128,949 records with country code but NULL continent.

Uses world_borders.iso_a2 → continent mapping from natural earth DB.
84,530 also have GPS and could be spatially joined, but the country→continent
map handles all of them since they all have country codes.
"""
import sqlite3
from gw_db import connect, Provenance

# Load country→continent mapping from world_borders
ne = sqlite3.connect("data/natural_earth/world_borders.db")
cur = ne.execute("SELECT iso_a2, continent FROM world_borders WHERE iso_a2 IS NOT NULL AND continent IS NOT NULL")
country_continent = {row[0].upper(): row[1] for row in cur.fetchall()}
ne.close()

print(f"Loaded {len(country_continent)} country→continent mappings")

# Add manual overrides for codes not in world_borders
country_continent.update({
    "XK": "Europe",        # Kosovo
    "AQ": "Antarctica",    # Antarctica
    "CX": "Asia",          # Christmas Island
    "GF": "South America", # French Guiana
    "GI": "Europe",        # Gibraltar
    "GP": "North America", # Guadeloupe
    "MQ": "North America", # Martinique
    "RE": "Africa",        # Réunion
    "TK": "Oceania",       # Tokelau
    "YT": "Africa",        # Mayotte
    "SX": "North America", # Sint Maarten
    "MF": "North America", # Saint Martin
    "BL": "North America", # Saint Barthélemy
    "PM": "North America", # Saint Pierre and Miquelon
    "WF": "Oceania",       # Wallis and Futuna
    "PF": "Oceania",       # French Polynesia
    "NC": "Oceania",       # New Caledonia
    "TF": "Antarctica",    # French Southern Territories
    "BV": "Antarctica",    # Bouvet Island
    "HM": "Antarctica",    # Heard Island and McDonald Islands
    "GS": "Antarctica",    # South Georgia and the South Sandwich Islands
    "JE": "Europe",        # Jersey
    "GG": "Europe",        # Guernsey
    "IM": "Europe",        # Isle of Man
})

# Full country name → ISO code mapping (for records that used names instead of codes)
country_name_to_iso = {
    "Croatia": "HR",
    "Denmark": "DK",
    "Estonia": "EE",
    "Finland": "FI",
    "France": "FR",
    "Greece": "GR",
    "Iceland": "IS",
    "Italy": "IT",
    "Latvia": "LV",
    "Monaco": "MC",
    "Montenegro": "ME",
    "Norway": "NO",
    "Portugal": "PT",
    "Spain": "ES",
    "Sweden": "SE",
    "Turkey": "TR",
    "United Kingdom": "GB",
}

# Add name→continent entries by resolving through ISO codes
for full_name, iso in country_name_to_iso.items():
    if iso in country_continent:
        country_continent[full_name] = country_continent[iso]

# Check which country codes in churches are NOT in our mapping
db = connect()
c = db.cursor()
c.execute("SELECT DISTINCT country FROM churches WHERE (continent IS NULL OR continent='') AND country IS NOT NULL AND country != ''")
db_countries = [r[0] for r in c.fetchall()]
unmapped = [c for c in db_countries if c.upper() not in country_continent and c not in country_continent]
print(f"Country codes in gap that are NOT in mapping: {unmapped if unmapped else 'none (all covered)'}")

# Fix the gaps — per-country UPDATEs (fast with index on country)
with Provenance(db, script_name="_fix_missing_continents.py",
                source="grid_fix", action="enriched",
                fields="continent", records_attempted=128949) as prov:

    # Ensure index exists for speed
    c = db.cursor()
    c.execute("CREATE INDEX IF NOT EXISTS idx_churches_country ON churches(country)")

    fixed_total = 0
    items = list(country_continent.items())
    for i, (iso2, continent) in enumerate(items):
        c.execute("""
            UPDATE churches SET continent=?
            WHERE country=? AND (continent IS NULL OR continent='')
        """, (continent, iso2))
        if c.rowcount:
            fixed_total += c.rowcount
        db.commit()
        # Progress bar
        if (i + 1) % 20 == 0 or i == len(items) - 1:
            pct = (i + 1) / len(items) * 100
            bar_len = 40
            filled = int(bar_len * (i + 1) / len(items))
            bar = chr(9608) * filled + chr(9617) * (bar_len - filled)
            print(f"\r  [{bar}] {pct:5.1f}%  ({i+1}/{len(items)} countries, {fixed_total:,} fixed so far)", end="")

    print()
    prov.churches_updated = fixed_total
    prov.records_matched = fixed_total
    print(f"\nFixed {fixed_total:,} records with continent from country→continent mapping")
    db.commit()

# Verify
c = db.cursor()
c.execute("SELECT COUNT(*) FROM churches WHERE (continent IS NULL OR continent='') AND country IS NOT NULL AND country != ''")
remaining = c.fetchone()[0]
print(f"\nRemaining with country but no continent: {remaining:,}")

if remaining > 0:
    c.execute("SELECT country, COUNT(*) FROM churches WHERE (continent IS NULL OR continent='') AND country IS NOT NULL AND country != '' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10")
    print("Still missing:")
    for r in c.fetchall():
        print(f"  {r[0]}: {r[1]}")

# Final continent distribution
c.execute("SELECT continent, COUNT(*) FROM churches WHERE continent IS NOT NULL AND continent != '' GROUP BY continent ORDER BY COUNT(*) DESC")
print("\nFinal continent distribution:")
total = c.fetchone()[0] if False else 0
for r in c.execute("SELECT continent, COUNT(*) FROM churches WHERE continent IS NOT NULL AND continent != '' GROUP BY continent ORDER BY COUNT(*) DESC"):
    print(f"  {r[0]:20s}  {r[1]:>8,}")

c.execute("SELECT COUNT(*) FROM churches WHERE continent IS NULL OR continent = ''")
print(f"\nTotal with no continent (including no-country): {c.fetchone()[0]:,}")

db.close()
