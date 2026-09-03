"""Comprehensive enrichment summary for GRID marketing."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

print("=" * 60)
print("GRID ENRICHMENT SUMMARY")
print("=" * 60)

# Core
us = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US'").fetchone()['n']
global_ = db.execute("SELECT COUNT(*) as n FROM churches").fetchone()['n']
countries = db.execute("SELECT COUNT(DISTINCT country) as n FROM churches").fetchone()['n']
gps = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US' AND latitude IS NOT NULL").fetchone()['n']
fips = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US' AND county_fips_5 IS NOT NULL").fetchone()['n']
zip_ = db.execute("SELECT COUNT(*) as n FROM churches WHERE country='US' AND zip5 IS NOT NULL AND zip5 != ''").fetchone()['n']

print(f"\nCore: {global_:,} sites, {countries} countries, {us:,} US")
print(f"  GPS: {gps:,} ({100*gps//us}%)  |  County FIPS: {fips:,} ({100*fips//us}%)  |  ZIP5: {zip_:,}")

# FTLM taxonomy
faiths = []
for r in db.execute("SELECT faith, COUNT(*) as n FROM churches GROUP BY faith ORDER BY n DESC"):
    faiths.append((r['faith'], r['n']))
trads = db.execute("SELECT COUNT(DISTINCT tradition) as n FROM churches WHERE tradition IS NOT NULL").fetchone()['n']
null_trad = db.execute("SELECT COUNT(*) as n FROM churches WHERE tradition IS NULL").fetchone()['n']
print(f"\nFTLM Taxonomy: {len(faiths)} faiths, {trads} traditions")
print(f"  NULL tradition: {null_trad:,}")
for f, n in faiths:
    print(f"  {f}: {n:,}")

# FEMA
fema_tracts = db.execute("SELECT COUNT(*) as n FROM fema_nri_tract").fetchone()['n']
fema_joined = db.execute("""
    SELECT COUNT(DISTINCT c.id) as n FROM churches c
    JOIN church_districts d ON d.church_id=c.id AND d.layer_code='TRACT'
    JOIN fema_nri_tract f ON f.TRACTFIPS=d.geo_id
    WHERE c.country='US'
""").fetchone()['n']
print(f"\nFEMA NRI: {fema_tracts:,} tracts + {fema_joined:,} churches joined (18 hazard types)")

# FBI Crime
srs = db.execute("SELECT COUNT(*) as n, MIN(year) as y0, MAX(year) as y1 FROM fbi_srs_state").fetchone()
nibrs = db.execute("SELECT COUNT(*) as n FROM fbi_nibrs_agency_2024").fetchone()['n']
print(f"FBI Crime: {srs['n']:,} state-level rows ({srs['y0']}-{srs['y1']}) + {nibrs:,} agency-level (2024)")

# CDC
cdc = db.execute("SELECT COUNT(*) as n FROM cdc_places_tract").fetchone()['n']
print(f"CDC PLACES: {cdc:,} tract records (health outcomes)")

# Contact data
contacts = {}
for r in db.execute("""
    SELECT cv.contact_type, COUNT(DISTINCT cv.church_id) as n
    FROM church_contact_values cv JOIN churches c ON c.id=cv.church_id
    WHERE c.country='US' GROUP BY cv.contact_type
"""):
    contacts[r['contact_type']] = r['n']
print(f"\nContact data (US):")
for t, n in contacts.items():
    print(f"  {t}: {n:,}")

# Geographic layers
layers = {}
for r in db.execute("SELECT layer_code, COUNT(DISTINCT church_id) as n FROM church_districts GROUP BY layer_code"):
    layers[r['layer_code']] = r['n']
print(f"\nGeographic layers (via church_districts):")
for l, n in sorted(layers.items()):
    print(f"  {l}: {n:,} churches")

# Hierarchies
for table in ['lds_hierarchy','lutheran_hierarchy','jw_hierarchy','catholic_hierarchy','baptist_hierarchy','sa_hierarchy','chabad_hierarchy','moravian_hierarchy','bahai_hierarchy']:
    try:
        n = db.execute(f"SELECT COUNT(*) as n FROM {table}").fetchone()['n']
        print(f"  {table}: {n:,}")
    except:
        pass

# Enrichment change log
enrich = db.execute("SELECT COUNT(*) as n FROM enrichment_change_log").fetchone()['n']
prov = db.execute("SELECT COUNT(*) as n FROM provenance_log").fetchone()['n']
print(f"\nEnrichment tracking: {enrich:,} changes logged, {prov:,} provenance entries")

# RUCC
try:
    rucc = db.execute("SELECT COUNT(*) as n FROM rucc_codes").fetchone()['n']
    print(f"RUCC: {rucc:,} county codes")
except: pass

# PPP
try:
    ppp = db.execute("SELECT COUNT(*) as n FROM sba_ppp_loans").fetchone()['n']
    print(f"SBA PPP: {ppp:,} loans")
except: pass

db.close()
