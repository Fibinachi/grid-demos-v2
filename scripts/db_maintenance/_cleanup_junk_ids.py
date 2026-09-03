"""
Clean up two junk church records (IDs 13, 18) with no source.
These appear to be CSV import artifacts — name is a zip code, denomination is "2022",
and all other fields are NULL or garbage.
"""
import sqlite3
import datetime
import time

DB = 'churches.db'
JUNK_IDS = [13, 18]

# Retry on database lock
for attempt in range(5):
    try:
        conn = sqlite3.connect(DB, timeout=60)
        c = conn.cursor()
        
        # Verify the junk rows still exist
        c.execute("SELECT COUNT(*) FROM churches WHERE id IN (?, ?)", JUNK_IDS)
        if c.fetchone()[0] == 0:
            print("Junk rows already deleted. Nothing to do.")
            conn.close()
            break

        # Show what we're about to delete
        print("=== Churches to delete ===")
        for cid in JUNK_IDS:
            c.execute("SELECT id, name, denomination, source FROM churches WHERE id = ?", (cid,))
            row = c.fetchone()
            print(f"  ID={row[0]} name={row[1]!r} denom={row[2]!r} source={row[3]!r}")

        # Delete dependent rows first
        c.execute("DELETE FROM church_broadcast WHERE church_id IN (?, ?)", JUNK_IDS)
        print(f"  Deleted {c.rowcount} rows from church_broadcast")
        c.execute("DELETE FROM church_contacts WHERE church_id IN (?, ?)", JUNK_IDS)
        print(f"  Deleted {c.rowcount} rows from church_contacts")
        c.execute("DELETE FROM church_operations WHERE church_id IN (?, ?)", JUNK_IDS)
        print(f"  Deleted {c.rowcount} rows from church_operations")
        c.execute("DELETE FROM church_enrichment WHERE church_id IN (?, ?)", JUNK_IDS)
        print(f"  Deleted {c.rowcount} rows from church_enrichment")

        # Delete the churches
        c.execute("DELETE FROM churches WHERE id IN (?, ?)", JUNK_IDS)
        print(f"  Deleted {c.rowcount} churches")

        # Log in provenance_log
        ts = datetime.datetime.now().isoformat()
        c.execute("""
            INSERT INTO provenance_log (source, script_name, started_at, completed_at, 
                churches_updated, churches_inserted, fields_populated, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ('manual', '_cleanup_junk_ids.py', ts, ts, 0, 0, 
              'deleted junk rows', 'completed', 
              f'Deleted junk church IDs 13,18 (zip codes as names, year as denomination) and dependent rows'))

        conn.commit()
        print("\n=== Cleanup complete, committed ===")
        conn.close()
        break
    except sqlite3.OperationalError as e:
        print(f"Attempt {attempt+1}: {e}")
        try:
            conn.close()
        except:
            pass
        time.sleep(2)
