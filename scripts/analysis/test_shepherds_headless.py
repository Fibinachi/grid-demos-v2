"""Test if Shepherd's Stream data is in raw HTML (headless-friendly)."""
import urllib.request, re

url = "https://shepherdsstream.org/arkansas-church-directory/first-baptist-church-376"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="replace")

checks = {
    "state": r"State</div><div class=.jrFieldValue.>([^<]+)",
    "denom": r"Denomination</div><div class=.jrFieldValue.>\s*<a[^>]*>([^<]+)",
    "phone": r"Main Phone</div><div class=.jrFieldValue.>([^<]+)",
    "website": r"Website</div><div class=.jrFieldValue.><a href=\"([^\"]+)\"",
}
for name, pat in checks.items():
    m = re.search(pat, html)
    print(f"{name}: {m.group(1).strip() if m else 'NOT FOUND'}")

print(f"\nHas field_group2 (Location): {'field_group2' in html}")
print(f"Has field_group3 (Doctrine): {'field_group3' in html}")
print(f"Page size: {len(html)} bytes")
