"""Normalize GB → UK in churches and holy_sites tables."""
import sqlite3
from datetime import datetime, timezone

NOW = datetime.now(timezone.utc).isoformat()
DB = 'E:/grid/churches.db'

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=30000")
c = conn.cursor()

# ── churches ──
c.execute("SELECT COUNT(*) FROM churches WHERE country='GB'")
gb_count = c.fetchone()[0]
print(f"churches GB→UK: {gb_count:,} rows")

c.execute("UPDATE churches SET country='UK' WHERE country='GB'")
print(f"  churches updated: {c.rowcount:,}")

# ── holy_sites ──
c.execute("SELECT COUNT(*) FROM holy_sites WHERE country='GB'")
hs_gb = c.fetchone()[0]
print(f"holy_sites GB→UK: {hs_gb:,} rows")

c.execute("UPDATE holy_sites SET country='UK' WHERE country='GB'")
print(f"  holy_sites updated: {c.rowcount:,}")

# ── Provenance ──
c.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_inserted,
     fields_populated, records_attempted, records_matched, status, notes)
    VALUES(?,?,?,?,?,?,?,?,'completed',?)
""", (
    "manual",
    "normalize_gb_to_uk.py",
    NOW, datetime.now(timezone.utc).isoformat(),
    0,
    "country",
    gb_count + hs_gb,
    gb_count + hs_gb,
    f"Normalized country code GB→UK: {gb_count:,} churches + {hs_gb:,} holy_sites"
))

conn.commit()

# ── Verify ──
c.execute("SELECT country, COUNT(*) FROM churches WHERE country IN ('UK','GB') GROUP BY country")
print("\nVerification - churches:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

c.execute("SELECT country, COUNT(*) FROM holy_sites WHERE country IN ('UK','GB') GROUP BY country")
print("Verification - holy_sites:")
for r in c.fetchall():
    print(f"  {r[0]}: {r[1]:,}")

conn.close()
print("\nDone.")
