"""Test parser on Gastonia sample."""
import sys
sys.path.insert(0, 'e:/grid/scripts/enrichment')
from ia_city_directory_scraper import extract_churches_section, parse_church_entries, infer_denomination

text = open('E:/grid/data/directories/sample_gastonia_1976.txt', encoding='utf-8', errors='ignore').read()
section = extract_churches_section(text)
if section:
    print(f'Section extracted: {len(section):,} chars')
    entries = parse_church_entries(section)
    print(f'Parsed {len(entries)} church entries\n')
    for e in entries[:25]:
        denom = infer_denomination(e['name'])
        print(f'  {e["name"]}')
        print(f'    Addr: {e["address"]}  [{denom}]')
    if len(entries) > 25:
        print(f'\n  ... ({len(entries)} total)')
else:
    print('No section found!')
    
    # Debug: show where CHURCHES appears
    import re
    for m in re.finditer(r'(?i)CHURCH', text):
        start = max(0, m.start()-5)
        end = min(len(text), m.end()+100)
        print(f'  @{m.start()}: ...{text[start:end]}...')
