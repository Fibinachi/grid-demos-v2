#!/usr/bin/env python3
"""
Staff Scraper — Scrape known church websites for staff + contact data
=====================================================================
For churches that ALREADY have verified websites (Overture, OSM, batch_finder):
  → Download homepage
  → Extract staff names with roles (Pastor, Secretary, Rector, etc.)
  → Extract emails, phones, social links
  → Write to church_staff table AND update church record

Usage:
    python3 staff_scraper.py --csv churches_with_websites.csv --output staff_results.csv --workers 5
    python3 staff_scraper.py --db churches.db --limit 5000 --workers 5

Output CSV fields:
    id, church_name, website, title, staff_entries, emails, phones, social, has_staff_page
"""
import csv, html, json, os, re, sqlite3, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ── Staff & people extraction patterns ──
STAFF_ROLES = [
    r'(?:^|[\|\n])\s*Senior\s+Pastor',
    r'(?:^|[\|\n])\s*Lead\s+Pastor',
    r'(?:^|[\|\n])\s*Pastor',
    r'(?:^|[\|\n])\s*Reverend',
    r'(?:^|[\|\n])\s*Rev\.?\s*',
    r'(?:^|[\|\n])\s*Rector',
    r'(?:^|[\|\n])\s*Fr\.?\s*',
    r'(?:^|[\|\n])\s*Father',
    r'(?:^|[\|\n])\s*Minister',
    r'(?:^|[\|\n])\s*Deacon',
    r'(?:^|[\|\n])\s*Deaconess',
    r'(?:^|[\|\n])\s*Elder',
    r'(?:^|[\|\n])\s*Bishop',
    r'(?:^|[\|\n])\s*Canon',
    r'(?:^|[\|\n])\s*Vicar',
    r'(?:^|[\|\n])\s*Chaplain',
    r'(?:^|[\|\n])\s*Secretary',
    r'(?:^|[\|\n])\s*Administrator',
    r'(?:^|[\|\n])\s*Director\s+of\s+',
    r'(?:^|[\|\n])\s*Youth\s+Pastor',
    r'(?:^|[\|\n])\s*Children.s\s+Pastor',
    r'(?:^|[\|\n])\s*Worship\s+Pastor',
    r'(?:^|[\|\n])\s*Executive\s+Pastor',
    r'(?:^|[\|\n])\s*Associate\s+Pastor',
    r'(?:^|[\|\n])\s*Music\s+Director',
    r'(?:^|[\|\n])\s*Office\s+Manager',
    r'(?:^|[\|\n])\s*Business\s+Manager',
    r'(?:^|[\|\n])\s*Coordinator',
    r'(?:^|[\|\n])\s*Treasurer',
    r'(?:^|[\|\n])\s*Clerk',
]

NAME_RE = re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})')


def extract_staff(text, url):
    """Extract staff names with roles from HTML text."""
    text_upper = text.upper()
    staff = []
    seen = set()
    
    # Pattern 1: "Role: Name" or "Role Name" in page text
    for role_pat in STAFF_ROLES:
        for m in re.finditer(role_pat, text_upper):
            start = m.end()
            # Look for a name after the role (within next 100 chars)
            snippet = text_upper[start:start+100]
            # Remove separator characters
            snippet = re.sub(r'^[\s:\-–—\|]+', '', snippet)
            name_m = NAME_RE.search(snippet)
            if name_m:
                name = name_m.group(1).strip()
                # Get the role (clean it up)
                role_text = m.group(0).strip().lstrip('\n|').strip()
                role = re.sub(r'^[\s\|]+', '', role_text)
                key = (name, role)
                if key not in seen and len(name) > 4:
                    seen.add(key)
                    staff.append({"name": name, "role": role})
    
    # Pattern 2: HTML title tag with " | " separator (e.g., "Pastor John Smith | First Baptist")
    title_m = re.search(r'<title[^>]*>(.*?)</title>', text, re.IGNORECASE|re.DOTALL)
    title = ""
    if title_m:
        title = html.unescape(re.sub(r'<[^>]+>', '', title_m.group(1))).strip()
        # Extract from title
        for role_pat in STAFF_ROLES:
            for m in re.finditer(role_pat, title.upper()):
                rest = title.upper()[m.end():]
                rest = rest.lstrip().lstrip(':').lstrip('-').lstrip()
                # Name is usually next word(s) before " | " or end
                name_m = NAME_RE.search(rest)
                if name_m:
                    name = name_m.group(1).strip()
                    role = m.group(0).strip()
                    key = (name, role)
                    if key not in seen and len(name) > 4:
                        seen.add(key)
                        staff.append({"name": name, "role": role})
    
    return staff, title


