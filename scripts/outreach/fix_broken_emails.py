import csv
from pathlib import Path

OUT = Path("outputs/outreach")
fname = OUT / "outreach_emails.csv"

with open(fname, "r", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

fixes = {
    "globalreligiousfutures@pewresearch.org": "info@pewresearch.org",
    "hello@planningcenter.com": "webmaster@planningcenter.com",
    "info@acstechnologies.com": "webmaster@acstechnologies.com",
    "info@listgiant.com": "contact@listgiant.com",
    "roster.stats@lcms.org": "help@lcms.org",
    "sales@elvanto.com": "hello@tithe.ly",
}

fixed = 0
for r in rows:
    if r["contact_value"] in fixes:
        old = r["contact_value"]
        r["contact_value"] = fixes[old]
        print(f"  {r['org'][:40]:40s} {old:40s} -> {r['contact_value']}")
        fixed += 1

with open(fname, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(rows)

print(f"\nFixed {fixed} addresses")

# Now rebuild the unified queue so sender picks up fixes
print("\nRebuilding unified queue...")
