"""Fix misclassified Hindu entries in Nigeria."""
import sqlite3
db = sqlite3.connect('e:/grid/churches.db')
db.row_factory = sqlite3.Row

print('=== Nigerian "Hindu" entries by taxonomy ===')
for r in db.execute("""
    SELECT taxonomy_id, COUNT(*) n, GROUP_CONCAT(DISTINCT landmark_type) as types,
           GROUP_CONCAT(DISTINCT source) as sources
    FROM churches WHERE country='NG' AND faith='Hindu'
    GROUP BY taxonomy_id ORDER BY n DESC
"""):
    print(f'  tax_id={r["taxonomy_id"]}: {r["n"]:,} entries | types={r["types"]} | sources={r["sources"]}')

print()
print('=== Sample entries ===')
for r in db.execute("""
    SELECT id, name, landmark_type, taxonomy_id, source, state, city
    FROM churches WHERE country='NG' AND faith='Hindu'
    LIMIT 20
"""):
    print(f'  [{r["id"]}] {r["name"]:<50} type={r["landmark_type"]:<20} tax={r["taxonomy_id"]} src={r["source"]}')

print()
print('=== Nigerian "Other" entries by taxonomy ===')
for r in db.execute("""
    SELECT taxonomy_id, COUNT(*) n, GROUP_CONCAT(DISTINCT landmark_type) as types
    FROM churches WHERE country='NG' AND faith='Other'
    GROUP BY taxonomy_id ORDER BY n DESC LIMIT 10
"""):
    print(f'  tax_id={r["taxonomy_id"]}: {r["n"]:,} entries | types={r["types"]}')

# The Hindu entries in Nigeria are almost certainly misclassified.
# Nigeria has ~2,200 people who practice Hinduism (mostly Indian expats), not 2,200 temples.
# These are likely:
# 1. "Other" faith buildings (African Traditional Religion, etc.) labeled as Hindu
# 2. Christian churches with Indian-origin names mistaken for Hindu
# 3. Source-level misclassification from Overture/OSM/Wikidata

# Let's fix: reclassify all Nigerian faith='Hindu' to faith='Other'
# with tradition='African Traditional' or 'Unclassified (Nigeria)'

print()
print('=== FIX PLAN ===')
print('Move all Nigerian faith=Hindu to faith=Other, tradition=African Traditional')

# Check if there's an African Traditional taxonomy node
for r in db.execute("SELECT id, name FROM taxonomy WHERE name LIKE '%African%' OR name LIKE '%Traditional%' LIMIT 10"):
    print(f'  Taxonomy: {r["id"]} = {r["name"]}')

# Count
n = db.execute("SELECT COUNT(*) FROM churches WHERE country='NG' AND faith='Hindu'").fetchone()[0]
print(f'\n{n:,} entries to fix.')

# Apply fix: These are all Christian churches mislabeled as Hindu in Wikidata
# Names include: Baptist Church, DIGC (Deeper Life), First Baptist, etc.
# Fix: faith=Christian, landmark_type=church, fix taxonomy_id=3→2

# First fix those with Hindu taxonomy (id=3) to generic Christian (id=2)
db.execute("""
    UPDATE churches SET faith = 'Christian', tradition = 'Protestant',
        taxonomy_id = 2, landmark_type = 'church'
    WHERE country = 'NG' AND faith = 'Hindu' AND taxonomy_id = 3
""")
print(f'Fixed Hindu taxonomy (id=3): {db.total_changes} rows')

# The rest already have Christian taxonomies (209=Baptist, 14=Catholic, etc.)
# Just fix faith and landmark_type
db.execute("""
    UPDATE churches SET faith = 'Christian', landmark_type = 'church'
    WHERE country = 'NG' AND faith = 'Hindu'
""")
print(f'Fixed remaining faith/type: {db.total_changes} rows')

# Verify
remaining = db.execute("SELECT COUNT(*) FROM churches WHERE country='NG' AND faith='Hindu'").fetchone()[0]
print(f'Remaining Hindu in NG: {remaining}')

# Updated counts
for r in db.execute("SELECT faith, COUNT(*) n FROM churches WHERE country='NG' GROUP BY faith ORDER BY n DESC"):
    print(f'  {r[0]}: {r[1]:,}')

db.close()
print('\nDone.')
