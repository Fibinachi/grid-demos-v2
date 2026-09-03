"""Scrape Gordon-Conwell MinistryList for churches."""
import urllib.request, json, time, csv, re

d = r'E:\grid'
all_jobs = []

for page in range(1, 15):
    url = f'https://ministrylist.com/wp-json/wp/v2/job-listings?per_page=100&page={page}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read())
        if not data:
            break
        for j in data:
            title = j.get('title',{}).get('rendered','')
            content = j.get('content',{}).get('rendered','')
            
            # Extract church name from content
            church = title
            patterns = [
                r'<strong>(.*?Church.*?)</strong>',
                r'<strong>(.*?Ministry.*?)</strong>',
                r'<strong>(.*?Chapel.*?)</strong>',
                r'<strong>(.*?Fellowship.*?)</strong>',
                r'<strong>(.*?Baptist.*?)</strong>',
                r'<strong>(.*?Assembly.*?)</strong>',
                r'<strong>(.*?Temple.*?)</strong>',
                r'<strong>(.*?Cathedral.*?)</strong>',
                r'<strong>(.*?Center.*?)</strong>',
                r'<strong>(.*?Mission.*?)</strong>',
            ]
            for p in patterns:
                m = re.search(p, content, re.I)
                if m:
                    church = m.group(1)
                    break
            
            church = re.sub(r'<[^>]+>', '', church).strip()
            church = church.replace('&amp;', '&').replace('&#038;', '&')
            
            denom_ids = [str(t) for t in j.get('job_listing_category', [])]
            location = j.get('_job_location', '')
            
            all_jobs.append({
                'church_name': church,
                'position': title,
                'denomination_ids': ','.join(denom_ids),
                'location': location,
                'url': j.get('link', ''),
                'email': '',
            })
        print(f'Page {page}: {len(data)} jobs')
        time.sleep(0.3)
    except Exception as e:
        print(f'Page {page}: {e}')
        break

print(f'\nTotal: {len(all_jobs)}')

# Scrape individual pages for contact info
print('Scraping detail pages for contacts...')
for j in all_jobs:
    if j.get('url'):
        try:
            req = urllib.request.Request(j['url'], headers={'User-Agent': 'Mozilla/5.0'})
            resp = urllib.request.urlopen(req, timeout=10)
            html = resp.read().decode('utf-8', errors='replace')
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
            for e in emails:
                if 'ministrylist.com' not in e and 'gordonconwell' not in e:
                    j['email'] = e
                    break
            time.sleep(0.2)
        except:
            pass

# Save
out = d + '/gordon_conwell_jobs.csv'
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['church_name','position','denomination_ids','location','url','email'])
    w.writeheader()
    w.writerows(all_jobs)
print(f'Saved: {out}')

with_email = sum(1 for j in all_jobs if j['email'])
print(f'With email: {with_email}/{len(all_jobs)}')

# Show sample
print('\nSample:')
for j in all_jobs[:10]:
    print(f'  {j["church_name"][:40]} | {j["location"][:20]} | {j["email"][:30] if j["email"] else "no email"}')
