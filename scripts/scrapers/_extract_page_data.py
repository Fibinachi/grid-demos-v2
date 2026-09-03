"""Extract all useful text data from a Religiana page."""
import requests, re, json
from bs4 import BeautifulSoup

def extract_page(node_id):
    url = f'https://religiana.com/node/{node_id}'
    r = requests.get(url, allow_redirects=True, timeout=10)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    data = {'religiana_id': node_id, 'url': r.url}
    
    # Title
    h1 = soup.find('h1', class_='article-header-title')
    data['name'] = h1.get_text(strip=True) if h1 else 'N/A'
    
    # Body class for type
    body = soup.find('body')
    btype = None
    if body:
        for cls in body.get('class', []):
            if cls.startswith('page-node-type-'):
                btype = cls.replace('page-node-type-', '')
    data['building_type'] = btype or 'N/A'
    
    # Meta description
    meta = soup.find('meta', attrs={'name': 'description'})
    data['meta_description'] = meta.get('content', '').strip() if meta else ''
    
    # Location text - usually the first <p> with text near the map
    # Look for the location div
    loc_div = soup.find('div', class_='location')
    if loc_div:
        data['location_block'] = loc_div.get_text(' ', strip=True)
    else:
        data['location_block'] = ''
    
    # All paragraphs in article
    article = soup.find('article')
    paragraphs = []
    if article:
        for p in article.find_all('p'):
            txt = p.get_text(strip=True)
            if txt and len(txt) > 10:
                paragraphs.append(txt)
    data['article_paragraphs'] = paragraphs[:5]  # first 5
    
    # The sidebar info (address, opening hours, etc.)
    sidebar = soup.find('div', class_=lambda c: c and 'sidebar' in str(c).lower())
    sidebar_info = {}
    if sidebar:
        # Find field labels and values
        for field in sidebar.find_all(['div', 'span', 'p'], class_=lambda c: c and 'field' in str(c).lower()):
            label = field.find(['strong', 'b', 'h3', 'h4', 'span', 'div'], class_=lambda c: c and 'label' in str(c).lower())
            if label:
                key = label.get_text(strip=True).rstrip(':')
                val = label.next_sibling
                if val:
                    val_text = val.get_text(strip=True) if hasattr(val, 'get_text') else str(val)
                    sidebar_info[key] = val_text
    
    data['sidebar_info'] = sidebar_info
    
    # Also look for h3 headings with common labels
    for h3 in soup.find_all(['h3', 'h4']):
        txt = h3.get_text(strip=True)
        parent = h3.find_parent(['div', 'section', 'aside'])
        if parent:
            next_text = ''
            for sibling in h3.find_next_siblings():
                if sibling.name in ['h3', 'h4']: break
                next_text += sibling.get_text(' ', strip=True) + ' '
            sidebar_info[txt] = next_text.strip()
    
    return data

# Test a few pages
for node_id in [88, 15155, 17199, 17208, 85]:
    data = extract_page(node_id)
    print(f"\n--- ID={node_id} ({data['building_type']}) ---")
    print(f"Name: {data['name']}")
    print(f"URL: {data['url']}")
    print(f"Location block: {data['location_block'][:200]}")
    print(f"Sidebar: {json.dumps(data['sidebar_info'], indent=2)[:500]}")
    if data['article_paragraphs']:
        print(f"First para: {data['article_paragraphs'][0][:200]}")
