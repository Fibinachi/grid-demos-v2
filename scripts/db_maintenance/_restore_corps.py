"""
Restore the deleted LDS President record and other unique geocoded corp records.

Strategy:
1. Restore the LDS Corporation of the President (id=359203) — has coordinates
2. Restore the 6 LDS Corporation of the Presiding Bishop records — have coordinates
3. Restore the handful of geocoded RC/Episcopal corp records (those with lat/lon)
4. For ungeocoded CRA duplicates, use a deduplication approach instead
"""
import sqlite3
import sys

DB = r'E:\grid\churches.db'
BACKUP = r'E:\grid\churches_merge_temp.db'

# Current schema column names
curdb = sqlite3.connect(DB)
CUR_COLS = [c[1] for c in curdb.execute("PRAGMA table_info(churches)").fetchall()]
curdb.close()

# Backup schema and data
bdb = sqlite3.connect(BACKUP)
B_COLS = [c[1] for c in bdb.execute("PRAGMA table_info(churches)").fetchall()]

# Patterns for records to restore
patterns = [
    '%CORPORATION OF THE PRESIDENT%',        # 1 record
    '%CORPORATION OF THE PRESIDING BISHOP%',  # 6 records
]

# Also find geocoded RC Episc Corp records
cur = bdb.execute("SELECT * FROM churches WHERE (name LIKE '%EPISCOPAL CORPORATION%' OR name LIKE '%CATHOLIC EPISCOPAL CORPORATION%') AND latitude IS NOT NULL AND latitude != 0")
geocoded_rc = cur.fetchall()
print(f"Geocoded RC/Episc corp records: {len(geocoded_rc)}")
for row in geocoded_rc:
    rdata = dict(zip(B_COLS, row))
    print(f"  id={rdata.get('id')} | {rdata.get('name','')[:60]} | lat={rdata.get('latitude')} lon={rdata.get('longitude')}")

# Check which are already in current DB
all_to_restore = []

# 1. LDS President (specific id)
cur = bdb.execute("SELECT * FROM churches WHERE id = 359203")
row = cur.fetchone()
if row:
    all_to_restore.append(dict(zip(B_COLS, row)))

# 2. The 6 LDS Presiding Bishop 
cur = bdb.execute("SELECT * FROM churches WHERE name LIKE '%CORPORATION OF THE PRESIDING BISHOP%'")
for row in cur.fetchall():
    all_to_restore.append(dict(zip(B_COLS, row)))

# 3. Geocoded RC corps that aren't already in the DB
cur = bdb.execute("SELECT * FROM churches WHERE (name LIKE '%EPISCOPAL CORPORATION%' OR name LIKE '%CATHOLIC EPISCOPAL CORPORATION%') AND latitude IS NOT NULL AND latitude != 0")
for row in cur.fetchall():
    all_to_restore.append(dict(zip(B_COLS, row)))

bdb.close()

print(f"\n=== Records to restore: {len(all_to_restore)} ===")

# Check which already exist
curdb = sqlite3.connect(DB)
for rdata in all_to_restore[:5]:
    name = rdata.get('name', '')
    rid = rdata.get('id')
    if rid:
        cur = curdb.execute("SELECT COUNT(*) FROM churches WHERE id = ?", (rid,))
        if cur.fetchone()[0] > 0:
            print(f"  ALREADY EXISTS: id={rid} | {str(name)[:60]}")

# Build INSERT for current schema
STATE_MAP = {'ON': 'CA', 'QC': 'CA', 'BC': 'CA', 'AB': 'CA', 'SK': 'CA', 'MB': 'CA',
             'NS': 'CA', 'NB': 'CA', 'NL': 'CA', 'PE': 'CA', 'YT': 'CA', 'NT': 'CA', 'NU': 'CA'}

