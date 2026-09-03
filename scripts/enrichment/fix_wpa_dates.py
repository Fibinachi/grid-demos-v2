"""Fix WPA date false positives and re-extract with address filter."""
import sqlite3, re

ch = sqlite3.connect('E:/grid/churches.db')
wpa = sqlite3.connect('E:/grid/wpa.db')

# Revert bad pre-1800 dates
bad = ch.execute("SELECT id, name, building_year FROM churches WHERE building_source='wpa_archive_record_book' AND building_year < 1800").fetchall()
print(f'Reverting {len(bad)} pre-1800 false positives:')
for rid, name, yr in bad:
    print(f'  y={yr} [{name[:80]}]')
ch.executemany("UPDATE churches SET building_year=NULL, building_source=NULL WHERE id=? AND building_source='wpa_archive_record_book'", [(r[0],) for r in bad])
# Also revert all wpa_archive entries to start clean
ch.execute("UPDATE churches SET building_year=NULL, building_source=NULL WHERE building_source='wpa_archive_record_book'")
ch.commit()
print(f'All reverted. Starting clean.')

# Reset wpa date columns
wpa.execute("UPDATE wpa_records SET founding_year=NULL, closing_year=NULL, date_source=NULL WHERE 1")
wpa.commit()

# Pattern: must be in church context, not an address
patterns = [
    # "CHURCH NAME, 1848—" or "BAPTIST, 1837—"
    (r'(?:CHURCH|BAPTIST|METHODIST|PRESBYTERIAN|LUTHERAN|CATHOLIC|EPISCOPAL|CONGREGATIONAL|CHRISTIAN|PARISH|CHAPEL)\S*\s*,?\s*(\d{4})\s*[—\-–]', 'open'),
    # "1906-28" after a church keyword
    (r'(?:CHURCH|BAPTIST)\S*\s*,?\s*(\d{4})\s*[—\-–]\s*(\d{2,4})\b', 'closed'),
    # "organized in 1911"
    (r'(?:organized|founded|established|constituted)\s+(?:in\s+)?(\d{4})', 'founded'),
]

dated = []
for row in wpa.execute("SELECT id, church_name FROM wpa_records WHERE church_name LIKE '%1%'").fetchall():
    wid, name = row
    
    # Skip address-like lines
    if re.search(r'\d{2,5}\s+(?:Street|Avenue|Road|Drive|Lane|Blvd|St\.?|Ave\.?|Rd\.?|Place|Court|Way|Highway|Hwy|Route|Rte)\b', name, re.IGNORECASE):
        continue
    # Skip lines that are just "Page X" or "Minutes of XXXX"
    if re.match(r'^(?:Page|Minutes|See|The|This|In|At|By|For|A\s|An\s)\b', name, re.IGNORECASE):
        continue
    
    for pat, ptype in patterns:
        m = re.search(pat, name, re.IGNORECASE)
        if m:
            y = int(m.group(1))
            if 1800 <= y <= 1942:
                ey = None
                if len(m.groups()) > 1 and m.group(2):
                    try:
                        ev = int(m.group(2))
                        ey = 1900 + ev if ev < 100 else ev
                    except: pass
                dated.append((wid, y, ey, ptype))
                break

print(f'Re-extracted: {len(dated):,} (was 2,617)')

for wid, y, ey, pt in dated:
    wpa.execute('UPDATE wpa_records SET founding_year=?, closing_year=?, date_source=? WHERE id=?', (y, ey, f'wpa_{pt}', wid))
wpa.commit()

# Show samples
print('\nSample:')
for r in wpa.execute("SELECT church_name, founding_year FROM wpa_records WHERE founding_year IS NOT NULL ORDER BY founding_year LIMIT 10").fetchall():
    print(f'  {r[1]} [{r[0][:80]}]')

# Push to churches.db
match_map = {r[0]: r[1] for r in wpa.execute('SELECT wpa_record_id, church_id FROM wpa_matches').fetchall()}
records = [(r[0], r[1], r[2], r[3]) for r in wpa.execute(
    'SELECT r.id, r.church_name, r.state, r.founding_year FROM wpa_records r WHERE r.founding_year IS NOT NULL'
).fetchall()]
wpa.close()

ch_index = {}
for row in ch.execute("SELECT id, name, state FROM churches WHERE source='wpa_historical_records_survey'").fetchall():
    ch_index[(row[1], row[2] or '')] = row[0]

updates = []
for (wid, name, state, fy) in records:
    cid = match_map.get(wid) or ch_index.get((name, state or ''))
    if cid and 1800 <= fy <= 1942:
        updates.append((fy, 'wpa_archive_record_book', cid, fy))

print(f'Pushing {len(updates):,} clean updates...')

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

total = ch.execute("SELECT COUNT(*) FROM churches WHERE building_source='wpa_archive_record_book'").fetchone()[0]
print(f'Done: {enriched:,} enriched, {total:,} total')
for r in ch.execute("SELECT (building_year/10)*10 d, COUNT(*) n FROM churches WHERE building_source='wpa_archive_record_book' GROUP BY d ORDER BY d").fetchall():
    print(f'  {r[0]}s: {r[1]:,}')
ch.close()
