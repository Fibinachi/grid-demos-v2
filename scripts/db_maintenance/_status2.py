import sqlite3, json, os, subprocess

conn = sqlite3.connect('churches.db')

# 1. DB totals
total = conn.execute('SELECT COUNT(*) FROM churches').fetchone()[0]
cu = conn.execute("SELECT COUNT(*) FROM churches WHERE source='churchunion_scraper'").fetchone()[0]
has_coords = conn.execute('SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL').fetchone()[0]

print('=== DATABASE ===')
print(f'Total churches:       {total:,}')
print(f'ChurchUnion new:      {cu:,}')
print(f'Has coordinates:      {has_coords:,} ({100*has_coords/total:.1f}%)')

# 2. church_sources schema
print('\n=== church_sources schema ===')
cols = [r[1] for r in conn.execute("PRAGMA table_info(church_sources)")]
for r in conn.execute("PRAGMA table_info(church_sources)"):
    print(f'  {r[1]:20s} {r[2]}')
if 'source_name' in cols:
    cu_dup = conn.execute("SELECT COUNT(*) FROM church_sources WHERE source_name='churchunion_scraper'").fetchone()[0]
    print(f'  ChurchUnion duplicates logged: {cu_dup:,}')
else:
    print('  *** MISSING source_name column - needs ALTER TABLE ***')

# 3. Import checkpoint
ck_file = 'data/churchunion_import_ck.json'
if os.path.exists(ck_file):
    ck = json.load(open(ck_file))
    csv_rows = 165064
    pct = ck['processed'] / csv_rows * 100 if csv_rows else 0
    remaining = csv_rows - ck['processed']
    eta_min = remaining * 1.1 / 60
    print(f'\n=== IMPORT CHECKPOINT ===')
    print(f'Processed:  {ck["processed"]:,} / {csv_rows:,} ({pct:.1f}%)')
    print(f'Inserted:   {ck["inserted"]:,}')
    print(f'Duplicates: {ck["dup"]:,}')
    print(f'Failed:     {ck["fail"]:,}')
    print(f'Remaining:  {remaining:,}')
    if remaining > 0 and ck['processed'] > 0:
        print(f'ETA:        {eta_min:.0f} min ({eta_min/60:.1f} hrs)')
        print(f'New rate:   {ck["inserted"]/ck["processed"]*100:.1f}%')
        print(f'Dup rate:   {ck["dup"]/ck["processed"]*100:.1f}%')
else:
    print('\nNO IMPORT CHECKPOINT')

# 4. CSV
csv_file = 'data/churchunion_scraped.csv'
if os.path.exists(csv_file):
    lines = sum(1 for _ in open(csv_file, encoding='utf-8'))
    size = os.path.getsize(csv_file)/1024/1024
    print(f'\n=== CSV ===')
    print(f'{csv_file}: {lines:,} lines, {size:.1f} MB')

# 5. Python processes
result = subprocess.run(['powershell', '-Command', 'Get-Process python -ErrorAction SilentlyContinue | Select Id, StartTime'], capture_output=True, text=True)
print(f'\n=== PYTHON PROCESSES ===')
out = result.stdout.strip()
print(out if out else 'None (import not running)')

conn.close()
