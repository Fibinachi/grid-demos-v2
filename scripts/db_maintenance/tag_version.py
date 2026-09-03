"""Create version tracking and tag v1.0-rc (release candidate)."""
import sqlite3, json
from datetime import datetime

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Create version table
c.execute("""
    CREATE TABLE IF NOT EXISTS db_version (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version TEXT NOT NULL,
        version_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'release',
        description TEXT,
        total_records INTEGER,
        jewish_records INTEGER,
        faith_breakdown TEXT,
        changes_summary TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")

# Get current stats
c.execute("SELECT COUNT(*) FROM churches")
total = c.fetchone()[0]

c.execute("SELECT faith, COUNT(*) FROM churches GROUP BY faith ORDER BY COUNT(*) DESC")
faiths = {r[0] or 'NULL': r[1] for r in c.fetchall()}

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
jewish = c.fetchone()[0]

c.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL")
with_gps = c.fetchone()[0]

c.execute("SELECT COUNT(DISTINCT country) FROM churches WHERE country IS NOT NULL AND country != ''")
countries = c.fetchone()[0]

# Check if already tagged
c.execute("SELECT COUNT(*) FROM db_version WHERE version='1.0-rc'")
if c.fetchone()[0] == 0:
    c.execute("""
        INSERT INTO db_version (version, version_date, status, description, total_records, jewish_records, faith_breakdown, changes_summary)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        '1.0-rc',
        datetime.now().isoformat(),
        'release-candidate',
        'GRID Database v1.0 Release Candidate — Comprehensive global religious infrastructure database after major Jewish classification cleanup.',
        total,
        jewish,
        json.dumps(faiths, indent=2),
        'Major cleanup: ~2,500 records reclassified out of Judaism across all regions. '
        'DeepSeek-assisted classification of 1,856 flagged entries. '
        'Name transliteration applied to 1.14M records. '
        'Facility type taxonomy applied across US entries. '
        'US state-by-state review in progress (~50% complete).'
    ))
    conn.commit()
    print(f"Tagged v1.0-rc")
else:
    print("v1.0-rc already exists, updating...")
    c.execute("""
        UPDATE db_version SET 
            total_records=?, jewish_records=?, 
            faith_breakdown=?, version_date=?
        WHERE version='1.0-rc'
    """, (total, jewish, json.dumps(faiths), datetime.now().isoformat()))
    conn.commit()
    print("Updated v1.0-rc")

# Show current tag
c.execute("SELECT version, version_date, status, total_records, jewish_records FROM db_version ORDER BY id DESC LIMIT 1")
r = c.fetchone()
print(f"\nVersion: {r[0]}")
print(f"Date: {r[1]}")
print(f"Status: {r[2]}")
print(f"Total records: {r[3]:,}")
print(f"Jewish records: {r[4]:,}")
print(f"Faiths: {json.dumps(faiths, indent=2)}")

conn.close()
