"""
Debug USAChurches HTML structure
"""
import urllib.request, re

url = 'https://www.usachurches.org/baptist.htm'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='replace')

print("Page length:", len(html))

# Find the content section - after "Christian Denominations > Baptist Churches"
idx = html.find('Baptist Churches')
if idx > 0:
    chunk = html[idx:idx+8000]
    # Print lines containing 'denomination/'
    for line in chunk.split('\n'):
        if 'denomination/' in line.lower():
            print(repr(line.strip()[:250]))
else:
    print("Could not find 'Baptist Churches' in page")

print("\n--- ALL denomination links found ---")
matches = re.findall(r'denomination/([^"\'\\s]+)', html)
print("Total denom links:", len(matches))
for m in matches[:10]:
    print(" ", m)
