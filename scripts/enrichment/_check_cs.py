"""Check First Church of Christ, Scientist property records."""
import json

with open(r'E:\grid\data\boston_property_records.json') as f:
    props = json.load(f)

# Find all records mentioning CHRIST SCIENTIST, FALMOUTH, or MASSACHUSETTS AV near there
for p in props:
    owner = (p.get('OWNER') or '').upper()
    st_name = (p.get('ST_NAME') or '').upper()
    st_num = p.get('ST_NUM') or ''
    pid = p.get('PID')
    
    if 'CHRIST SCIENTIST' in owner or 'FALMOUTH' in st_name:
        print(f"PID={pid:>12}  {p.get('LUC')}  {p.get('LU_DESC'):30s}  {st_num:6s} {st_name:25s}  ${p.get('TOTAL_VALUE'):>12}  {p.get('OWNER')[:60]}")

# Also check if 93 Falmouth exists
print("\n--- Any record at 93 Falmouth? ---")
for p in props:
    if p.get('ST_NUM') == '93' and 'FALMOUTH' in (p.get('ST_NAME') or '').upper():
        print(f"PID={p.get('PID')}: {p.get('OWNER')} | {p.get('LU_DESC')}")

# Check the 204 Massachusetts Ave record
print("\n--- 204 Massachusetts Ave record ---")
for p in props:
    if p.get('PID') == '0401185000':
        for k, v in p.items():
            print(f"  {k}: {v}")
