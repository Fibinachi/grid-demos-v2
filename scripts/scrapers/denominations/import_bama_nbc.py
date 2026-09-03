"""Import AL NBC district-level church data into DB"""
import sqlite3, json

DB = r'E:\grid\churches.db'
infile = r'E:\grid\data\nbc_churches.jsonl'

# Load records
records = []
with open(infile) as f:
    for line in f:
        records.append(json.loads(line))

print(f'Loaded {len(records)} records')

# Group by district
districts = {}
for r in records:
    d = r.get('district', 'Unknown')
    if d not in districts:
        districts[d] = []
    districts[d].append(r)

for d, recs in sorted(districts.items()):
    print(f'  {d}: {len(recs)} churches')

DENOM = "National Baptist Convention of America"
FAMILY = "Missionary Baptist"
SOURCE = "ASMBC Election Voting Eligibility List (alabamastatebaptist.org)"

conn = sqlite3.connect(DB)
c = conn.cursor()

imported = 0
skipped = 0
dups = 0
for r in records:
    name = r['name']
    pastor = r.get('pastor', '')
    address = r.get('address', '')
    city = r.get('city', '')
    state = r.get('state', 'AL')
    zip_code = r.get('zip', '')
    district = r.get('district', '')
    
    # Check for exact name+city duplicate
    c.execute("SELECT COUNT(*) FROM churches WHERE name=? AND city=? AND state=?", (name, city, state))
    if c.fetchone()[0] > 0:
        # Update existing record with district info if available
        c.execute("UPDATE churches SET district=?, pastor_name=?, denomination=?, family=? WHERE name=? AND city=? AND state=? AND (district IS NULL OR district='')",
                  (district, pastor, DENOM, FAMILY, name, city, state))
        dups += 1
        continue
    
    try:
        c.execute("""
            INSERT INTO churches 
            (name, address, city, state, zip, pastor_name, district,
             denomination, family, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, address, city, state, zip_code, pastor, district,
              DENOM, FAMILY, SOURCE))
        imported += 1
    except Exception as e:
        skipped += 1

conn.commit()
conn.close()

print(f'\nResults:')
print(f'  Imported: {imported}')
print(f'  Duplicates (updated district/pastor): {dups}')
print(f'  Skipped: {skipped}')
print(f'  Total processed: {len(records)}')
