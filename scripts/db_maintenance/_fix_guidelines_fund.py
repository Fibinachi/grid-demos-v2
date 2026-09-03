"""
Fix GUIDELINES FUND CORP (rowid=216317) data issues.

This script fixes:
1. city: "ISRAEL" → "Bet Shemesh" (actual city from IRS address "BET SHEMESH 9964166")
2. country: "US" → "IL" (mailing address is in Israel per IRS BMF raw data)
3. Append note in church_enrichment about Foundation 15 supporting org status

All changes logged to provenance_log + enrichment_change_log.
"""

import sqlite3
import json
import sys
import os

DB_PATH = 'E:/grid/churches.db'
CHURCH_ID = 216317
SCRIPT_NAME = '_fix_guidelines_fund.py'
SOURCE = 'manual'  # manual data quality fix

# --- Gather old values ---
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
old = db.execute(
    'SELECT rowid, city, state, zip, country, address, name, faith, faith_tradition FROM churches WHERE rowid = ?',
    (CHURCH_ID,)
).fetchone()

old_note = db.execute(
    'SELECT notes FROM church_enrichment WHERE church_id = ?',
    (CHURCH_ID,)
).fetchone()

db.close()

if not old:
    print(f"ERROR: No church found with rowid={CHURCH_ID}")
    sys.exit(1)

print(f"=== FIXING {old['name']} (rowid={CHURCH_ID}) ===")
print(f"  city:    '{old['city']}'  →  'Bet Shemesh'")
print(f"  country: '{old['country']}'  →  'IL'")
print(f"  faith:   '{old['faith']}'  (unchanged - correct as Jewish)")
print()

# --- Build new note ---
new_note_parts = []
if old_note and old_note['notes']:
    new_note_parts.append(old_note['notes'])
new_note_parts.append(
    "[manual fix 2026-06-24] Foundation 15 supporting org (pass-through charitable fund), "
    "not a synagogue. IRS NTEE_CD=X30, CLASSIFICATION=7000, EIN=810733616. "
    "Address from IRS BMF: BET SHEMESH 9964166, ISRAEL."
)
new_note = ' | '.join(new_note_parts)

print(f"  notes: appending Foundation 15 info")

# --- Execute updates ---
db = sqlite3.connect(DB_PATH)
db.execute("PRAGMA journal_mode=WAL")
db.execute("BEGIN TRANSACTION")

try:
    # 1. Update churches table
    db.execute(
        'UPDATE churches SET city = ?, country = ? WHERE rowid = ?',
        ('Bet Shemesh', 'IL', CHURCH_ID)
    )
    print(f"  ✅ churches.city updated: '{old['city']}' → 'Bet Shemesh'")
    print(f"  ✅ churches.country updated: '{old['country']}' → 'IL'")

    # 2. Update enrichment notes
    db.execute(
        'UPDATE church_enrichment SET notes = ? WHERE church_id = ?',
        (new_note, CHURCH_ID)
    )
    print(f"  ✅ church_enrichment.notes updated")

    # 3. Log to enrichment_change_log (city)
    db.execute(
        '''INSERT INTO enrichment_change_log
           (church_id, field_name, old_value, new_value, change_source)
           VALUES (?, ?, ?, ?, ?)''',
        (CHURCH_ID, 'city', old['city'], 'Bet Shemesh', SCRIPT_NAME)
    )

    # 4. Log to enrichment_change_log (country)
    db.execute(
        '''INSERT INTO enrichment_change_log
           (church_id, field_name, old_value, new_value, change_source)
           VALUES (?, ?, ?, ?, ?)''',
        (CHURCH_ID, 'country', old['country'], 'IL', SCRIPT_NAME)
    )

    # 5. Log to enrichment_change_log (notes)
    old_note_text = old_note['notes'] if old_note and old_note['notes'] else ''
    db.execute(
        '''INSERT INTO enrichment_change_log
           (church_id, field_name, old_value, new_value, change_source)
           VALUES (?, ?, ?, ?, ?)''',
        (CHURCH_ID, 'notes', old_note_text, new_note, SCRIPT_NAME)
    )

    # 6. Log to provenance_log
    db.execute(
        '''INSERT INTO provenance_log
           (source, script_name, started_at, completed_at, churches_updated,
            fields_populated, parameters, status, notes)
           VALUES (?, ?, datetime('now'), datetime('now'), 1, ?, ?, 'completed', ?)''',
        (
            SOURCE,
            SCRIPT_NAME,
            json.dumps(['city', 'country', 'notes']),
            json.dumps({
                'church_id': CHURCH_ID,
                'name': old['name'],
                'ein': '810733616',
                'reason': 'City was set to "ISRAEL" (country name) instead of actual city "Bet Shemesh"; '
                          'country was "US" but IRS mailing address is in Israel'
            }),
            'Fixed city (ISRAEL→Bet Shemesh), country (US→IL), added Foundation 15 supporting org note'
        )
    )

    db.commit()
    print(f"\n  ✅ All changes committed. Provenance logged.")

except Exception as e:
    db.rollback()
    print(f"\n  ❌ ERROR: {e}")
    print("  Rolled back.")
    sys.exit(1)
finally:
    db.close()

# --- Verify ---
print("\n=== VERIFICATION ===")
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
row = db.execute('SELECT rowid, name, city, state, zip, country, faith FROM churches WHERE rowid = ?', (CHURCH_ID,)).fetchone()
print(f"  city:    {row['city']}")
print(f"  country: {row['country']}")
print(f"  faith:   {row['faith']}")

note = db.execute('SELECT notes FROM church_enrichment WHERE church_id = ?', (CHURCH_ID,)).fetchone()
if note:
    print(f"  notes:   {note['notes'][:100]}...")

# Check provenance
prov = db.execute(
    'SELECT id, source, script_name, status FROM provenance_log WHERE script_name = ? ORDER BY id DESC LIMIT 1',
    (SCRIPT_NAME,)
).fetchone()
if prov:
    print(f"  provenance: #{prov['id']} ({prov['source']}/{prov['script_name']}) — {prov['status']}")

db.close()
print("\nDone.")
