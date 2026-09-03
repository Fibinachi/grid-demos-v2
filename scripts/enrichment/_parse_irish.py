"""Parse the Irish Church Directory text into structured data."""
import re

with open('data/irish_directory/full_text.txt', encoding='utf-8') as f:
    text = f.read()

# Find all clergy list sections
parts = text.split('LIST OF CLERGY')
print(f'Found {len(parts)-1} clergy list sections')

# Count entries per page
clergy_pages = [i for i, p in enumerate(parts) if i > 0]
total_entries_est = 0

for i, section in enumerate(clergy_pages):
    content = parts[section]
    # Count lines that look like clergy entries (start with name pattern)
    lines = content.split('\n')
    entry_count = 0
    for line in lines:
        line = line.strip()
        # Skip headers, page numbers, ads
        if not line or line.startswith('=') or line.startswith('ADVERTISING') or line.startswith('LIST OF CLERGY'):
            continue
        if line.isdigit() or len(line) < 5:
            continue
        # Check if it has clergy-like pattern (name with comma, degrees, parish/diocese)
        if ',' in line and '(' in line and ')' in line:
            entry_count += 1
    
    total_entries_est += entry_count

print(f'Estimated clergy entries: {total_entries_est}')

# Now parse properly
# Pattern: [optional class]*Name, Degrees, Position Parish (Diocese), Location
clergy_entries = []
current_entry = ""

for section_idx in range(1, len(parts)):
    content = parts[section_idx]
    lines = content.split('\n')
    
    for line in lines:
        line = line.strip()
        # Skip non-content lines
        if not line or line.startswith('=') or line.isdigit():
            continue
        if line.startswith('LIST OF CLERGY') or line.startswith('ADVERTISING') or len(line) < 5:
            continue
        
        # Check if line looks like a clergy entry
        # Starts with optional class marker, then name
        if re.match(r'^[\*\-]*[12]?\*?\s*[A-Z][a-z]+', line) and ',' in line:
            if current_entry:
                clergy_entries.append(current_entry)
            current_entry = line
        elif current_entry and line and not line.startswith(' ' * 10):  # continuation lines
            # Check if it's a new entry starting
            if re.match(r'^[\*\-]*[12]?\*?\s*[A-Z][a-z]+.*,', line):
                clergy_entries.append(current_entry)
                current_entry = line
            else:
                current_entry += ' ' + line

if current_entry:
    clergy_entries.append(current_entry)

print(f'\nParsed {len(clergy_entries)} clergy entries')

# Save to CSV
import csv
with open('data/irish_directory/clergy_parsed.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['raw_text'])
    for entry in clergy_entries:
        w.writerow([entry])

# Show first 30
print('\nFirst 30 entries:')
for e in clergy_entries[:30]:
    print(f'  {e[:120]}')

# Show bishops/additional pages
print('\n\nBishops section (page 15):')
parts2 = text.split('=== PAGE 15 ===')
if len(parts2) > 1:
    p15 = parts2[1]
    # Show between ARCHBISHOPS and the clergy list
    if 'ARCHBISHOPS' in p15:
        arch_section = p15[p15.index('ARCHBISHOPS'):]
        arch_end = arch_section.index('LIST OF CLERGY') if 'LIST OF CLERGY' in arch_section else len(arch_section)
        print(arch_section[:arch_end][:2000])