def extract_emails(text):
    emails = set()
    for m in re.finditer(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text):
        emails.add(m.group(1).lower())
    for m in re.finditer(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text):
        e = m.group(0).lower()
        if not any(s in e for s in ['png','jpg','css','.js','example','.png','.jpg']) and '.' in e.split('@')[1]:
            emails.add(e)
    return list(emails)[:10]


def extract_phones(text):
    phones = set()
    for m in re.finditer(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text):
        p = re.sub(r'[^\d]', '', m.group(0))
        if len(p) == 10:
            phones.add(p)
    return list(phones)[:5]


def extract_social(text):
    social = []
    for m in re.finditer(r'href=[\'"](https?://(?:www\.)?(facebook|instagram|youtube|twitter|x)\.com[^\'"]*)[\'"]', text, re.IGNORECASE):
        social.append(f"{m.group(2)}:{m.group(1)}")
    return social[:5]


# ── New: Service times ──
def extract_service_times(text):
    times = []
    patterns = [
        r'(?:sunday|sun|saturday|sat|wednesday|wed|thursday|thur|friday|fri|saturday|sat)\s*(?:services?|worship|mass|celebration|gathering)?\s*(?:at\s*)?(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.))',
        r'(?:worship|mass|service)\s*(?:times?|schedule)\s*(?::|at)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))',
        r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))\s*(?:-|–)\s*(\d{1,2}(?::\d{2})?\s*(?:am|pm))',
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            times.append(m.group(0).strip()[:50])
    return list(set(times))[:5]


# ── New: Languages ──
LANG_PATTERNS = {
    "spanish": r'\b(?:spanish|espanol|español|hispanic|latino)\b',
    "korean": r'\b(?:korean|한국어)\b',
    "chinese": r'\b(?:chinese|mandarin|cantonese|中文)\b',
    "vietnamese": r'\b(?:vietnamese|tiếng\s+việt)\b',
    "tagalog": r'\b(?:tagalog|filipino)\b',
    "french": r'\b(?:french|français|francais)\b',
    "portuguese": r'\b(?:portuguese|português|portugues)\b',
    "russian": r'\b(?:russian|русский)\b',
    "arabic": r'\b(?:arabic|العربية)\b',
    "amharic": r'\b(?:amharic|አማርኛ)\b',
    "burmese": r'\b(?:burmese|myanmar|ဗမာ)\b',
    "swahili": r'\b(?:swahili|kiswahili)\b',
}

def extract_languages(text):
    found = []
    for lang, pat in LANG_PATTERNS.items():
        if re.search(pat, text, re.IGNORECASE):
            found.append(lang)
    return found


# ── New: Community services ──
def extract_community_services(text):
    services = {}
    # These are all existing columns in the DB
    checks = {
        "has_food_pantry": r'\b(?:food\s+(?:pantry|bank|closet)|soup\s+kitchen|community\s+meal|food\s+distribution)\b',
        "has_preschool": r'\b(?:preschool|pre.?school|nursery\s+school|early\s+childhood|p.k3|p.k4|prek)\b',
        "has_daycare": r'\b(?:daycare|day\s+care|child\s+care|childcare)\b',
        "has_youth": r'\b(?:youth\s+(?:group|ministry|program)|teen|youth\s+night|jr\.?\s+high)\b',
        "has_children": r'\b(?:children.?s\s+ministry|kids\s+club|children.?s\s+church|awana|vacation\s+bible|vbs)\b',
        "has_seniors": r'\b(?:senior\s+(?:ministry|adult|program)|golden\s+age|elderly|prime\s+timers)\b',
        "has_esl": r'\b(?:esl|english\s+(?:as\s+)?(?:second|classes?)|language\s+classes?)\b',
        "has_recovery": r'\b(?:recovery|celebrate\s+recovery|aa|alcoholics|na\s+meeting|overcomers?)\b',
        "has_missions": r'\b(?:missions?|missionary|global\s+outreach|short.?term\s+mission)\b',
        "has_counseling": r'\b(?:counseling|counselling|pastoral\s+care|support\s+group|grief\s+share)\b',
        "has_sports": r'\b(?:sports?|upward|athletic|basketball\s+league|soccer|softball|recreation)\b',
    }
    for col, pat in checks.items():
        if re.search(pat, text, re.IGNORECASE):
            services[col] = 1
    return services


