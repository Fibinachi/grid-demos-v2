"""
Download all accessible text from Catholic Directory (1907) via Google Books text view.
"""
import requests, re, time, os

book_id = 'Tb0vAQAAMAAJ'
out_dir = 'data/catholic_directory'
os.makedirs(out_dir, exist_ok=True)
out_file = f'{out_dir}/full_text.txt'

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}

# Scan pages 10-600 to find which ones have content
accessible_pages = []
for pg in range(10, 601, 10):
    url = f'https://books.google.com/books?id={book_id}&newbks=0&source=entity_page&pg=PA{pg}&output=text'
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if 'No preview available' not in r.text and len(r.text) > 2000:
            accessible_pages.append(pg)
            print(f'  Page {pg}: OK ({len(r.text):,} chars)')
        else:
            print(f'  Page {pg}: No preview')
    except Exception as e:
        print(f'  Page {pg}: Error - {e}')

print(f'\nAccessible pages at intervals: {accessible_pages}')

# Now get a few specific pages to check content
print('\n=== Sample content ===')
for pg in [20, 50, 100, 200, 300, 400, 500]:
    url = f'https://books.google.com/books?id={book_id}&newbks=0&source=entity_page&pg=PA{pg}&output=text'
    r = requests.get(url, headers=headers, timeout=15)
    # Extract text between paragraph tags
    paras = re.findall(r'<paragraph[^>]*>(.*?)</paragraph>', r.text, re.DOTALL)
    if paras:
        text = ' | '.join(p.strip() for p in paras[:5])
        print(f'  Page {pg}: {text[:200]}')
    else:
        print(f'  Page {pg}: No paragraph content ({len(r.text)} chars)')
