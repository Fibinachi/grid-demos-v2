"""
Scrape SBC Executive Committee members and staff.
Parses committee members (name, title, location) and staff (name, title, phone, email).
Stores in church_staff linked to the SBC parent church record.
"""
import urllib.request, re, sqlite3, json, os, time
from datetime import datetime

DB_PATH = r'E:\grid\churches.db'

def fetch(url):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html'
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='replace')

def parse_committee(html):
    """Parse Executive Committee members."""
    members = []
    # Simple split on each person div
    chunks = html.split('<div class="people__item person">')[1:]
    
    for chunk in chunks:
        # End at the closing </div> for this person
        end = chunk.find('</div>')
        if end < 0:
            continue
        item = chunk[:end]
        
        name_m = re.search(r'<h5[^>]*class="person__title"[^>]*>(.*?)</h5>', item)
        role_m = re.search(r'<p[^>]*class="person__position"[^>]*>(.*?)</p>', item)
        
        name = name_m.group(1).strip() if name_m else ''
        role = role_m.group(1).strip() if role_m else ''
        
        # Location is text after the role paragraph
        location = ''
        if role_m:
            after_role = item[role_m.end():]
            loc_m = re.match(r'\s*([^<]+?)\s*(?:<|$)', after_role)
            if loc_m:
                location = loc_m.group(1).strip()
        
        city, state = '', ''
        if location:
            parts = location.rsplit(', ', 1)
            if len(parts) == 2:
                city, state = parts[0].strip(), parts[1].strip()
        
        if name:
            members.append({
                'name': name,
                'role': role,
                'city': city,
                'state': state,
                'source': 'sbc_ec_committee'
            })
    return members

def parse_staff(html):
    """Parse SBC EC Staff."""
    staff = []
    chunks = html.split('<div class="people__item person">')[1:]
    
    for chunk in chunks:
        end = chunk.find('</div>')
        if end < 0:
            continue
        item = chunk[:end]
        
        name_m = re.search(r'<h5[^>]*class="person__title"[^>]*>(.*?)</h5>', item)
        role_m = re.search(r'<p[^>]*class="person__position"[^>]*>(.*?)</p>', item)
        phone_m = re.search(r'<p[^>]*class="person__phone"[^>]*>(.*?)</p>', item)
        email_m = re.search(r'<p[^>]*class="person__email"[^>]*>(.*?)</p>', item)
        
        name = name_m.group(1).strip() if name_m else ''
        role = re.sub(r'<[^>]+>', '', role_m.group(1)).strip() if role_m else ''
        phone = re.sub(r'<[^>]+>', '', phone_m.group(1)).strip() if phone_m else ''
        email = re.sub(r'<[^>]+>', '', email_m.group(1)).strip() if email_m else ''
        
        if name:
            staff.append({
                'name': name,
                'role': role,
                'phone': phone,
                'email': email,
                'source': 'sbc_ec_staff'
            })
    return staff

def main():
    print("Scraping SBC Executive Committee...")
    
    # Fetch committee members page
    mem_html = fetch("https://www.sbc.net/about/what-we-do/sbc-entities/executive-committee/committee-members/")
    members = parse_committee(mem_html)
    print(f"  Members: {len(members)}")
    
    # Fetch staff page
    staff_html = fetch("https://www.sbc.net/about/what-we-do/sbc-entities/executive-committee/staff/")
    staff = parse_staff(staff_html)
    print(f"  Staff: {len(staff)}")
    
    # Save to JSON
    output = {
        'scraped_at': datetime.now().isoformat(),
        'committee_members': members,
        'staff': staff
    }
    out_path = r'E:\grid\data\sbc_ec.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\nSaved to {out_path}")
    
    # Print summary
    print("\n=== Committee Members ===")
    for m in members[:5]:
        loc = f"{m['city']}, {m['state']}" if m['city'] else ''
        print(f"  {m['name']:35s} {m['role']:30s} {loc}")
    if len(members) > 5:
        print(f"  ... and {len(members)-5} more")
    
    print("\n=== Staff ===")
    for s in staff[:10]:
        print(f"  {s['name']:30s} {s['role']:40s} {s['phone']:15s} {s['email']}")
    if len(staff) > 10:
        print(f"  ... and {len(staff)-10} more")

if __name__ == '__main__':
    main()