# ── New: Livestream / Online Giving ──
def extract_livestream(text, url):
    for m in re.finditer(r'href=[\'"]([^\'"]*(?:watch|live|livestream|live\.stream|sermons?|message|media)[^\'"]*)[\'"]', text, re.IGNORECASE):
        href = m.group(1)
        if href.startswith("/"):
            from urllib.parse import urljoin
            href = urljoin(url, href)
        if href.startswith("http"):
            return href
    return ""


def extract_online_giving(text, url):
    for m in re.finditer(r'href=[\'"]([^\'"]*(?:give|donate|donation|online.?giving|tithes?|offering|pushpay|subsplash|giving\.church|tithely)[^\'"]*)[\'"]', text, re.IGNORECASE):
        href = m.group(1)
        if href.startswith("/"):
            from urllib.parse import urljoin
            href = urljoin(url, href)
        if href.startswith("http"):
            return href
    return ""


def extract_worship_style(text):
    styles = []
    if re.search(r'\b(?:contemporary|modern|band|praise\s+team|projection|screen)\b', text, re.IGNORECASE):
        styles.append("contemporary")
    if re.search(r'\b(?:traditional|hymnal|organ|choir|liturgical|vestments|chant)\b', text, re.IGNORECASE):
        styles.append("traditional")
    if re.search(r'\b(?:blended|mix)\b', text, re.IGNORECASE):
        styles.append("blended")
    return "; ".join(styles[:3])


def find_staff_page(url, text):
    """Look for /staff /leadership /about /team links on homepage."""
    for m in re.finditer(r'href=[\'"]([^\'"]*(?:staff|leadership|about.?us|pastor|team|clergy|directory|our.?people)[^\'"]*)[\'"]', text, re.IGNORECASE):
        href = m.group(1)
        if href.startswith('/'):
            from urllib.parse import urljoin
            href = urljoin(url, href)
        elif not href.startswith('http'):
            continue
        return href
    return None


