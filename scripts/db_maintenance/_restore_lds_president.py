"""
Restore the deleted LDS "Corporation of the President" record (id=359203).

Found in churches_gcs_backup.db with:
  name: Corporation of the President of the Church of Jesus Chrst of Latter-Day Saints
  denomination: LDS / Mormon
  family: lds
  address: 108 Briggs Ave
  city: Richmond Hill, ON
  lat: 43.8498, lon: -79.3997
  source: overture
  org_type: church
"""
import sqlite3
import sys

DB = r'E:\grid\churches.db'
BACKUP = r'E:\grid\churches_gcs_backup.db'

# Step 1: Read the backup record
bdb = sqlite3.connect(BACKUP)
b_cols = [c[1] for c in bdb.execute("PRAGMA table_info(churches)").fetchall()]
b_row = bdb.execute("SELECT * FROM churches WHERE id = 359203").fetchone()
bdata = dict(zip(b_cols, b_row))
bdb.close()

print("=== Backup record ===")
for k, v in bdata.items():
    if v:
        print(f"  {k}: {v}")

# Step 2: Build INSERT for current schema
db = sqlite3.connect(DB)
cur_cols = [c[1] for c in db.execute("PRAGMA table_info(churches)").fetchall()]
print(f"\nCurrent DB has {len(cur_cols)} columns")

# Map backup columns to current columns
mapping = {
    'name': 'name',
    'denomination': 'denomination',
    'family': 'family',
    'address': 'address',
    'city': 'city',
    'state': 'state',
    'zip': 'zip',
    'latitude': 'latitude',
    'longitude': 'longitude',
    'source': 'source',
    'landmark_type': 'org_type',  # backup has org_type, current has landmark_type
}

# Country not in backup - derive from state
STATE_COUNTRY = {'ON': 'CA', 'QC': 'CA', 'BC': 'CA', 'AB': 'CA', 'SK': 'CA', 'MB': 'CA',
                 'NS': 'CA', 'NB': 'CA', 'NL': 'CA', 'PE': 'CA', 'YT': 'CA', 'NT': 'CA',
                 'NU': 'CA'}

for cur_col in cur_cols:
    if cur_col == 'id':
        insert_cols.append('id')
        insert_vals.append(359203)
    elif cur_col == 'country':
        state = bdata.get('state', '') or ''
        insert_cols.append('country')
        insert_vals.append(STATE_COUNTRY.get(state.strip(), 'US'))
    elif cur_col in mapping:
insert_vals = []

for cur_col in cur_cols:
    if cur_col == 'id':
        insert_cols.append('id')
        insert_vals.append(359203)
    elif cur_col in mapping:
        bkey = mapping[cur_col]
        val = bdata.get(bkey)
        # Handle org_type -> landmark_type
        if cur_col == 'landmark_type' and val == 'church':
            insert_cols.append(cur_col)
            insert_vals.append('church')
        elif val:
            insert_cols.append(cur_col)
            insert_vals.append(val)
        else:
            insert_cols.append(cur_col)
            insert_vals.append(None)
    elif cur_col == 'country':
        # Derive country from state
        state = bdata.get('state', '')
        insert_cols.append('country')
        insert_vals.append('CA' if state == 'ON' else 'US')
    elif cur_col == 'faith':
        insert_cols.append('faith')
        insert_vals.append('Christian')
    elif cur_col in ('faith_tradition', 'denomination_affiliation'):
        insert_cols.append(cur_col)
        insert_vals.append('LDS / Mormon')
    elif cur_col == 'source':
        insert_cols.append('source')
        insert_vals.append('overture')
    else:
        insert_cols.append(cur_col)
        insert_vals.append(None)

# Build the SQL
placeholders = ','.join(['?' for _ in insert_vals])
sql = f"INSERT INTO churches ({','.join(insert_cols)}) VALUES ({placeholders})"

if '--dry-run' in sys.argv:
    print(f"\n=== DRY RUN ===")
    print(f"SQL: INSERT INTO churches ({','.join(insert_cols)})")
    print(f"Values: {insert_vals}")
else:
    cur = db.execute(sql, insert_vals)
    db.commit()
    print(f"\n=== RESTORED id=359203 ===")
    print(f"  Rows affected: {cur.rowcount}")

# Verify
cur = db.execute("SELECT id, name, city, state, country, latitude, longitude FROM churches WHERE id = 359203")
r = cur.fetchone()
if r:
    print(f"  VERIFIED: id={r[0]}, name={r[1][:60]}, {r[2]}, {r[3]} {r[4]}, {r[5]:.4f}, {r[6]:.4f}")
else:
    print(f"  WARNING: Record not found after restore!")

db.close()
