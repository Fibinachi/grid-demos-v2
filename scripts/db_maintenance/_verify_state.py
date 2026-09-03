"""Verify AGENTS.md final state."""
with open('AGENTS.md', 'r', encoding='utf-8') as f:
    text = f.read()

count = text.count('| **06-23**')
print(f'06-23 table rows: {count}')

idx1 = text.find('### Recent Fixes (2026-06-21)')
idx2 = text.find('### Recent Fixes (2026-06-21)', idx1 + 10)

print(f'\nFirst Recent Fixes (pos {idx1}):')
scan = idx1 + len('### Recent Fixes (2026-06-21)\n\n')
# Find the table end (blank line after last row)
# The table ends at first blank line (or next section)
table_end_candidates = []
# Look for blank line after a | row
search_in = text[idx1:idx2 if idx2 != -1 else idx1+2000]
lines = search_in.split('\n')
last_table_line = 0
for i, line in enumerate(lines):
    if line.strip().startswith('|'):
        last_table_line = i
# The table end is at the blank line after last_table_line
for r in lines[max(0,last_table_line-2):last_table_line+1]:
    print(f'  {r[:110]}')
# Find the next line after last table row
if last_table_line + 1 < len(lines):
    print(f'  [blank/next: {repr(lines[last_table_line+1][:60])}]')

print(f'\nSecond Recent Fixes (pos {idx2}):')
search_in2 = text[idx2:idx2+2000]
lines2 = search_in2.split('\n')
last_table_line2 = 0
for i, line in enumerate(lines2):
    if line.strip().startswith('|'):
        last_table_line2 = i
for r in lines2[max(0,last_table_line2-2):last_table_line2+1]:
    print(f'  {r[:110]}')
if last_table_line2 + 1 < len(lines2):
    print(f'  [blank/next: {repr(lines2[last_table_line2+1][:60])}]')

print(f'\nCross-source validation count: {text.count("Cross-source validation")}')
