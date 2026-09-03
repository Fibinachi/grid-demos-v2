"""
Extract founding/closing years from WPA archive date patterns.
Patterns: "1888—" (founded 1888, still active), "1906-28" (existed 1906-1928),
          "1869-97, 1899-1936" (multiple date ranges).
These predate the WPA survey year and provide verified temporal anchors.
"""
import sqlite3, re, datetime

WPA_DB = 'E:/grid/wpa.db'
CHURCHES_DB = 'E:/grid/churches.db'

wpa = sqlite3.connect(WPA_DB)
churches = sqlite3.connect(CHURCHES_DB)

# Patterns for date ranges in WPA names
# Priority: "1888—" (open range), "1906-28" (closed range), "(founded 1911)"
patterns = [
    # "1888—" or "1888—,"
    (r'(\d{4})\s*[—\-–]\s*(?:,|$|present|\.)', 'open_range'),
    # "1906-28" or "1869-97"
    (r'(\d{4})\s*[—\-–]\s*(\d{2,4})', 'closed_range'),
    # "organized in 1911" or "founded 1885"
    (r'(?:organized|founded|established|constituted|built|erected)\s+(?:in\s+)?(\d{4})', 'founded'),
    # "(1870)" standalone year in context
    (r'(?:since|from|circa|about|ca\.?)\s+(\d{4})', 'circa'),
]

extracted = []
for row in wpa.execute(
    "SELECT id, church_name, city, county, state, denomination, confidence FROM wpa_records WHERE church_name LIKE '%1%'"
).fetchall():
    wpa_id, name, city, county, state, denom, conf = row
    
    found_year = None
    found_end = None
    found_type = None
    
    for pattern, ptype in patterns:
        matches = list(re.finditer(pattern, name, re.IGNORECASE))
        for m in matches:
            y = int(m.group(1))
            if 1600 < y < 1943:  # Sanity check
                if not found_year or (ptype == 'founded'):  # 'founded' is most reliable
                    found_year = y
                    found_type = ptype
                    if len(m.groups()) > 1 and m.group(2):
                        try:
                            end = int(m.group(2))
                            if end < 100:
                                end = 1900 + end if end < 43 else 1800 + end
                            if 1600 < end < 1943:
                                found_end = end
                        except:
                            pass
    
    if found_year:
        extracted.append((wpa_id, found_year, found_end, found_type))

print(f'WPA records with date range data: {len(extracted):,}')

# Push to wpa_records
try:
    wpa.execute('ALTER TABLE wpa_records ADD COLUMN founding_year INTEGER')
except: pass
try:
    wpa.execute('ALTER TABLE wpa_records ADD COLUMN closing_year INTEGER')
except: pass
try:
    wpa.execute('ALTER TABLE wpa_records ADD COLUMN date_source TEXT')
except: pass

for wpa_id, fy, cy, dtype in extracted:
    wpa.execute(
        'UPDATE wpa_records SET founding_year=?, closing_year=?, date_source=? WHERE id=?',
        (fy, cy, f'wpa_name_pattern_{dtype}', wpa_id)
    )
wpa.commit()

# Now push to churches.db for matched and imported WPA records
# For records with wpa_matches
pushed_match = 0
for wpa_id, fy, cy, dtype in extracted:
    match = wpa.execute('SELECT church_id FROM wpa_matches WHERE wpa_record_id=?', (wpa_id,)).fetchone()
    if match:
        churches.execute(
            '''UPDATE churches SET building_year=?, building_source=?
               WHERE id=? AND (building_year IS NULL OR building_year > ?)''',
            (fy, f'wpa_archive_{dtype}', match[0], fy)
        )
        pushed_match += 1

# For records imported directly (match by name+denomination+state)
pushed_import = 0
for wpa_id, fy, cy, dtype in extracted:
    rec = wpa.execute('SELECT church_name, state, denomination FROM wpa_records WHERE id=?', (wpa_id,)).fetchone()
    if rec:
        name, state, denom = rec
        # Find matching WPA import in churches.db
        result = churches.execute(
            '''UPDATE churches SET building_year=?, building_source=?
               WHERE source='wpa_historical_records_survey'
               AND name=? AND state=?
               AND (building_year IS NULL OR building_year > ?)''',
            (fy, f'wpa_archive_{dtype}', name, state, fy)
        )
        pushed_import += result.rowcount

churches.commit()

total_wpa = wpa.execute('SELECT COUNT(*) FROM wpa_records WHERE founding_year IS NOT NULL').fetchone()[0]
total_ch = churches.execute("SELECT COUNT(*) FROM churches WHERE building_source LIKE 'wpa_archive_%'").fetchone()[0]

print(f'WPA records with founding_year: {total_wpa:,}')
print(f'Churches enriched:            {total_ch:,}')
print(f'  Via matches:  {pushed_match:,}')
print(f'  Via imports:  {pushed_import:,}')

# Show some examples
print('\nExample extractions:')
for row in wpa.execute(
    "SELECT church_name, founding_year, closing_year, date_source FROM wpa_records WHERE founding_year IS NOT NULL LIMIT 20"
).fetchall():
    cy = f'—{row[2]}' if row[2] else '—present'
    print(f'  {row[0][:70]:70s}  {row[1]}{cy:12s}  [{row[3]}]')

# Log provenance
now = datetime.datetime.now().isoformat()
churches.execute(
    "INSERT INTO provenance_log (source, script_name, started_at, completed_at, churches_updated, status, notes) VALUES (?,?,?,?,?,?,?)",
    ('wpa_archive_dates', 'scripts/enrichment/extract_wpa_dates.py', now, now, total_ch, 'complete',
     f'WPA archive date extraction: {total_ch} churches enriched with founding dates from WPA name patterns')
)
churches.commit()

wpa.close()
churches.close()
print(f'\nDone. {total_ch} building years enriched from WPA archive records.')
