"""Debug listing page HTML structure"""
import urllib.request, re

url = 'https://www.usachurches.org/christian/episcopal-anglican/episcopal-church/'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='replace')

# Search for key patterns
for pattern in ['Showing', 'church listing', 'listings', 'total']:
    idx = html.lower().find(pattern.lower())
    if idx >= 0:
        snippet = html[max(0,idx-50):idx+300]
        print('--- %s at %d ---' % (pattern, idx))
        print(snippet)
        print()

# Check for pagination
if 'Next' in html:
    print('Has Next page link')
if 'pagination' in html.lower():
    print('Has pagination')

# Number of church links
church_links = re.findall(r'/church/([\.\w-]+)', html)
print('\nChurch links found: %d' % len(set(church_links)))
for cl in list(set(church_links))[:10]:
    print(' ', cl)
