"""Debug church listing URLs"""
import urllib.request, re

families = ['baptist', 'episcopal-anglican', 'lutheran', 'pentecostal', 'other']
denom_slugs = ['alliance-of-baptists', 'episcopal-church', 'evangelical-lutheran-church-in-america', 'assemblies-of-god', 'non-denominational-independent']

for family, slug in zip(families, denom_slugs):
    listing_url = "https://www.usachurches.org/christian/%s/%s/" % (family, slug)
    print("\nURL: %s" % listing_url)
    req = urllib.request.Request(listing_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="replace")
        print("  Length: %d" % len(html))
        m = re.search(r'Showing\s+\d+-\d+\s+of\s+([\d,]+)\s+church', html)
        if m:
            print("  COUNT: %s churches" % m.group(1))
        else:
            print("  No count found")
            # Check if page exists
            if "Page Not Found" in html or "404" in html[:500]:
                print("  PAGE NOT FOUND")
            else:
                # Try alternative page structure
                m2 = re.search(r'(\d+)\s+church', html)
                if m2:
                    print("  Alt count: %s" % m2.group(1))
                else:
                    # Try the denomination page for the listing link
                    print("  First 500 chars:")
                    print(html[:500])
    except Exception as e:
        print("  Error: %s" % str(e)[:100])
