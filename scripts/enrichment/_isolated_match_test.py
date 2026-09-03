"""Isolated match test - 34 Gloucester entries."""
import sqlite3, time, sys
sys.path.insert(0, 'e:/grid/scripts/enrichment')
from ia_city_directory_scraper import match_against_grid, parse_church_entries, extract_churches_section, download_ocr

# Load Gloucester entries
print('Loading OCR...')
text = download_ocr('gloucesteressexc1960unse')
if not text:
    print('No OCR')
    sys.exit(1)

section = extract_churches_section(text)
if not section:
    print('No section')
    sys.exit(1)

entries = parse_church_entries(section)
print(f'{len(entries)} entries to match')

# Match
print('Opening DB...')
t0 = time.time()
db = sqlite3.connect('e:/grid/churches.db')
db.execute('PRAGMA journal_mode=WAL')

print(f'Matching...')
matched = match_against_grid(db, entries, 'Gloucester', 'MA')
elapsed = time.time() - t0
print(f'Matched {len(matched)} in {elapsed:.1f}s')

matched_count = sum(1 for e in matched if e['matched_church_id'])
print(f'{matched_count}/{len(matched)} matched to GRID')

for e in matched[:10]:
    marker = 'OK' if e['match_confidence'] >= 0.85 else ('~' if e['match_confidence'] >= 0.75 else '?')
    print(f'{marker} {e["name"][:50]:50s} | {e.get("matched_name","") or "NONE":40s} | {e["match_confidence"]:.2f}')

db.close()
