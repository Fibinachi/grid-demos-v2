"""Push WPA founding years to churches.db."""
import sqlite3, datetime

wpa = sqlite3.connect('E:/grid/wpa.db')
dated = [(r[0], r[1], r[2], r[3]) for r in wpa.execute(
    "SELECT r.id, r.church_name, r.state, r.founding_year FROM wpa_records r WHERE r.founding_year IS NOT NULL"
).fetchall()]
match_map = {r[0]: r[1] for r in wpa.execute('SELECT wpa_record_id, church_id FROM wpa_matches').fetchall()}
wpa.close()
print(f'Dated: {len(dated):,}  Matches: {len(match_map):,}')

ch = sqlite3.connect('file:E:/grid/churches.db?mode=ro', uri=True)
ch_index = {}
for row in ch.execute("SELECT id, name, state FROM churches WHERE source='wpa_historical_records_survey'").fetchall():
    ch_index[(row[1], row[2] or '')] = row[0]
ch.close()
print(f'Indexed: {len(ch_index):,}')

updates = []
for (wpa_id, name, state, fy) in dated:
    cid = match_map.get(wpa_id) or ch_index.get((name, state or ''))
    if cid:
        updates.append((fy, 'wpa_archive_record_book', cid, fy))

print(f'Updates: {len(updates):,}')

import time; time.sleep(1)
ch = sqlite3.connect('E:/grid/churches.db')
ch.execute('PRAGMA journal_mode=WAL')

enriched = 0; batch = []
for u in updates:
    batch.append(u)
    if len(batch) >= 200:
        ch.executemany('UPDATE churches SET building_year=?, building_source=? WHERE id=? AND (building_year IS NULL OR building_year > ?)', batch)
        enriched += len(batch); batch = []; ch.commit()
if batch:
    ch.executemany('UPDATE churches SET building_year=?, building_source=? WHERE id=? AND (building_year IS NULL OR building_year > ?)', batch)
    enriched += len(batch)
ch.commit()

now = datetime.datetime.now().isoformat()
ch.execute("INSERT INTO provenance_log (source, script_name, churches_updated, status, notes) VALUES (?,?,?,?,?)",
    ('wpa_archive_dates', 'push_wpa_dates.py', enriched, 'complete', f'{enriched} WPA record book start years'))
ch.commit()

print(f'Enriched: {enriched:,}')

for r in ch.execute("SELECT (building_year/10)*10 d, COUNT(*) n FROM churches WHERE building_source='wpa_archive_record_book' GROUP BY d ORDER BY d").fetchall():
    print(f'  {r[0]}s: {r[1]:,}')

for r in ch.execute("SELECT name, building_year FROM churches WHERE building_source='wpa_archive_record_book' ORDER BY building_year LIMIT 5").fetchall():
    print(f'  {r[1]} [{r[0][:70]}]')

ch.close()
print('Done.')
