"""
Generate church listings organized by state.
Parses addresses from church_contacts.csv and creates per-state CSV files.
Also generates a summary report.
"""
import csv, os, re
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(SCRIPT_DIR, "church_contacts.csv")
OUT_DIR = os.path.join(SCRIPT_DIR, "church_by_state")

os.makedirs(OUT_DIR, exist_ok=True)

# Read contacts
contacts = list(csv.DictReader(open(INPUT, encoding="utf-8-sig")))
print("Loaded %d church records" % len(contacts))

# Group by state
by_state = defaultdict(list)
no_state = []
state_counts = defaultdict(int)

for r in contacts:
    cs = r.get("city_state", "").strip()
    name = r.get("church_name", "").strip()
    website = r.get("website", "").strip()
    phone = r.get("phone", "").strip()
    
    # Try to extract state from city_state (format: "123 Street, City, ST")
    state = None
    if cs:
        # Look for 2-letter state code at end after comma
        m = re.search(r',\s*([A-Z]{2})\s*$', cs)
        if m:
            state = m.group(1)
    
    if state:
        by_state[state].append(r)
        state_counts[state] += 1
    else:
        no_state.append(r)

# Write per-state CSV files
fieldnames = contacts[0].keys()
for state in sorted(by_state.keys()):
    rows = by_state[state]
    fname = "churches_%s.csv" % state
    fpath = os.path.join(OUT_DIR, fname)
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    print("  %s: %d churches → %s" % (state, len(rows), fname))

# Write no-state rows
if no_state:
    fpath = os.path.join(OUT_DIR, "churches_NO_STATE.csv")
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(no_state)
    print("  NO_STATE: %d churches → %s" % (len(no_state), fpath))

# Generate summary
print("\n" + "=" * 60)
print("  CHURCHES BY STATE — SUMMARY")
print("=" * 60)
print("  %-20s %s" % ("State", "Count"))
print("  " + "-" * 30)
for state in sorted(by_state.keys(), key=lambda s: -len(by_state[s])):
    print("  %-20s %d" % (state, len(by_state[state])))
print("  " + "-" * 30)
print("  %-20s %d" % ("Total with state", sum(state_counts.values())))
print("  %-20s %d" % ("No address data", len(no_state)))
print("  %-20s %d" % ("Grand total", len(contacts)))

# Generate a consolidated report
report_path = os.path.join(OUT_DIR, "README.md")
with open(report_path, "w") as f:
    f.write("# Church Listings by State\n\n")
    f.write("Generated from church_contacts.csv\n\n")
    f.write("| State | Count | File |\n")
    f.write("|-------|-------|------|\n")
    for state in sorted(by_state.keys(), key=lambda s: -len(by_state[s])):
        f.write("| %s | %d | churches_%s.csv |\n" % (state, len(by_state[state]), state))
    f.write("| No state | %d | churches_NO_STATE.csv |\n" % len(no_state))

print("\n📁 Output: %s" % OUT_DIR)
print("📄 Report: %s" % report_path)
