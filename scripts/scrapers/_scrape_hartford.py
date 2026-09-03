"""Scrape Hartford megachurch database — fixed for data-label attributes."""
import urllib.request, re, time, json, os

base = "https://hirr.hartfordinternational.edu/research/megachurch-database/full-list-of-megachurches/"
params = "?sort_order=_sfm_denomination%20asc%20alpha&sf_paged="
all_churches = []

for page in range(1, 68):
    url = f"{base}{params}{page}"
    print(f"Page {page}/67...", end=" ", flush=True)
    
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"ERROR: {e}")
        break
    
    # Parse each <tr> inside <tbody>
    tbody_match = re.search(r'<tbody>(.*?)</tbody>', html, re.DOTALL)
    if not tbody_match:
        print("no tbody")
        continue
    
    rows = re.findall(r'<tr>(.*?)</tr>', tbody_match.group(1), re.DOTALL)
    page_count = 0
    
    for row_html in rows:
        # Extract cells by data-label
        name_match = re.search(r'data-label="Church Name"[^>]*>(.*?)</td>', row_html, re.DOTALL)
        city_match = re.search(r'data-label="City"[^>]*>(.*?)</t[hd]>', row_html, re.DOTALL)
        state_match = re.search(r'data-label="State"[^>]*>(.*?)</t[hd]>', row_html, re.DOTALL)
        size_match = re.search(r'data-label="Size"[^>]*>(.*?)</t[hd]>', row_html, re.DOTALL)
        denom_match = re.search(r'data-label="Denomination"[^>]*>(.*?)</t[hd]>', row_html, re.DOTALL)
        
        if not all([name_match, city_match, state_match, size_match]):
            continue
        
        name = re.sub(r'<[^>]+>', '', name_match.group(1)).strip()
        city = re.sub(r'<[^>]+>', '', city_match.group(1)).strip()
        state = re.sub(r'<[^>]+>', '', state_match.group(1)).strip()
        att_str = re.sub(r'<[^>]+>', '', size_match.group(1)).strip()
        denom = re.sub(r'<[^>]+>', '', denom_match.group(1)).strip()
        
        if not name or name.lower() == 'church name':
            continue
        
        try:
            attendance = int(att_str.replace(',', ''))
        except:
            attendance = 0
        
        all_churches.append({
            'name': name, 'city': city, 'state': state,
            'attendance': attendance, 'denomination': denom,
        })
        page_count += 1
    
    print(f"{page_count} churches | total: {len(all_churches)}")
    time.sleep(0.3)

os.makedirs('data', exist_ok=True)
with open('data/hartford_megachurches.json', 'w') as f:
    json.dump(all_churches, f, indent=2)

print(f"\nDone! {len(all_churches)} megachurches")

# Stats
denoms = {}
for ch in all_churches:
    d = ch['denomination']
    denoms[d] = denoms.get(d, 0) + 1

print(f"Top denominations:")
for d, n in sorted(denoms.items(), key=lambda x: -x[1])[:15]:
    print(f"  {d[:40]:40s} {n:>6,}")