def scrape_church(church_id, name, website, source_label="common_crawl"):
    """Scrape one church website for staff + contacts."""
    result = {
        "id": church_id, "name": name, "website": website,
        "title": "", "status": "error", "confidence": 0,
        "staff_entries": "", "emails": "", "phones": "", "social": "",
        "has_staff_page": 0, "staff_page_url": "",
        "service_times": "", "languages": "", "worship_style": "",
        "has_food_pantry": 0, "has_preschool": 0, "has_daycare": 0,
        "has_youth": 0, "has_children": 0, "has_seniors": 0,
        "has_esl": 0, "has_recovery": 0, "has_missions": 0,
        "has_counseling": 0, "has_sports": 0,
        "livestream_link": "", "online_giving_link": "",
    }
    
    if not website:
        result["status"] = "no_website"
        return result
    
    try:
        req = urllib.request.Request(website,
            headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                     "Accept":"text/html"})
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read(500*1024)
        text = raw.decode("utf-8","replace")
    except Exception as e:
        result["status"] = f"fetch_error:{str(e)[:30]}"
        return result
    
    result["status"] = "scraped"
    
    # Extract data
    staff, title = extract_staff(text, website)
    emails = extract_emails(text)
    phones = extract_phones(text)
    social = extract_social(text)
    staff_page = find_staff_page(website, text) if not (title and any(s in (title or "").upper() for s in ['STAFF','LEADERSHIP','CLERGY','PASTOR'])) else None
    
    result["title"] = title
    result["emails"] = "; ".join(emails)
    result["phones"] = "; ".join(phones)
    result["social"] = "; ".join(social)
    
    # Extra data
    result["service_times"] = "; ".join(extract_service_times(text))[:200]
    langs = extract_languages(text)
    result["languages"] = "; ".join(langs) if langs else ""
    result["worship_style"] = extract_worship_style(text)
    
    services = extract_community_services(text)
    for col, val in services.items():
        result[col] = val
    
    result["livestream_link"] = extract_livestream(text, website)
    result["online_giving_link"] = extract_online_giving(text, website)
    
    if staff:
        result["staff_entries"] = "; ".join(f"{s['name']} ({s['role']})" for s in staff[:8])
    
    if staff_page:
        result["has_staff_page"] = 1
        result["staff_page_url"] = staff_page
    
    result["confidence"] = 80 if staff else (60 if emails or phones else 40)
    
    # Also scrape staff page if found
    if staff_page:
        time.sleep(0.2)
        try:
            req2 = urllib.request.Request(staff_page,
                headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(req2, timeout=10) as r:
                raw2 = r.read(500*1024)
            text2 = raw2.decode("utf-8","replace")
            staff2, _ = extract_staff(text2, staff_page)
            emails2 = extract_emails(text2)
            phones2 = extract_phones(text2)
            
            existing_entries = set(result["staff_entries"].split("; ")) if result["staff_entries"] else set()
            for s in staff2:
                entry = f"{s['name']} ({s['role']})"
                if entry not in existing_entries:
                    existing_entries.add(entry)
            
            if staff2:
                result["staff_entries"] = "; ".join(
                    f"{s['name']} ({s['role']})" for s in staff2[:15]
                )
            if emails2 and not result["emails"]:
                result["emails"] = "; ".join(emails2[:5])
            if phones2 and not result["phones"]:
                result["phones"] = "; ".join(phones2[:3])
        except:
            pass
    
    return result


CSV_FIELDS = [
    "id", "name", "website", "title", "status", "confidence",
    "staff_entries", "emails", "phones", "social",
    "has_staff_page", "staff_page_url",
    "service_times", "languages", "worship_style",
    "has_food_pantry", "has_preschool", "has_daycare",
    "has_youth", "has_children", "has_seniors",
    "has_esl", "has_recovery", "has_missions",
    "has_counseling", "has_sports",
    "livestream_link", "online_giving_link",
]


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", help="Input CSV (id,name,website)")
    parser.add_argument("--output", default="data/staff_results.csv")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--db", default="churches.db")
    args = parser.parse_args()
    
    workers = args.workers
    print(f"[{datetime.now()}] Staff scraper starting with {workers} workers...")
    
    # Load churches with websites
    churches = []
    if args.csv:
        with open(args.csv, 'r', encoding='utf-8') as f:
            for r in csv.DictReader(f):
                churches.append({
                    "id": r.get("id",""), "name": r.get("name",""),
                    "website": r.get("website",""),
                })
    else:
        db = sqlite3.connect(args.db)
        q = """
            SELECT id, name, website FROM churches 
            WHERE website IS NOT NULL AND website != ''
            ORDER BY 
                CASE WHEN website_source='overture' THEN 1 ELSE 2 END,
                website_confidence DESC,
                id
        """
        if args.limit: q += f" LIMIT {args.limit}"
        churches = [{"id":str(r[0]),"name":r[1],"website":r[2]} for r in db.execute(q).fetchall()]
        db.close()
    
    print(f"Loaded {len(churches):,} churches with websites")
    if not churches: return
    
    start = time.time()
    results = []
    done = 0
    
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for c in churches:
            futures[pool.submit(scrape_church, c["id"], c["name"], c["website"])] = c
        
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            done += 1
            
            if done % 100 == 0:
                elapsed = time.time()-start
                rate = done/elapsed if elapsed>0 else 0
                staff_count = sum(1 for x in results if x["staff_entries"])
                print(f"  {done:,}/{len(churches):,} ({rate:.0f}/s) — staff found: {staff_count:,}")
                
                if done % 1000 == 0:
                    with open(args.output, 'w', newline='', encoding='utf-8') as f:
                        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
                        w.writeheader()
                        w.writerows(results)
    
    elapsed = time.time()-start
    # Final write
    with open(args.output, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction='ignore')
        w.writeheader()
        w.writerows(results)
    
    staff_count = sum(1 for r in results if r["staff_entries"])
    email_count = sum(1 for r in results if r["emails"])
    phone_count = sum(1 for r in results if r["phones"])
    
    print(f"\nDone! {done:,} churches in {elapsed:.0f}s ({done/elapsed:.0f}/s)")
    print(f"Staff found:  {staff_count:,} churches")
    print(f"Emails found: {email_count:,} churches")
    print(f"Phones found: {phone_count:,} churches")


if __name__ == "__main__":
    main()
