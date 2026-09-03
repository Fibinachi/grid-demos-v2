"""Parse all useful data from a Religiana building page."""
import requests
from bs4 import BeautifulSoup

r = requests.get('https://religiana.com/node/15155', allow_redirects=True, timeout=10)
print(f'URL: {r.url}')
soup = BeautifulSoup(r.text, 'html.parser')

# Title
h1 = soup.find('h1', class_='article-header-title')
title = h1.get_text(strip=True) if h1 else 'N/A'
print(f'Title: {title}')

# Location from first paragraph with img
location = 'N/A'
for p in soup.find_all('p'):
    imgs = p.find_all('img')
    if imgs and p.get_text(strip=True) and len(p.get_text(strip=True)) < 100:
        location = p.get_text(strip=True)
        print(f'Location: {location}')
        break

# Find coordinates - look in image alt text containing lat,lng
for img in soup.find_all('img'):
    alt = img.get('alt', '')
    if alt and ',' in alt:
        parts = alt.split(',')
        if len(parts) == 2:
            try:
                float(parts[0].strip())
                float(parts[1].strip())
                print(f'Coords from img alt: {alt}')
            except:
                pass

# Check for map iframe src
for iframe in soup.find_all('iframe'):
    src = iframe.get('src', '')
    if 'll=' in src:
        ll = src.split('ll=')[1].split('&')[0]
        print(f'Coords from iframe: {ll}')

# Check all meta tags
for meta in soup.find_all('meta'):
    if meta.get('name') and meta.get('content'):
        print(f'Meta {meta["name"]}: {meta["content"][:150]}')

# Check for building type in tags or categories
for a in soup.find_all('a'):
    href = a.get('href', '')
    text = a.get_text(strip=True)
    if '/type/' in href or '/category/' in href or '/tags/' in href:
        print(f'Category/Tag: {text} -> {href}')
    if text in ('Church', 'Cathedral', 'Abbey', 'Chapel', 'Mosque', 'Synagogue', 'Temple', 'Monastery', 'Hermitage'):
        print(f'Type link: {text} -> {href}')

# Check for building type from the body class
body = soup.find('body')
if body:
    for cls in body.get('class', []):
        if 'node-type' in cls or 'node--' in cls:
            print(f'Body class: {cls}')

# Check for taxonomy/field tags
for div in soup.find_all('div', class_=lambda c: c and ('field' in str(c).lower() or 'taxonomy' in str(c).lower() or 'tags' in str(c).lower())):
    print(f'Field div: {div.get("class", "")} -> {div.get_text(strip=True)[:100]}')

# Description
article = soup.find('article')
if article:
    for p in article.find_all('p'):
        t = p.get_text(strip=True)
        if len(t) > 80:
            print(f'DESC: {t[:200]}')
            break
