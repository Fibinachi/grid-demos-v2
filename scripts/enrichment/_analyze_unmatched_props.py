"""Categorize all 457 Boston property records by type and faith."""
import json, re
from collections import Counter, defaultdict

with open(r'E:\grid\data\boston_property_records.json') as f:
    props = json.load(f)

# Load our matched PIDs
import sys
sys.path.insert(0, r'E:\grid')
from gw_db import connect
conn = connect(r'E:\grid\churches.db')
matched_pids = set()
for row in conn.execute("SELECT boston_pid FROM churches WHERE boston_pid IS NOT NULL").fetchall():
    if row[0]:
        matched_pids.add(row[0])
conn.close()

print(f"Total property records: {len(props)}")
print(f"Already matched PIDs:   {len(matched_pids)}")
print(f"Unmatched:              {len(props) - len(matched_pids)}")

unmatched = [p for p in props if p.get('PID') not in matched_pids]

# Categorize by keywords in owner name + LU_DESC
def categorize(p):
    owner = (p.get('OWNER') or '').upper()
    desc = (p.get('LU_DESC') or '').upper()
    name = f"{owner} {desc}"
    
    # Cemetery
    if 'CEMETERY' in name or 'CEMETRY' in name or 'CEM' in name.split()[:3]:
        if 'CATH' in name or 'CATHOLIC' in name:
            return 'cemetery', 'Christian', 'Catholic'
        if 'JEWISH' in name or 'JESHURUN' in name or 'BNAI' in name or 'ISRAEL' in name or 'HEBREW' in name or 'SHALOM' in name:
            return 'cemetery', 'Judaism', None
        if 'MILITARY' in name or 'GOVERNMENT' in name or 'CITY' in name or 'STATE' in name:
            return 'cemetery', 'Secular', None
        return 'cemetery', 'Christian', None  # default cemetery
    
    # Hospital / Medical
    if 'HOSPITAL' in name or 'MEDICAL CENTER' in name or 'DEACONESS' in name or 'HEALTH' in name:
        if 'BETH ISRAEL' in name:
            return 'hospital', 'Judaism', None
        if 'CATHOLIC' in name or 'ST ' in owner or 'SAINT' in owner:
            return 'hospital', 'Christian', 'Catholic'
        return 'hospital', 'Christian', None
    
    # Church / religious building by LUC
    if p.get('LUC') == '970':
        # Try to determine denomination
        if 'MOSQUE' in name or 'ISLAMIC' in name or 'MUSLIM' in name:
            return 'church', 'Islam', None
        if 'SYNAGOGUE' in name or 'TEMPLE' in name and 'BAPTIST' not in name and 'CHURCH' not in name:
            return 'synagogue', 'Judaism', None
        if 'BAPTIST' in name:
            return 'church', 'Christian', 'Baptist'
        if 'CATHOLIC' in name or 'ROMAN CATH' in name or 'ARCHDIOCES' in name or 'ST ' in owner[:5] or 'SAINT ' in owner[:7] or 'PARISH' in name or 'CHURCH OF THE' in name:
            return 'church', 'Christian', 'Catholic'
        if 'METHODIST' in name or 'UMC' in name:
            return 'church', 'Christian', 'Methodist'
        if 'LUTHERAN' in name:
            return 'church', 'Christian', 'Lutheran'
        if 'EPISCOPAL' in name:
            return 'church', 'Christian', 'Episcopal'
        if 'ORTHODOX' in name:
            return 'church', 'Christian', 'Orthodox'
        if 'PENTECOSTAL' in name or 'APOSTOLIC' in name or 'PENT APSTL' in name:
            return 'church', 'Christian', 'Pentecostal'
        if 'EVANGELICAL' in name or 'EVANGELICAL' in name:
            return 'church', 'Christian', 'Evangelical'
        if 'CONGREGATIONAL' in name or 'UCC' in name:
            return 'church', 'Christian', 'Congregational'
        if 'PRESBYTERIAN' in name:
            return 'church', 'Christian', 'Presbyterian'
        if 'CHURCH OF GOD' in name or 'CHURCH OF CHRIST' in name:
            return 'church', 'Christian', 'Church of God/Christ'
        if 'CHRISTIAN' in name or 'CHURCH' in name:
            return 'church', 'Christian', None
        if 'TEMPLE' in name:
            return 'church', 'Judaism', None  # Conservative guess
        return 'church', 'Christian', None  # default church
    
    # Religious Organization by LUC
    if p.get('LUC') == '906':
        if 'CEMETERY' in name or 'CEM' in name.split()[:3]:
            if 'CATH' in name:
                return 'cemetery', 'Christian', 'Catholic'
            return 'cemetery', 'Christian', None
        if 'HOSPITAL' in name or 'MEDICAL' in name or 'HEALTH' in name or 'DEACONESS' in name:
            if 'BETH ISRAEL' in name:
                return 'hospital', 'Judaism', None
            return 'hospital', 'Christian', None
        if 'HOUSING' in name or 'APARTMENT' in name or 'HOMES' in name or 'SHELTER' in name or 'RESIDENCE' in name or 'RETIREMENT' in name:
            return 'housing', 'Christian', None
        if 'SCHOOL' in name or 'ACADEMY' in name or 'EDUCATION' in name or 'LEARNING' in name or 'COLLEGE' in name or 'UNIVERSITY' in name or 'YOUTH' in name or 'CAMP' in name:
            return 'school', 'Christian', None
        if 'SOCIAL' in name or 'SERVICES' in name or 'CHARITIES' in name or 'OUTREACH' in name or 'COMMUNITY' in name or 'CENTER' in name:
            return 'community_center', 'Christian', None
        if 'CONVENT' in name or 'MONASTERY' in name or 'RECTORY' in name or 'PRIORY' in name:
            return 'religious_house', 'Christian', 'Catholic'
        if 'DIOCESAN' in name or 'ARCHDIOCES' in name or 'PASTORAL' in name or 'CATHOLIC' in name:
            return 'administrative', 'Christian', 'Catholic'
        if 'MOSQUE' in name or 'ISLAMIC' in name:
            return 'church', 'Islam', None
        if 'BAPTIST' in name:
            return 'administrative', 'Christian', 'Baptist'
        # Default for 906: religious organization, likely Christian
        return 'religious_org', 'Christian', None
    
    return 'unknown', None, None

