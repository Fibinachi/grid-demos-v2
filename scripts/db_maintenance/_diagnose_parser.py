"""Diagnose what the Catholic Directory parser is missing."""
import re

ct = open('data/catholic_directory_1907/full_text.txt', encoding='utf-8').read()
sections = list(re.finditer(r'CLERGY,\s*CHURCHES,\s*MISSIONS\s+AND\s+SCHOOLS\.', ct))

# Get Baltimore section (section 0)
s = sections[0]
end = sections[1].start()
body = ct[s.end():end]

# Trim at RECAPITULATION or RELIGIOUS COMMUNITIES
recap = body.find('RECAPITULATION')
rel = body.find('RELIGIOUS COMMUNITIES')
trim_points = [p for p in [recap, rel] if p > 0]
trim_at = min(trim_points) if trim_points else len(body)
usable = body[:trim_at]
lines = usable.split('\n')

print(f'Baltimore body: {len(body):,} chars, {len(lines)} lines')
print(f'Trimmed at pos {trim_at}')
print(f'Usable section: {len(usable):,} chars\n')

# Count all non-empty, non-page-marker lines
content_lines = [l for l in lines if l.strip() and not l.strip().startswith('===')]
print(f'Content lines (non-empty, non-page): {len(content_lines)}')

# Count churches - lines starting with ST./SAINT/THE/HOLY/SACRED etc.
church_pattern = r'^(ST\.|SAINT|THE\s|OUR\s|HOLY\s|SACRED\s|IMMACULATE\s|BLESSED\s|CORPUS\s|FOURTEEN\s|SS\.)\s*'
church_lines = [l for l in content_lines if re.match(church_pattern, l.strip(), re.IGNORECASE)]
print(f'\nPotential church lines: {len(church_lines)}')
print('First 20:')
for cl in church_lines[:20]:
    print(f'  [{cl.strip()[:120]}]')

# Count school-associated lines
school_kw = r'\b(School|Sisters|Brothers|Nuns|Felician|Benedictine|Franciscan|Ursuline)\b'
school_lines = [l for l in content_lines if re.search(school_kw, l.strip(), re.IGNORECASE)]
print(f'\nLines with school keywords: {len(school_lines)}')
print('First 20:')
for sl in school_lines[:20]:
    print(f'  [{sl.strip()[:120]}]')

# Orphan/Asylum lines
orphan_lines = [l for l in content_lines if re.search(r'\b(Orphan|Asylum)\b', l.strip(), re.IGNORECASE)]
print(f'\nOrphan/Asylum lines: {len(orphan_lines)}')

# Lines starting with numbers (school counts like "6 Sisters")
num_lines = [l for l in content_lines if re.match(r'^\d+\s+(Sisters|Brothers|Lay|School|Felician|Benedictine|Franciscan)', l.strip(), re.IGNORECASE)]
print(f'\nLines starting with number+order: {len(num_lines)}')
for nl in num_lines[:10]:
    print(f'  [{nl.strip()[:120]}]')

# City headers
city_lines = [l for l in content_lines if re.match(r'^(CITY\s+OF|OUTSIDE\s+OF)', l.strip(), re.IGNORECASE)]
print(f'\nCity headers: {len(city_lines)}')

# Lines we're correctly catching vs missing
print('\n=== What the current parser should produce ===')
print(f'Churches: ~{len(church_lines)}')
print(f'School mentions: ~{len(school_lines)} (many nested under churches)')
print(f'Orphan/Asylum: ~{len(orphan_lines)}')
