"""Fix AGENTS.md - add 06-23 diocese validation to both Recent Fixes tables.

Approach: find each Recent Fixes section header, scan forward to find the
immediately following table (delimited by | rows), and append the 06-23 row.
"""

import sys

with open('AGENTS.md', 'r', encoding='utf-8') as f:
    text = f.read()

row_0623 = (
    '| **06-23** | **Diocese coverage validation** | '
    '`_validate_dioceses.py` | '
    '**763 distinct diocese values** (25.1% of Vatican 3,041). '
    'US 357 raw\u2192214 normalized (0 dupes), FR 85/98, IT 54/~225, CA 53/70, '
    'PH 48/86, GB 36/~35. Zero Africa/Asia/Oceania coverage. '
    '39,354 churches with diocese (38,323 US). '
    'GoodLands: 69 French polygons. Eastern/Orthodox: 17 entries. |'
)

# Find all Recent Fixes header positions
sections = []
pos = 0
while True:
    idx = text.find('### Recent Fixes (2026-06-21)', pos)
    if idx == -1:
        break
    sections.append(idx)
    pos = idx + 1

print(f'Found {len(sections)} Recent Fixes sections')

if len(sections) == 0:
    print('ERROR: No Recent Fixes sections found!')
    sys.exit(1)

# Work backwards to preserve insertion positions
changes_made = 0
for i in range(len(sections) - 1, -1, -1):
    sec_start = sections[i]
    
    # Skip past the header line and blank line to find the table
    header_end = text.find('\n', sec_start)
    # Skip blank lines
    scan_pos = header_end + 1
    
    # Find where the table actually starts (first | line after header)
    table_start = -1
    while scan_pos < len(text):
        line_end = text.find('\n', scan_pos)
        if line_end == -1:
            line_end = len(text)
        line = text[scan_pos:line_end].strip()
        if line == '':
            scan_pos = line_end + 1
            continue
        if line.startswith('|'):
            table_start = scan_pos
            break
        # If we hit a non-empty, non-table line, stop
        scan_pos = line_end + 1
    
    if table_start == -1:
        print(f'  Section {i}: no table found after header')
        continue
    
    # Find the last line of the table (consecutive | rows)
    scan_pos = table_start
    last_table_row_pos = -1
    last_table_row_end = -1
    
    while scan_pos < len(text):
        line_end = text.find('\n', scan_pos)
        if line_end == -1:
            line_end = len(text)
        line = text[scan_pos:line_end].strip()
        if line == '' or not line.startswith('|'):
            # Table ended at the non-| line or blank line
            break
        last_table_row_pos = scan_pos
        last_table_row_end = line_end
        scan_pos = line_end + 1
    
    if last_table_row_pos == -1:
        print(f'  Section {i}: no data rows in table')
        continue
    
    # Check if we already have a 06-23 row (note: check ALL context containing '06-23'
    # might match other dates; check specifically for '| **06-23**')
    # We'll check the table content only
    table_content = text[table_start:last_table_row_end + 1]
    if '| **06-23**' in table_content:
        print(f'  Section {i}: 06-23 row already in table, skipping')
        continue
    
    # Check if the previous row is a 06-22 row (they should all be 06-21/06-22)
    # The last row shouldn't be 06-23 - if it is, we inserted already
    last_row = text[last_table_row_pos:last_table_row_end].strip()
    if '06-23' in last_row:
        print(f'  Section {i}: last row already 06-23, skipping')
        continue
    
    # Insert after the last row (at the newline after last_table_row_end)
    insertion_pos = last_table_row_end + 1  # after the \n
    
    insertion = row_0623 + '\n'
    text = text[:insertion_pos] + insertion + text[insertion_pos:]
    print(f'  Section {i}: inserted 06-23 row after "{last_row[:60]}"')
    changes_made += 1

if changes_made == 0:
    print('\nNo changes made.')
else:
    with open('AGENTS.md', 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'\nDone! {changes_made} change(s) made. File size: {len(text)} bytes')

# Verify
count = text.count('| **06-23**')
print(f'Total 06-23 table rows in file: {count}')
