"""Analyze Religiana page HTML structure for building data extraction."""
import requests
from bs4 import BeautifulSoup

r = requests.get('https://religiana.com/node/88', allow_redirects=True, timeout=10)
soup = BeautifulSoup(r.text, 'html.parser')

# Title
h1 = soup.find('h1', class_='article-header-title')
print(f'Title: {h1.get_text(strip=True) if h1 else "N/A"}')

# Location paragraph
loc_para = soup.find('p', class_=lambda c: c and 'article-header-place' in str(c))
if not loc_para:
    for p in soup.find_all('p'):
        imgs = p.find_all('img')
        if imgs and p.get_text(strip=True):
            print(f'Location: {p.get_text(strip=True)}')
            break

# Address
for h in soup.find_all(['h3', 'h4']):
    txt = h.get_text(strip=True)
    if 'Address' in txt:
        parent = h.find_parent(['div', 'section'])
        if parent:
            print(f'Address section: {parent.get_text(strip=True)[:300]}')

# Building type
meta = soup.find('meta', attrs={'name': 'description'})
print(f'Meta desc: {meta["content"][:150] if meta else "N/A"}')

# Check for type in breadcrumbs/links
type_keywords = ['Church', 'Cathedral', 'Abbey', 'Chapel', 'Mosque', 'Synagogue', 'Temple', 'Monastery', 'Hermitage']
for a in soup.find_all('a'):
    text = a.get_text(strip=True)
    if text in type_keywords:
        print(f'Building type link: {text} -> {a.get("href", "")}')

# Features and facilities
for h in soup.find_all(['h3', 'h4']):
    txt = h.get_text(strip=True)
    if 'Feature' in txt or 'Facilit' in txt or 'Visitor' in txt:
        ul = h.find_next('ul')
        if ul:
            items = [li.get_text(strip=True) for li in ul.find_all('li')]
            print(f'{txt}: {items}')

# Opening times
for h in soup.find_all(['h3', 'h4']):
    if 'Opening' in h.get_text(strip=True) or 'Times' in h.get_text(strip=True):
        parent = h.find_parent(['div'])
        if parent:
            text = parent.get_text(strip=True).replace(h.get_text(strip=True), '').strip()
            print(f'Opening: {text[:200]}')

# Description paragraphs
article = soup.find('article')
if article:
    desc_paras = article.find_all('p')
    print(f'Description paragraphs: {len(desc_paras)}')
    for p in desc_paras[:3]:
        t = p.get_text(strip=True)
        if len(t) > 50:
            print(f'  DESC: {t[:150]}')
