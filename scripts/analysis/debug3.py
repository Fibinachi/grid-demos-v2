"""Debug exact church link HTML format"""
import urllib.request, re

url = 'https://www.usachurches.org/christian/episcopal-anglican/episcopal-church/'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='replace')

# Find church links with context
count = 0
idx = 0
while count < 3:
    idx = html.find('church/', idx)
    if idx < 0:
        break
    # Show surrounding context
    start = max(0, idx - 100)
    end = min(len(html), idx + 300)
    chunk = html[start:end]
    print('--- Match %d at idx %d ---' % (count+1, idx))
    print(repr(chunk))
    print()
    idx += 1
    count += 1
