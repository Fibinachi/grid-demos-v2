"""
Scraper for Anglican Church in North America (ACNA) congregation directory.
https://www.acna.org/admin_units?q%5Bkind_eq%5D=Congregation

Output: acna_churches.csv
Columns: church_name, denomination, address, city, state, zip, phone, website, email, clergy
"""
import csv, os, json, re, time, urllib.request, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT = os.path.join(SCRIPT_DIR, "acna_churches.csv")
BASE = "https://www.acna.org"

def fetch_json(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode())
    except:
        return None

def fetch_html(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode("utf-8", errors="ignore")
    except:
        return None

def scrape_congregation(url):
    """Scrape a single congregation page for full details."""
    html = fetch_html(url)
    if not html:
        return {}
    
    data = {}
    
    # Extract email
    m = re.search(r'heading\s+"Email".*?paragraph[^>]*>([^<]+@[^<]+)', html, re.DOTALL)
    if m:
        data["email"] = m.group(1).strip()
    
    # Extract website
    m = re.search(r'heading\s+"Website".*?(?:https?://[^"<\s]+)', html, re.DOTALL)
    if m:
        data["website"] = m.group(0).split("Website")[-1].strip()
        if data["website"].startswith("https://") or data["website"].startswith("http://"):
            pass
        else:
            # Extract from link
            m2 = re.search(r'heading\s+"Website".*?link[^>]*>([^<]+)', html, re.DOTALL)
            if m2:
                data["website"] = m2.group(1).strip()
    
    # Actually, let's try the API approach - ACNA likely has JSON endpoints
    return data

# First, let's try to find the congregation list via the API
# ACNA uses a JSON API - let's check the network requests
print("Discovering ACNA API endpoints...")

# Try the listing page
listing_url = f"{BASE}/admin_units?q%5Bkind_eq%5D=Congregation"
html = fetch_html(listing_url)

if html:
    # Look for total count - the page shows congregation entries
    total_pages = 30  # estimate from ACNA directory
    
    # Extract congregation links (deduplicate)
    all_links = re.findall(r'/admin_units/(\d+)', html)
    churches = list(dict.fromkeys((lid, "") for lid in all_links))
    print("Extracted %d congregation links from page 1" % len(churches))
    
    # Try subsequent pages
    page = 2
    while page <= total_pages:
        page_url = "%s/admin_units?q%%5Bkind_eq%%5D=Congregation&page=%d" % (BASE, page)
        page_html = fetch_html(page_url)
        if not page_html:
            break
        new_links = re.findall(r'/admin_units/(\d+)', page_html)
        new_unique = list(dict.fromkeys((lid, "") for lid in new_links))
        old_count = len(churches)
        for lid, _ in new_unique:
            if lid not in [c[0] for c in churches]:
                churches.append((lid, ""))
        print("  Page %d: +%d new congregations (total: %d)" % (page, len(churches) - old_count, len(churches)))
        page += 1
        time.sleep(1)
    
    print("\nTotal: %d unique ACNA congregations found" % len(churches))
    
    # Now scrape each congregation for details
    results = []
    for i, (cid, cname) in enumerate(churches):
        url = f"{BASE}/admin_units/{cid}"
        detail_html = fetch_html(url)
        
        church = {
            "church_name": cname.strip(),
            "denomination": "Anglican Church in North America",
            "address": "",
            "city": "",
            "state": "",
            "zip": "",
            "phone": "",
            "website": "",
            "email": "",
            "clergy": "",
            "source_url": url,
        }
        
        if detail_html:
            # Extract worship address
            addr_match = re.search(
                r'Worship Address[^<]*<[^>]*>[^<]*<[^>]*>([^<]+)',
                detail_html
            )
            if addr_match:
                church["address"] = addr_match.group(1).strip()
            
            # Extract city, state, zip
            loc_match = re.search(r'([A-Za-z\s]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)', detail_html)
            if loc_match:
                church["city"] = loc_match.group(1).strip()
                church["state"] = loc_match.group(2).strip()
                church["zip"] = loc_match.group(3).strip()
            
            # Phone
            phone_match = re.search(r'heading\s+"Phone"[^<]*<[^>]*>([^<]+)', detail_html)
            if phone_match:
                church["phone"] = phone_match.group(1).strip()
            
            # Website
            web_match = re.search(r'heading\s+"Website"[^<]*<[^>]*>.*?(https?://[^"<\s]+)', detail_html)
            if web_match:
                church["website"] = web_match.group(1).strip()
            
            # Email
            email_match = re.search(r'heading\s+"Email"[^<]*<[^>]*>([^<]+@[^<]+)', detail_html)
            if email_match:
                church["email"] = email_match.group(1).strip()
            
            # Clergy
            clergy_names = re.findall(
                r'heading[^>]*>(Rector|Priest|Deacon|Pastor|Vicar|Bishop|Canon)[^<]*<[^>]*>[^<]*<[^>]*>([^<]+)',
                detail_html
            )
            if clergy_names:
                church["clergy"] = "; ".join("%s: %s" % (r, n.strip()) for r, n in clergy_names)
        
        results.append(church)
        
        if (i + 1) % 10 == 0:
            print(f"  Scraped {i+1}/{len(churches)}: {cname[:30]}...")
            # Save incrementally
            with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=church.keys())
                w.writeheader()
                w.writerows(results)
        
        time.sleep(0.5)
    
    # Final save
    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=church.keys())
        w.writeheader()
        w.writerows(results)
    
    print(f"\n✅ Saved {len(results)} ACNA congregations to {OUTPUT}")
    
    # Count stats
    with_email = sum(1 for r in results if r["email"])
    with_web = sum(1 for r in results if r["website"])
    print(f"   With email: {with_email}")
    print(f"   With website: {with_web}")
else:
    print("❌ Could not access ACNA listing page")
