"""Clean up artifact/garbage records from csv_import source.

Definite artifacts: page navigation titles (not real churches).
All have zero useful data — no coords, no address, no city.
"""
import sqlite3
from datetime import datetime

DB_PATH = 'E:/grid/churches.db'
SCRIPT_NAME = '_cleanup_csv_import_artifacts.py'

# Exact artifact names to delete
ARTIFACT_NAMES = [
    'CHURCH PLANTING',
    'CHURCH PLANTING IN IOWA',
    'CHURCH PLANTING / REVITALIZATION',
    'FIND A CHURCH',
    'CHURCHES',
    'OUR CHURCHES',
    'CHURCH BUILDING',
    'CHURCH COMPENSATION',
    'CHURCH BUILDING PLANNING',
    'CHURCH JOB BOARD',
    'PASTOR-LESS CHURCHES, PULPIT SUPPLY, INTERIM',
    # Coming-soon placeholders (no coords, no address, no city)
    'IGLESIA BAUTISTA DE SPRINGFIELD COMING SOON',
    'LIBERTY LIVE CHURCH FAIRVIEW HEIGHTS COMING SOON',
    'LIGHT COMMUNITY CHURCH COMING SOON',
    'MOSAIC ESPANOL WINCHESTER COMING SOON',
    # Article/blog titles (not churches)
    'INSPIRING GENEROSITY: 3 WAYS TO INCREASE GENEROSITY IN SMALL CHURCHES\u2026AND MORE!',
    'YOUTH MINISTRY ENCOURAGEMENT &#038; COACHING FOR IOWA CHURCHES',
    'HOW IOWA CAMPERS ON MISSION HELPS CHURCHES',
    'TEN NEW CHURCHES JOIN THE BCI FAMILY IN 2025',
    '1,600 BAPTIST CHURCHES',
    'SENDING CHURCHES',
    'STARTING CHURCHES',
    'STRONG CHURCHES',
    'HEALTHY CHURCHES',
    'CROSSING A NETWORK OF COMMUNITY CHURCHES',
]

CHILD_TABLES = [
    "attendance_history", "broadcast_ministries",
    "church_census_us", "church_arda", "church_broadband", "church_broadcast",
    "church_classification_meta", "church_contacts", "church_enrichment",
    "church_fcc", "church_food_desert", "church_gnis",
    "church_metro_area", "church_nrhp", "church_operations",
    "church_postal_admin", "church_sources", "church_staff",
    "church_territories", "church_vacancies",
    "org_links", "org_officers",
]

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 1. Collect all IDs to delete
all_ids = set()
for name in ARTIFACT_NAMES:
    c.execute("SELECT id FROM churches WHERE source='csv_import' AND name=?", (name,))
    ids = [r[0] for r in c.fetchall()]
    all_ids.update(ids)
    print(f'  {name:55s}: {len(ids)} records')

id_list = sorted(all_ids)
print(f'\nTotal records to delete: {len(id_list)}')

if not id_list:
    print('Nothing to do.')
    conn.close()
    exit(0)

# 2. Delete from child tables
print('\nDeleting from child tables...')
for tbl in CHILD_TABLES:
    try:
        placeholders = ','.join(['?'] * len(id_list))
        c.execute(f"DELETE FROM {tbl} WHERE church_id IN ({placeholders})", id_list)
        if c.rowcount > 0:
            print(f'  Deleted {c.rowcount} from {tbl}')
    except Exception as e:
        pass  # table might not exist

# 3. Log to enrichment_change_log
now = datetime.now().isoformat()
placeholders = ','.join(['?'] * len(id_list))
c.execute(
    f"INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source, enrichment_version, changed_at) "
    f"SELECT id, 'deleted_by_cleanup', NULL, 'csv_import_artifact', 'cleanup_csv_import_artifacts', NULL, ? FROM churches WHERE id IN ({placeholders})",
    [now] + id_list
)
print(f'  Logged {c.rowcount} to enrichment_change_log')

# 4. Delete from churches
c.execute(f"DELETE FROM churches WHERE id IN ({placeholders})", id_list)
print(f'  Deleted {c.rowcount} from churches')

# 5. Log provenance
c.execute(
    "INSERT INTO provenance_log (source, script_name, started_at, completed_at, churches_inserted, churches_updated, "
    "fields_populated, records_attempted, records_matched, status, notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
    ('csv_import', SCRIPT_NAME, now, datetime.now().isoformat(), 0, 0,
     '', len(id_list), 0, 'completed', f'Deleted {len(id_list)} artifact records from csv_import source')
)
print('  Provenance logged')

conn.commit()
conn.close()
print(f'\nDone. Deleted {len(id_list)} artifact records.')
