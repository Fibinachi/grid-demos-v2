"""Scan the Irish Church Directory text to find the clerical list."""
with open('data/irish_directory/full_text.txt', encoding='utf-8') as f:
    text = f.read()

parts = text.split('=== PAGE ')

# Find pages with clergy data
for p in parts:
    if not p.strip():
        continue
    page_num = p.split('===')[0].strip() if '===' in p else p[:5]
    if page_num.isdigit() and int(page_num) >= 40 and int(page_num) <= 55:
        # Show first 300 chars
        content = p[p.index('\n')+1:] if '\n' in p else p
        print(f'--- PAGE {page_num} ---')
        print(content[:400])
        print()
