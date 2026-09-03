"""Fix remaining Muslim classification stragglers and misclassifications."""
import sys
sys.path.insert(0, ".")
from gw_db import connect, log_change, log_changes_batch

db = connect(timeout=60)
c = db.cursor()

SCRIPT_NAME = "fix_muslim_stragglers"

# 1. Fix remaining non-Islamic traditions under Islam
print("=== Remaining non-Islamic traditions ===")
c.execute("""
    SELECT tradition, COUNT(*) FROM churches 
    WHERE faith='Islam' AND tradition IS NOT NULL AND tradition != ''
      AND tradition NOT IN ('Sunni','Salafi','Hanafi','Twelver','Maliki','Shafii',
                           'Sufi','Muslim','Zaydi','Ibadi','Ahmadiyya','Ismaili',
                           'Bohra','Nation of Islam','Deobandi','Quranist','Hanbali',
                           'Sunni (Generic)','Nation of Islam','Shia')
    GROUP BY tradition ORDER BY COUNT(*) DESC
""")
rows = c.fetchall()
changes = []
for r in rows:
    trad, cnt = r[0], r[1]
    print(f"  {trad:25s}: {cnt}")
    c.execute("SELECT id, name FROM churches WHERE faith='Islam' AND tradition=? LIMIT 5", (trad,))
    for church in c.fetchall():
        print(f"    ID={church[0]:>8d} | {str(church[1] or '')[:55]}")
    # Fix them
    c.execute("UPDATE churches SET faith='Other', tradition=NULL, taxonomy_id=NULL WHERE faith='Islam' AND tradition=?", (trad,))
    changes.append((0, 'faith', 'Islam', 'Other', SCRIPT_NAME))

# 2. Log the remaining unclassified
print(f"\n=== Still unclassified (no tradition) ===")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND (tradition IS NULL OR tradition='')")
still = c.fetchone()[0]
print(f"  {still:,}")

# Sample the unclassified
if still > 0:
    c.execute("SELECT id, name, city, country FROM churches WHERE faith='Islam' AND (tradition IS NULL OR tradition='') LIMIT 20")
    for r in c.fetchall():
        print(f"  ID={r[0]:>8d} | {str(r[1] or '')[:50]:50s} | {str(r[2] or ''):20s} {r[3] or ''}")

# 3. Final Muslim classification summary
print(f"\n=== FINAL MUSLIM CLASSIFICATION SUMMARY ===")
c.execute("""
    SELECT tradition, COUNT(*) as cnt
    FROM churches WHERE faith='Islam' AND tradition IS NOT NULL AND tradition != ''
    GROUP BY tradition ORDER BY cnt DESC
""")
total = 0
for r in c.fetchall():
    print(f"  {str(r[0] or 'unclassified'):25s}: {r[1]:>8,}")
    total += r[1]

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam' AND (tradition IS NULL OR tradition='')")
unclass = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Islam'")
grand = c.fetchone()[0]

print(f"  {'TOTAL CLASSIFIED':25s}: {total:>8,}")
print(f"  {'STILL UNCLASSIFIED':25s}: {unclass:>8,}")
print(f"  {'GRAND TOTAL ISLAM':25s}: {grand:>8,}")

db.commit()
db.close()
