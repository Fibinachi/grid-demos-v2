"""Fix AGENTS.md - add 06-23 diocese validation to both Recent Fixes tables.

Strategy: find each Recent Fixes section by header, locate the last | row
in that section's table, and append the 06-23 row. Handles both copies.
"""

import re

with open('AGENTS.md', 'r', encoding='utf-8') as f:
    text = f.read()

# Row to add
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

# Work backwards through sections to preserve positions
changes_made = 0
for i in range(len(sections) - 1, -1, -1):
    sec_start = sections[i]
    
    # Determine section end (next section or end of file)
    if i + 1 < len(sections):
        # Before the next header
        sec_end = sections[i + 1]
    else:
        sec_end = len(text)
    
    section = text[sec_start:sec_end]
    
    # Check if this section ALREADY has a row with 06-23
    # Be specific: look for '| **06-23**' within the section
    if '| **06-23**' in section:
        print(f'  Section {i} (pos {sec_start}): already has 06-23 row, skipping')
        continue
    
    # Check if this section has NO table rows at all (the truncated copy)
    # Count lines starting with |
    table_rows = [l for l in section.split('\n') if l.strip().startswith('|')]
    if len(table_rows) <= 2:  # Just header + separator
        print(f'  Section {i} (pos {sec_start}): table header only, no data rows')
        continue
    
    # Find the last non-empty line in the section that starts with |
    lines = section.split('\n')
    last_row_idx = -1
    for j in range(len(lines) - 1, -1, -1):
        if lines[j].strip().startswith('|') and '|' in lines[j][1:]:
            last_row_idx = j
            break
    
    if last_row_idx == -1:
        print(f'  Section {i} (pos {sec_start}): no data rows found')
        continue
    
    # Calculate the position in the full text where the last row ends
    # (the newline after it)
    last_row_text = lines[last_row_idx]
    # Find this text in the full text starting from sec_start
    search_pos = sec_start
    # We need to find the position of last_row_text in the full text
    # First find all the lines up to the last row
    for line_idx in range(last_row_idx + 1):
        nl_pos = text.find('\n', search_pos)
        if nl_pos == -1:
            break
        search_pos = nl_pos + 1
    
    # Now search_pos is the start of the line AFTER the last row
    # Insert our new row here
    insertion = row_0623 + '\n'
    text = text[:search_pos] + insertion + text[search_pos:]
    
    print(f'  Section {i} (pos {sec_start}): inserted 06-23 row after line with "{last_row_text[:50]}"')
    changes_made += 1

if changes_made == 0:
    print('\nNo changes made.')
else:
    # Write back
    with open('AGENTS.md', 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'\nDone! {changes_made} change(s) made. File size: {len(text)} bytes')

# Verify
count = text.count('| **06-23**')
print(f'Total 06-23 table rows in file: {count}')
