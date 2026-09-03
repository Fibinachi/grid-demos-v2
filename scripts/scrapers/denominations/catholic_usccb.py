"""Scrape USCCB dioceses list with homepages."""
import re, json, urllib.request

UA = "Mozilla/5.0"
url = "https://www.usccb.org/about/bishops-and-dioceses/all-dioceses"
req = urllib.request.Request(url, headers={"User-Agent": UA})
html = urllib.request.urlopen(req, timeout=30).read().decode()

# Find all diocese entries: name + website URL pattern
# Pattern: "Arch/Diocese of X ... https?://..." 
entries = re.findall(
    r'(Archdiocese|Diocese|Eparchy|Archeparchy)\s+(?:of\s+)?([^<]+?)'
    r'(?:<[^>]*>)*\s*(?:<[^>]*>)*\s*'
    r'(https?://[^\s<]+)',
    html, re.IGNORECASE
)

# Better approach: find all links that look like diocese websites
# The page has structure: "Diocese of X ... address ... http://website"
dioceses = []
lines = html.split("\n")
for i, line in enumerate(lines):
    # Find website URLs
    url_match = re.search(r'(https?://[^\s"<]+(?:org|com|net|us|info)/?)', line)
    if not url_match:
        continue
    site = url_match.group(1).rstrip("/")
    
    # Look backwards for the diocese name
    for j in range(max(0, i-3), i):
        name_match = re.search(r'(Archdiocese|Diocese|Eparchy|Archeparchy)\s+(?:of\s+)?([A-Z][A-Za-z\s\-–]+?)(?:\s*\(|<|\s+\d)', lines[j])
        if name_match:
            full_name = f"{name_match.group(1)} of {name_match.group(2).strip()}"
            dioceses.append({"name": full_name, "website": site, "type": name_match.group(1)})
            break

# If regex approach fails, use simpler extraction based on observed patterns
if len(dioceses) < 50:
    # Fallback: extract from the markdown content
    # Find all diocese names and their associated URLs
    pattern = r'(Archdiocese|Diocese|Eparchy|Archeparchy)\s+of\s+([A-Z][A-Za-z\s\-–]+?)(?:<|\,|\s+\d)'
    names = re.findall(pattern, html)
    urls = re.findall(r'https?://[^\s"<>]+(?:org|com|net|us|info)', html)
    
    # Print what we found for debugging
    print(f"Found {len(names)} diocese names, {len(urls)} URLs")
    for n in names[:10]:
        print(f"  Name: {n[0]} of {n[1].strip()}")
    for u in urls[:10]:
        print(f"  URL: {u}")

# Deduplicate
seen = set()
unique = []
for d in dioceses:
    key = d["name"].lower().strip()
    if key not in seen:
        seen.add(key)
        unique.append(d)

output = {"count": len(unique), "dioceses": unique}
print(json.dumps(output, indent=2))
