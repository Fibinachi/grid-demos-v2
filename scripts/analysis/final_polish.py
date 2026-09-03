#!/usr/bin/env python3
"""Final polish - remove ministries, programs, and non-grant-makers from final list."""
import csv, os, re

base = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(base, 'theology_final_list.csv')) as f:
    rows = list(csv.DictReader(f))

total = len(rows)

# Patterns that indicate non-grant-making organizations
# These are ministries, programs, media, or educational entities
NON_GRANTMAKER_PATTERNS = [
    # Names that are ministries/programs, not foundations
    # (case insensitive, word-boundary safe)
    
    # "Theology [Something]" - ministries/programs
    r'\bTheology\s+(Cafe|Uncapped|Simple|In\s+Perspective|In\s+Focus|'
    r'Cultural\s+Center|Connect|Dot\s+Connector|Academy|Forum|'
    r'Incubator|Media|Productions|Publishing|Records|Retreat|'
    r'Matters|Mission\b(?!\s+Found)|Peace\b(?!\s+Found)|And\s+Peace|Impact)\b',
    
    # "[Something] Theology" where the name isn't a foundation
    r'^(Simple|Kitchen|Supernatural|Real\s+World)\s+Theology$',
    r'^Muncie\s+Theology\s+Institute$',
    r'^Reformed\s+Theology\s+Institute$',
    
    # "Evangelism [Something]" that's not a foundation
    r'^Evangelism\s+Theology\s+Forum$',
    
    # "Theological [Something]" that aren't foundations
    r'\bTheological\s+(Education\s+Initiative|Field\s+Education)\b',
    
    # Other non-grant-makers
    r'\bChinese\s+Theological\s+Education\s+Ministry\b',
]

# Remove entries matching non-grant-maker patterns
kept = []
removed = 0

for r in rows:
    name = r['NAME'].lower().strip()
    original_name = r['NAME']
    
    should_remove = False
    for pat in NON_GRANTMAKER_PATTERNS:
        if re.search(pat, original_name, re.IGNORECASE):
            should_remove = True
            break
    
    # Also check if it has "FOUNDATION" in the name - if so, keep it
    # (override the pattern match)
    if should_remove:
        if 'FOUNDATION' in original_name.upper():
            should_remove = False
    
    if should_remove:
        removed += 1
        continue
    
    kept.append(r)

print(f"Total before: {total}")
print(f"Removed non-grant-makers: {removed}")
print(f"Final count: {len(kept)}")

high = [r for r in kept if r['PRIORITY'] == 'HIGH']
med = [r for r in kept if r['PRIORITY'] == 'MEDIUM']
ready = [r for r in kept if r['HAS_EMAIL'] == 'YES']

print(f"HIGH: {len(high)}, MEDIUM: {len(med)}")
print(f"Ready to send: {len(ready)}")

# Save final
out_path = os.path.join(base, 'theology_final_list.csv')
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(kept)

# Ready-to-send
ready_path = os.path.join(base, 'theology_final_send.csv')
with open(ready_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader()
    w.writerows(ready)

print(f"\nSaved: {out_path}")
print(f"Ready to send: {ready_path}")

print(f"\n{'='*70}")
print(f"TOP 30 — FINAL THEOLOGY GRANT-MAKER LIST (Columbia, SC)")
print(f"{'='*70}")
for r in kept[:30]:
    email = '✓' if r['HAS_EMAIL'] == 'YES' else '✗'
    print(f"  [{r['PRIORITY']:6s}] [{r['THEOLOGY_SCORE']:>3s}] {email} {r['NAME'][:55]} ({r['CITY']}, {r['STATE']})")
