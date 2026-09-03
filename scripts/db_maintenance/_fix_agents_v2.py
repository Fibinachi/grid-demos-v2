"""Fix AGENTS.md - add 06-23 diocese validation to both Recent Fixes tables."""

import sys

with open('AGENTS.md', 'r', encoding='utf-8') as f:
    text = f.read()

# Find all occurrences of Recent Fixes table headers and the rows
# Strategy: find each Recent Fixes section, identify where the table ends,
# and append the 06-23 row.

recent_fixes_count = text.count('### Recent Fixes (2026-06-21)')
print(f'Found {recent_fixes_count} Recent Fixes sections')

if recent_fixes_count != 2:
    print(f'WARNING: Expected 2 Recent Fixes sections, got {recent_fixes_count}')
    # Continue anyway with what we have

# Build the 06-23 row to add
row_0623 = (
    '| **06-23** | **Diocese coverage validation** | '
    '`_validate_dioceses.py` | '
    '**763 distinct diocese values** (25.1% of Vatican 3,041). '
    'US 357 raw\\u2192214 normalized (0 dupes), FR 85/98, IT 54/~225, CA 53/70, PH 48/86, GB 36/~35. '
    'Zero Africa/Asia/Oceania coverage. 39,354 churches with diocese (38,323 US). '
    'GoodLands: 69 French polygons. Eastern/Orthodox: 17 entries. |'
)

# For each Recent Fixes section, find the end of its table and append
# We work backwards to preserve positions
sections = []
pos = 0
while True:
    idx = text.find('### Recent Fixes (2026-06-21)', pos)
    if idx == -1:
        break
    sections.append(idx)
    pos = idx + 1

print(f'Found {len(sections)} sections at positions: {sections}')

# For each section, find where the table ends (next blank line after last | row)
for i, sec_start in enumerate(sections):
    # Find all table rows in this section by finding the next section header or end
    if i + 1 < len(sections):
        sec_end = sections[i + 1]
    else:
        sec_end = len(text)
    
    # Extract the section content
    section = text[sec_start:sec_end]
    
    # Find the last table row (line starting with |)
    lines = section.split('\n')
    last_table_row_idx = -1
    for j in range(len(lines) - 1, -1, -1):
        if lines[j].strip().startswith('|') and '|' in lines[j][1:]:
            last_table_row_idx = j
            break
    
    if last_table_row_idx == -1:
        print(f'  Section {i}: no table rows found')
        continue
    
    # The table ends after the last row - add our new row before the blank line
    # Find the insertion point: right after the last | row
    insert_pos = sec_start
    for j in range(last_table_row_idx + 1):
        insert_pos = text.find('\n', insert_pos) + 1
    
    # Check if 06-23 row already exists
    if '06-23' in text[sec_start:sec_end]:
        print(f'  Section {i}: 06-23 row already exists')
        continue
    
    # Insert the new row
    text = text[:insert_pos] + row_0623 + '\n' + text[insert_pos:]
    print(f'  Section {i}: inserted 06-23 row at position {insert_pos}')
    
    # Adjust positions for subsequent sections
    for j in range(i + 1, len(sections)):
        sections[j] += len(row_0623) + 1

# Also add cross-source validation note to Global Diocese Coverage
# Find both occurrences
gdc_count = text.count('### Global Diocese Coverage\n| Country')
print(f'Found {gdc_count} Global Diocese Coverage sections')

if gdc_count >= 1:
    validation_note = (
        '\n**Cross-source validation** (2026-06-23): `_validate_dioceses.py` confirmed '
        '**763 distinct diocese values** (25.1% of Vatican 3,041). '
        'See full section above for per-country breakdown.\n'
    )
    
    # Find all occurrences and insert note
    gdc_positions = []
    pos = 0
    while True:
        idx = text.find('### Global Diocese Coverage\n| Country', pos)
        if idx == -1:
            break
        # Find the end of this table (lines starting with |)
        table_start = idx
        table_end = text.find('\n', table_start)  # skip header
        table_end = text.find('\n', table_end + 1)  # skip |---|---|---|---|
        table_end = text.find('\n', table_end + 1)  # skip France row
        table_end = text.find('\n', table_end + 1)  # skip US row
        
        # Rest of world row - find where this table ends
        rest_pos = text.find('| Rest of world', table_end)
        if rest_pos != -1:
            eol = text.find('\n', rest_pos)
            # Check what follows - if blank line, insert before it
            if eol + 1 < len(text) and text[eol + 1:eol + 2] == '\n':
                insert_at = eol + 1
            else:
                insert_at = eol + 1
        else:
            insert_at = table_end  # fallback
        
        # Check if already has validation note
        if 'Cross-source validation' in text[idx:idx+500]:
            print(f'  GDC section at {idx}: validation note already exists')
        else:
            text = text[:insert_at] + validation_note + text[insert_at:]
            print(f'  GDC section at {idx}: inserted validation note')
        
        pos = idx + 1

# Write the result
with open('AGENTS.md', 'w', encoding='utf-8') as f:
    f.write(text)

print(f'\nDone! File size: {len(text)} bytes')
print(f'06-23 occurrences: {text.count("06-23")}')
print(f'Cross-source validation occurrences: {text.count("Cross-source validation")}')