cats = defaultdict(lambda: defaultdict(int))
faith_counts = Counter()
type_counts = Counter()

for p in unmatched:
    ptype, faith, denom = categorize(p)
    cats[faith][ptype] += 1
    faith_counts[faith] += 1
    type_counts[ptype] += 1

print(f"\n{'='*60}")
print(f"UNMATCHED PROPERTIES — By Type")
print(f"{'='*60}")
for ptype, cnt in type_counts.most_common():
    print(f"  {ptype}: {cnt}")

print(f"\n{'='*60}")
print(f"UNMATCHED PROPERTIES — By Faith")
print(f"{'='*60}")
for faith, cnt in faith_counts.most_common():
    print(f"  {faith}: {cnt}")

print(f"\n{'='*60}")
print(f"DETAILED BREAKDOWN")
print(f"{'='*60}")
for faith in sorted(cats.keys()):
    print(f"\n  {faith}:")
    for ptype, cnt in sorted(cats[faith].items(), key=lambda x: -x[1]):
        print(f"    {ptype}: {cnt}")

# List top properties by value
print(f"\n{'='*60}")
print(f"HIGHEST VALUE UNMATCHED PROPERTIES")
print(f"{'='*60}")
def parse_val(v):
    if not v: return 0
    return int(v.replace(',', '').replace('$', '').strip() or 0)

sorted_unmatched = sorted(unmatched, key=lambda p: -parse_val(p.get('TOTAL_VALUE')))
for p in sorted_unmatched[:20]:
    val = p.get('TOTAL_VALUE') or '$0'
    area = p.get('GROSS_AREA') or '?'
    ptype, faith, denom = categorize(p)
    owner = (p.get('OWNER') or '')[:50]
    addr = f"{p.get('ST_NUM') or ''} {p.get('ST_NAME') or ''}"
    print(f"  {val:>15}  {area:>8}sf  [{faith:12s}] [{ptype:16s}] {owner}")
    print(f"                    {addr}  PID={p.get('PID')}")

# List all cemeteries
print(f"\n{'='*60}")
print(f"CEMETERIES")
print(f"{'='*60}")
cemeteries = [p for p in unmatched if categorize(p)[0] == 'cemetery']
for p in sorted(cemeteries, key=lambda x: x.get('OWNER', '')):
    val = p.get('TOTAL_VALUE') or '$0'
    owner = (p.get('OWNER') or '')[:60]
    _, faith, denom = categorize(p)
    print(f"  PID={p.get('PID'):>12}  {val:>12}  [{faith:12s}] {owner}")

# List all Jewish properties
print(f"\n{'='*60}")
print(f"JEWISH PROPERTIES")
print(f"{'='*60}")
jewish = [p for p in unmatched if categorize(p)[1] == 'Judaism']
for p in sorted(jewish, key=lambda x: x.get('OWNER', '')):
    val = p.get('TOTAL_VALUE') or '$0'
    owner = (p.get('OWNER') or '')[:60]
    ptype, _, denom = categorize(p)
    print(f"  PID={p.get('PID'):>12}  {val:>12}  [{ptype:16s}] {owner}")

# List all Islamic properties
print(f"\n{'='*60}")
print(f"ISLAMIC PROPERTIES")
print(f"{'='*60}")
islamic = [p for p in unmatched if categorize(p)[1] == 'Islam']
for p in sorted(islamic, key=lambda x: x.get('OWNER', '')):
    val = p.get('TOTAL_VALUE') or '$0'
    owner = (p.get('OWNER') or '')[:60]
    print(f"  PID={p.get('PID'):>12}  {val:>12}  {owner}")

# Summary stats for all 457 records
print(f"\n{'='*60}")
print(f"ALL 457 RECORDS — Value Summary")
print(f"{'='*60}")
all_vals = [parse_val(p.get('TOTAL_VALUE')) for p in props]
all_areas = []
for p in props:
    a = p.get('GROSS_AREA')
    if a:
        try:
            all_areas.append(int(a.replace(',', '')))
        except:
            pass

print(f"  Total assessed value: ${sum(all_vals):,}")
print(f"  Mean value: ${sum(all_vals)//len(all_vals):,}")
print(f"  Median value: ${sorted(all_vals)[len(all_vals)//2]:,}")
print(f"  Properties with area data: {len(all_areas)}/{len(props)}")
if all_areas:
    print(f"  Mean gross area: {sum(all_areas)//len(all_areas):,} sf")
