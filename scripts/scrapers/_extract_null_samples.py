"""Extract key sections from the NULL faith report."""
with open('data/null_faith_samples.txt', 'rb') as f:
    raw = f.read()
text = raw[2:].decode('utf-16-le')
lines = text.split('\n')

targets = [
    'overture_full (306',
    'churchunion_scraper (59',
    'cra_2018 (28',
    'irs (23,0',
    'csv_import (9,',
    'catholic_diocese_scrape (8,',
    'ag_directory (5,',
    'cog_scraper (5,',
    'holy_sites_import (3,',
    'sbc_directory (1,',
]

for target in targets:
    sep = "=" * 80
    print(f"\n{sep}")
    in_section = False
    count = 0
    for line in lines:
        if target in line:
            in_section = True
            count = 0
        if in_section:
            print(line)
            count += 1
            if count > 55:
                print('  ... (truncated)')
                break
