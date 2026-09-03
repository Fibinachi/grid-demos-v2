"""Post-import verification script."""
import sqlite3, sys
from datetime import datetime

conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()

sys.stdout.write(f"\n  {'='*56}\n")
sys.stdout.write(f"  POST-IMPORT VERIFICATION\n")
sys.stdout.write(f"  {datetime.now().isoformat()}\n")
sys.stdout.write(f"  {'='*56}\n\n")

# Total
c.execute('SELECT COUNT(*) FROM churches')
total = c.fetchone()[0]
sys.stdout.write(f"  Total churches: {total:,}\n\n")

# New import breakdown
sys.stdout.write(f"  CSV Import breakdown:\n")
c.execute("SELECT source, COUNT(*) FROM churches WHERE source LIKE 'csv_import' || '%' GROUP BY source ORDER BY COUNT(*) DESC")
rows = c.fetchall()
total_imported = sum(r[1] for r in rows)
sys.stdout.write(f"    Total from csv_import: {total_imported:,}\n")
for r in rows:
    label = r[0].replace('csv_import_','').replace('_',' ').title()
    sys.stdout.write(f"    {label:40s} {r[1]:>8,}\n")

# Provenance
c.execute("SELECT COUNT(*) FROM provenance_log WHERE source='csv_import' AND script_name='_import_all_csvs.py'")
prov = c.fetchone()[0]
sys.stdout.write(f"\n  Provenance entries: {prov}\n")

# Faith breakdown
c.execute("SELECT faith, COUNT(*) FROM churches GROUP BY faith ORDER BY COUNT(*) DESC LIMIT 15")
sys.stdout.write(f"\n  Faith breakdown:\n")
for r in c.fetchall():
    sys.stdout.write(f"    {str(r[0] or 'NULL'):20s} {r[1]:>10,}\n")

# Country breakdown top 15
c.execute("SELECT country, COUNT(*) FROM churches WHERE country IS NOT NULL AND country != '' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10")
sys.stdout.write(f"\n  Top countries:\n")
for r in c.fetchall():
    sys.stdout.write(f"    {r[0]:6s} {r[1]:>10,}\n")

conn.close()
sys.stdout.write(f"\n  {'='*56}\n  DONE\n  {'='*56}\n")
