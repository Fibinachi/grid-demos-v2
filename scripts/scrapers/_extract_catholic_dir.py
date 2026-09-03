"""Extract text from Catholic Directory PDF and match against DB."""
import fitz, os, re

pdf_path = 'The_Official_Catholic_Directory_and_Cler.pdf'
out_dir = 'data/catholic_directory_1907'
os.makedirs(out_dir, exist_ok=True)

doc = fitz.open(pdf_path)
print(f'Total pages: {len(doc)}')

# Extract all text
with open(f'{out_dir}/full_text.txt', 'w', encoding='utf-8') as f:
    for i in range(len(doc)):
        text = doc[i].get_text()
        if text.strip():
            f.write(f'\n{"="*60}\n=== PAGE {i+1} ===\n{"="*60}\n')
            f.write(text)
        if (i+1) % 50 == 0:
            print(f'  Page {i+1}/{len(doc)}')

total_chars = sum(len(doc[i].get_text()) for i in range(len(doc)))
print(f'\nTotal chars: {total_chars:,}')
doc.close()

# Quick scan: show first occurrence of each US state abbreviation + diocese
print('\n=== Scanning for dioceses ===')
with open(f'{out_dir}/full_text.txt', encoding='utf-8') as f:
    text = f.read()

# Find ARCHDIOCESE/DIOCESE mentions
dioceses = set()
for m in re.finditer(r'(ARCHDIOCESE|DIOCESE)\s+OF\s+([A-Z][A-Z\s\-\']+?)\.', text, re.IGNORECASE):
    dioceses.add(m.group(0).strip())
print(f'Found {len(dioceses)} diocese mentions')
for d in sorted(dioceses)[:50]:
    print(f'  {d}')

# Find state abbreviations followed by diocese content
us_states = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY','DC']
print(f'\n=== US Dioceses found (pages 20-60 sample) ===')
for state in us_states[:10]:
    pattern = rf'ARCHDIOCESE\s+OF\s+([A-Z\s]+?)\.{state}'
    for m in re.finditer(pattern, text[:500000]):
        print(f'  {m.group(0)}')
