"""
Fix Category A US Jewish false positives → Christian.
Uses Python-side filtering for accurate matching.
"""
import sqlite3, json, re
from datetime import datetime, timezone

DB = r'E:\grid\churches.db'
db = sqlite3.connect(DB)
c = db.cursor()

# Clear Christian denominations
CHRISTIAN_DENOMS = {
    'BAPTIST': 'Baptist', 'SOUTHERN BAPTIST': 'Baptist',
    'METHODIST': 'Methodist', 'UNITED METHODIST': 'Methodist',
    'FREE METHODIST': 'Methodist', 'WESLEYAN': 'Methodist',
    'WESLEYAN CHURCH': 'Methodist',
    'LUTHERAN': 'Lutheran', 'EVANGELICAL FREE': 'Evangelical Free',
    'EVANGELICAL COVENANT': 'Evangelical Covenant',
    'EVANGELICAL CHURCH': 'Evangelical',
    'PRESBYTERIAN': 'Presbyterian', 'REFORMED': 'Reformed',
    'ANGLICAN': 'Anglican', 'EPISCOPAL': 'Anglican',
    'MORAVIAN': 'Anglican',
    'PENTECOSTAL': 'Pentecostal', 'ASSEMBLIES OF GOD': 'Pentecostal',
    'FOURSQUARE': 'Pentecostal',
    'CATHOLIC': 'Catholic',
    'SALVATION ARMY': 'Salvation Army',
    'ADVENTIST': 'Seventh-day Adventist',
    'SEVENTH-DAY ADVENTIST': 'Seventh-day Adventist',
    'MENNONITE': 'Mennonite', 'BRETHREN': 'Brethren',
    'FRIENDS': 'Quaker',
    'NAZARENE': 'Nazarene',
    'CHRISTIAN CHURCH': 'Christian Church (Disciples)',
    'CHURCH OF CHRIST': 'Churches of Christ',
    'CHURCHES OF CHRIST': 'Churches of Christ',
    'DISCIPLES OF CHRIST': 'Christian Church (Disciples)',
    'CHRISTIAN & MISSIONARY ALLIANCE': 'Christian & Missionary Alliance',
    'CHRISTIAN AND MISSIONARY ALLIANCE': 'Christian & Missionary Alliance',
    'CHRISTIAN MISSIONARY ALLIANCE': 'Christian & Missionary Alliance',
    'MISSIONARY CHURCH': 'Christian & Missionary Alliance',
    'CHURCH OF GOD': 'Church of God',
    'CONGREGATIONAL': 'Congregational',
}


def is_christian_name(name):
    """Check if name contains clearly Christian keywords (as standalone words)."""
    if not name:
        return False
    u = name.upper().strip()
    return bool(re.search(r'\b(CHRIST|CHRIST\'S|JESUS|JEHOVAH|CALVARY|MORMON|LDS|LATTER\.DAY)\b', u))


def assign_ft(denom, name):
    """Assign faith_tradition based on denomination or name keywords."""
    denom_u = str(denom).strip().upper() if denom else ''
    name_u = str(name).upper().strip() if name else ''

    # A1: By denomination
    if denom_u in CHRISTIAN_DENOMS:
        return CHRISTIAN_DENOMS[denom_u]

    # A6: Mormon
    if re.search(r'\b(MORMON|LDS|LATTER\.DAY)\b', name_u):
        return "Mormon/LDS"

    # A3: Jehovah
    if re.search(r'\bJEHOVAH\b', name_u):
        return "Jehovah's Witness"

    # A4: Calvary
    if re.search(r'\bCALVARY\b', name_u):
        return "Christian (Calvary)"

    # A2: Default Christian
    return 'Christian'


# Fetch all US Jewish records
all_rows = c.execute("""
    SELECT rowid, id, name, city, state, faith, faith_tradition, denomination,
           landmark_type, source
    FROM churches
    WHERE country = 'US' AND faith = 'Jewish'
""").fetchall()
print(f"Total US Jewish records: {len(all_rows)}")

