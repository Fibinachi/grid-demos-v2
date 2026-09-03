"""
Create church_contact_values table and migrate existing data from church_contacts.

The old church_contacts table has a single phone/email/website per church with
confidence scores. The new table allows multiple values per contact type, each
with its own confidence, source, and verification metadata.
"""
import sqlite3
from datetime import datetime, timezone

CHUNK = 500
db = sqlite3.connect("churches.db")
cur = db.cursor()

# ── 1. Create the new table ──
cur.execute("""
    CREATE TABLE IF NOT EXISTS church_contact_values (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        church_id INTEGER NOT NULL REFERENCES churches(id) ON DELETE CASCADE,
        contact_type TEXT NOT NULL CHECK(contact_type IN (
            'phone', 'email', 'website',
            'facebook', 'instagram', 'youtube',
            'online_giving', 'livestream'
        )),
        value TEXT NOT NULL,
        confidence REAL,
        source TEXT,
        last_verified TEXT,
        is_primary INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")

# Check if it already had data
cur.execute("SELECT COUNT(*) FROM church_contact_values")
existing_new = cur.fetchone()[0]
print(f"Existing rows in church_contact_values: {existing_new}")

if existing_new == 0:
    # ── 2. Migrate phones ──
    print("\nMigrating phones...")
    cur.execute("""
        INSERT INTO church_contact_values (church_id, contact_type, value, confidence, source, last_verified, is_primary)
        SELECT church_id, 'phone', phone, phone_confidence, 
               CASE WHEN phone_source = '' THEN NULL ELSE phone_source END,
               phone_last_verified, 1
        FROM church_contacts
        WHERE phone IS NOT NULL AND phone != ''
    """)
    db.commit()
    print(f"  {cur.rowcount} phones migrated")

    # ── 3. Migrate emails ──
    print("Migrating emails...")
    cur.execute("""
        INSERT INTO church_contact_values (church_id, contact_type, value, confidence, source, last_verified, is_primary)
        SELECT church_id, 'email', email, email_confidence,
               CASE WHEN email_source = '' THEN NULL ELSE email_source END,
               email_last_verified, 1
        FROM church_contacts
        WHERE email IS NOT NULL AND email != ''
    """)
    db.commit()
    print(f"  {cur.rowcount} emails migrated")

    # ── 4. Migrate websites ──
    print("Migrating websites...")
    cur.execute("""
        INSERT INTO church_contact_values (church_id, contact_type, value, confidence, source, last_verified, is_primary)
        SELECT church_id, 'website', website, website_confidence,
               CASE WHEN website_source = '' THEN NULL ELSE website_source END,
               website_last_verified, 1
        FROM church_contacts
        WHERE website IS NOT NULL AND website != ''
    """)
    db.commit()
    print(f"  {cur.rowcount} websites migrated")

    # ── 5. Migrate social media (facebook, instagram, youtube) ──
    for sm_type in ['facebook_url', 'instagram_url', 'youtube_url']:
        contact_type = sm_type.replace('_url', '')
        print(f"Migrating {contact_type}...")
        cur.execute(f"""
            INSERT INTO church_contact_values (church_id, contact_type, value, is_primary)
            SELECT church_id, '{contact_type}', {sm_type}, 1
            FROM church_contacts
            WHERE {sm_type} IS NOT NULL AND {sm_type} != ''
        """)
        db.commit()
        print(f"  {cur.rowcount} {contact_type} migrated")

    # ── 6. Migrate online_giving and livestream ──
    for col, ct in [('online_giving_link', 'online_giving'), ('livestream_link', 'livestream')]:
        print(f"Migrating {ct}...")
        cur.execute(f"""
            INSERT INTO church_contact_values (church_id, contact_type, value, is_primary)
            SELECT church_id, '{ct}', {col}, 1
            FROM church_contacts
            WHERE {col} IS NOT NULL AND {col} != ''
        """)
        db.commit()
        print(f"  {cur.rowcount} {ct} migrated")

else:
    print("Table already has data — skipping migration")

# ── 7. Verify ──
print(f"\n{'='*50}")
cur.execute("SELECT COUNT(*) FROM church_contact_values")
print(f"Total in church_contact_values: {cur.fetchone()[0]}")

cur.execute("""
    SELECT contact_type, COUNT(*) as cnt
    FROM church_contact_values
    GROUP BY contact_type
    ORDER BY cnt DESC
""")
print("\nBy type:")
for r in cur.fetchall():
    print(f"  {r[0]:20s} {r[1]:>8}")

# Sample a few rows
print("\nSample rows:")
cur.execute("""
    SELECT v.id, v.church_id, c.name, c.city, v.contact_type, v.value, v.confidence, v.source
    FROM church_contact_values v
    JOIN churches c ON c.id = v.church_id
    WHERE v.contact_type = 'phone'
    LIMIT 5
""")
for r in cur.fetchall():
    print(f"  #{r[0]}: church #{r[1]} {r[2]}, {r[3]} | {r[4]}={r[5]} conf={r[6]} src={r[7]}")

# ── 8. Log provenance ──
now = datetime.now(timezone.utc).isoformat()
cur.execute("""
    SELECT COUNT(*) FROM church_contact_values
""")
total_migrated = cur.fetchone()[0]

cur.execute("""
    INSERT INTO provenance_log
    (source, script_name, started_at, completed_at, churches_updated,
     records_attempted, fields_populated, status, notes, parameters)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    "contact_values_migration", "create_church_contact_values",
    now, datetime.now(timezone.utc).isoformat(),
    0, total_migrated,
    "phone,email,website,facebook,instagram,youtube,online_giving,livestream",
    "completed",
    f"Created church_contact_values table and migrated {total_migrated} contact values "
    f"from church_contacts. Old church_contacts table left intact for backward compatibility.",
    '{"table": "church_contact_values", "migrated_from": "church_contacts", "old_rows": 627565}'
))

db.commit()
db.close()

print(f"\n{'='*50}")
print(f"Migration complete. Provenance logged.")
print(f"{'='*50}")