def build_insert(rdata, cur_cols, b_cols):
    """Map backup columns to current schema."""
    mapping = {
        'name': 'name', 'denomination': 'denomination', 'family': 'family',
        'address': 'address', 'city': 'city', 'state': 'state',
        'zip': 'zip', 'latitude': 'latitude', 'longitude': 'longitude',
        'source': 'source', 'fips': 'fips', 'ein': 'ein',
        'normalized_name': 'normalized_name',
    }
    
    insert_cols = []
    insert_vals = []
    
    # If backup has an id, use it
    bid = rdata.get('id')
    
    for cur_col in cur_cols:
        if cur_col == 'id' and bid:
            insert_cols.append('id')
            insert_vals.append(bid)
        elif cur_col == 'country':
            state = (rdata.get('state', '') or '').strip()
            insert_cols.append('country')
            insert_vals.append(STATE_MAP.get(state, 'CA'))
        elif cur_col in mapping:
            bkey = mapping[cur_col]
            val = rdata.get(bkey)
            if val is not None and str(val).strip() not in ('', '0', '0.0', '00000'):
                insert_cols.append(cur_col)
                insert_vals.append(val)
            else:
                insert_cols.append(cur_col)
                insert_vals.append(None)
        elif cur_col == 'faith':
            insert_cols.append('faith')
            denom = str(rdata.get('denomination', '') or '')
            if 'LDS' in denom or 'Mormon' in denom or 'LATTER' in str(rdata.get('name', '')):
                insert_vals.append('Christian')
            elif 'CATHOLIC' in str(rdata.get('name', '')):
                insert_vals.append('Christian')
            else:
                insert_vals.append('Christian')
        elif cur_col == 'denomination_affiliation':
            denom = rdata.get('denomination', '') or ''
            insert_cols.append(cur_col)
            if denom:
                insert_vals.append(denom)
            else:
                insert_vals.append(None)
        elif cur_col == 'landmark_type':
            insert_cols.append('landmark_type')
            insert_vals.append('diocese_administration')
        elif cur_col == 'cra_bn':
            val = rdata.get('cra_bn')
            if val:
                insert_cols.append('cra_bn')
                insert_vals.append(val)
            else:
                insert_cols.append('cra_bn')
                insert_vals.append(None)
        else:
            insert_cols.append(cur_col)
            insert_vals.append(None)
    
    return insert_cols, insert_vals

dry_run = '--dry-run' in sys.argv
restored = 0
errors = 0

for rdata in all_to_restore:
    name = rdata.get('name', '')
    rid = rdata.get('id')
    
    # Check if already exists
    if rid:
        cur = curdb.execute("SELECT COUNT(*) FROM churches WHERE id = ?", (rid,))
        if cur.fetchone()[0] > 0:
            print(f"  SKIP (exists): id={rid} | {str(name)[:60]}")
            continue
    
    cols, vals = build_insert(rdata, CUR_COLS, B_COLS)
    placeholders = ','.join(['?' for _ in vals])
    sql = f"INSERT INTO churches ({','.join(cols)}) VALUES ({placeholders})"
    
    if dry_run:
        print(f"  DRY-RUN restore: {str(name)[:60]} | lat={rdata.get('latitude','?')}")
    else:
        try:
            curdb.execute(sql, vals)
            restored += 1
            print(f"  RESTORED: {str(name)[:60]}")
        except Exception as e:
            errors += 1
            print(f"  ERROR: {str(name)[:60]}: {e}")

if not dry_run:
    curdb.commit()
    print(f"\n=== Restored: {restored}, Errors: {errors} ===")
else:
    print(f"\n=== Would restore: {len(all_to_restore)} records ===")

# Verify restorations
print("\n=== VERIFICATION ===")
for label, pat in [
    ('LDS President', '%CORPORATION OF THE PRESIDENT%'),
    ('LDS Presiding Bishop', '%CORPORATION OF THE PRESIDING BISHOP%'),
    ('Episcopal Corp of IA', '%EPISCOPAL CORPORATION OF THE DIOCES%'),
    ('RC Corp Mackenzie', '%CORPORATION OF MACKENZIE%'),
    ('RC Corp St Johns', '%CORPORATION OF ST JOHN\'S%'),
]:
    cur = curdb.execute("SELECT id, name, city, state, country, latitude, longitude FROM churches WHERE name LIKE ? LIMIT 1", (pat,))
    r = cur.fetchone()
    if r:
        print(f"  {label}: id={r[0]} | {r[5]:.4f}, {r[6]:.4f} | {r[2]}, {r[3]} {r[4]}")
    else:
        print(f"  {label}: NOT FOUND")

# Count total corp records now
cur = curdb.execute("SELECT COUNT(*) FROM churches WHERE name LIKE '%CORPORATION%'")
print(f"\nTotal 'Corporation' records in DB: {cur.fetchone()[0]}")

curdb.close()