# Find Category A
fix_rows = []
for r in all_rows:
    rid, cid, name, city, state, faith, ft, denom, lm, src = r
    denom_u = str(denom).strip().upper() if denom else ''

    # A1: Christian denomination
    if denom_u in CHRISTIAN_DENOMS:
        fix_rows.append(r)
        continue

    # A2-A6: Christian keywords in name
    if is_christian_name(name):
        fix_rows.append(r)
        continue

print(f"Category A to fix: {len(fix_rows)}")

# Categorize
a1 = a2 = a3 = a4 = a6 = 0
for r in fix_rows:
    ft_assign = assign_ft(r[7], r[3])
    denom_u = str(r[7]).strip().upper() if r[7] else ''
    name_u = str(r[3]).upper().strip() if r[3] else ''
    if denom_u in CHRISTIAN_DENOMS:
        a1 += 1
    elif re.search(r'\b(MORMON|LDS|LATTER\.DAY)\b', name_u):
        a6 += 1
    elif re.search(r'\bJEHOVAH\b', name_u):
        a3 += 1
    elif re.search(r'\bCALVARY\b', name_u):
        a4 += 1
    else:
        a2 += 1

print(f"  A1 (Christian denom): {a1}")
print(f"  A2 (Christ/Jesus name): {a2}")
print(f"  A3 (Jehovah): {a3}")
print(f"  A4 (Calvary): {a4}")
print(f"  A6 (Mormon): {a6}")

# Show sample
print("\nSample records to fix:")
for r in fix_rows[:15]:
    _, cid, name, city, state, _, old_ft, denom, _, _ = r
    ft_new = assign_ft(denom, name)
    print(f"  rowid={r[0]:>7} {str(name or '')[:55].strip():<55} {str(city or ''):<15} {str(state or ''):<2} ft={old_ft} -> {ft_new}")

# Apply
print(f"\nApplying {len(fix_rows)} fixes...")
updated = 0
batch_source = 'category_a_fix_20260622'
started_at = datetime.now(timezone.utc).isoformat()

for r in fix_rows:
    rid, cid, name, city, state, old_faith, old_ft, denom, lm, src = r
    new_ft = assign_ft(denom, name)
    c.execute("UPDATE churches SET faith = 'Christian', faith_tradition = ? WHERE rowid = ?",
              (new_ft, rid))
    updated += c.rowcount

completed_at = datetime.now(timezone.utc).isoformat()

# Batch provenance log entry
c.execute("""INSERT INTO provenance_log
    (source, script_name, started_at, completed_at, churches_updated,
     fields_populated, parameters, records_attempted, records_matched, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)""",
    ('enrichment', 'fix_category_a.py', started_at, completed_at, updated,
     'faith,faith_tradition',
     json.dumps({'batch': 'category_a_fix', 'criteria': 'christian_denom_or_keyword_name'}),
     len(fix_rows), len(fix_rows),
     f'Reclassified {updated} US Jewish records to Christian (Category A false positives)'))

db.commit()
print(f"  Updated {updated} records")
print(f"  1 batch provenance row logged")

# Verify
remaining_a1 = c.execute("SELECT COUNT(*) FROM churches WHERE country='US' AND faith='Jewish' AND UPPER(COALESCE(denomination,'')) IN ({})".format(
    ','.join('?' for _ in CHRISTIAN_DENOMS)), list(CHRISTIAN_DENOMS.keys())).fetchone()[0]

remaining_a2 = 0
all_remaining = c.execute("SELECT rowid, name, denomination FROM churches WHERE country='US' AND faith='Jewish'").fetchall()
for r in all_remaining:
    if is_christian_name(r[1]):
        remaining_a2 += 1

print(f"\nVerification:")
print(f"  Remaining A1 (Christian denom): {remaining_a1} (expect 0)")
print(f"  Remaining A2-A6 (keyword name): {remaining_a2} (expect 0)")
print(f"  Total US Jewish: {len(all_remaining)}")

db.close()
print("Done.")
