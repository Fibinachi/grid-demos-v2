"""Cross-reference CA registry against our foundation data."""
import csv, sys

# Load CA registry
with open("ca_registry.csv", encoding="utf-8") as f:
    ca_rows = {}
    for r in csv.DictReader(f):
        fein = r.get("FEIN", "").strip()
        if fein:
            ca_rows[fein] = r

print(f"CA Registry: {len(ca_rows):,} entries")

# Load our enriched contacts
with open("enriched_contacts.csv", encoding="utf-8") as f:
    our_rows = list(csv.DictReader(f))

# Find CA foundations that match
ca_ours = [r for r in our_rows if r.get("STATE", "") == "CA"]
print(f"Our CA foundations: {len(ca_ours):,}")

matched = 0
ca_reg_numbers = 0
for r in ca_ours:
    ein = r["EIN"].strip()
    if ein in ca_rows:
        matched += 1
        if ca_rows[ein].get("State Charity Reg#", "").strip():
            ca_reg_numbers += 1

print(f"Matched in CA registry: {matched:,}")
print(f"With CA registration #: {ca_reg_numbers:,}")
if ca_ours:
    print(f"Match rate: {matched/len(ca_ours)*100:.0f}%")
print()

# Show example matches
for r in ca_ours[:5]:
    ein = r["EIN"].strip()
    if ein in ca_rows:
        cr = ca_rows[ein]
        name = r.get("NAME", "")[:40]
        ct = cr.get("State Charity Reg#", "")
        status = cr.get("Registry Status", "")
        print(f"  {name:40s} CT#{ct:15s} Status: {status:15s}")
