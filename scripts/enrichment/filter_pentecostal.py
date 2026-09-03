"""Generate Pentecostal send list from all local sources."""
import csv, os
from collections import defaultdict

d = r"E:\grid"

PENT_KEYWORDS = [
    "pentecostal", "assembly of god", "assemblies of god", "church of god",
    "apostolic", "foursquare", "charismatic", "word of faith",
    "vineyard", "full gospel", "holiness", "cogic",
    "church of god in christ", "calvary chapel",
    "united pentecostal", "nazarene", "wesleyan",
]

# Build domain -> denomination map from church_contacts.csv
contacts = list(csv.DictReader(open(os.path.join(d, "church_contacts.csv"), encoding="utf-8-sig")))
pent_domains = set()
for r in contacts:
    denom = (r.get("denomination", "") or "").lower()
    web = (r.get("website", "") or "").strip().lower().replace("https://","").replace("http://","").replace("www.","").split("/")[0]
    if web and any(k in denom for k in PENT_KEYWORDS):
        pent_domains.add(web)
    # Also check page_url for church names
    name = (r.get("church_name", "") or "").lower()
    if any(k in name for k in PENT_KEYWORDS):
        if web:
            pent_domains.add(web)

print("Pentecostal domains: %d" % len(pent_domains))

# Check all email sources for matching domains
results = []
seen = set()

def check_email(email, source, name):
    if not email or "@" not in email or email in seen:
        return
    domain = email.split("@")[1].lower()
    if domain in pent_domains:
        seen.add(email)
        results.append({"email": email, "source": source, "name": str(name)[:60]})

# 1. Church master list
master = list(csv.DictReader(open(os.path.join(d, "church_master_emails.csv"), encoding="utf-8-sig")))
for r in master:
    email = (r.get("email", "") or r.get("EMAIL", "") or "").strip().lower()
    check_email(email, "master", r.get("church_name", ""))

# 2. Church scraper results
scraped = list(csv.DictReader(open(os.path.join(d, "church_emails_scraped.csv"), encoding="utf-8-sig")))
for r in scraped:
    email = (r.get("email", "") or "").strip().lower()
    check_email(email, "scraper", r.get("church_name", ""))

# 3. Church clean send
clean = list(csv.DictReader(open(os.path.join(d, "church_clean_send.csv"), encoding="utf-8-sig")))
for r in clean:
    email = (r.get("email", "") or r.get("EMAIL", "") or "").strip().lower()
    check_email(email, "clean", r.get("church_name", "") or r.get("NAME", ""))

# 4. SC churches
try:
    sc = list(csv.DictReader(open(os.path.join(d, "sc_church_emails.csv"), encoding="utf-8-sig")))
    for r in sc:
        email = (r.get("email", "") or "").strip().lower()
        check_email(email, "sc", r.get("church_name", ""))
except: pass

# 5. Anglican
try:
    ang = list(csv.DictReader(open(os.path.join(d, "church_anglican_episcopal_emails.csv"), encoding="utf-8-sig")))
    for r in ang:
        email = (r.get("email", "") or r.get("EMAIL", "") or "").strip().lower()
        check_email(email, "anglican", r.get("church_name", ""))
except: pass

output = os.path.join(d, "send_list_pentecostal.csv")
with open(output, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["email","source","name"])
    w.writeheader()
    for r in results:
        w.writerow(r)

print("\nTotal Pentecostal emails: %d" % len(results))
print("Saved to: send_list_pentecostal.csv")
for r in results[:10]:
    print("  %s" % r["email"])
