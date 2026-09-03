"""Check what property PID=0306499000 is."""
import json
with open(r'E:\grid\data\boston_property_records.json') as f:
    props = json.load(f)

for p in props:
    if p.get('PID') == '0306499000':
        print(f"PID={p['PID']}: {p.get('OWNER')}")
        print(f"  Address: {p.get('ST_NUM')} {p.get('ST_NAME')}, {p.get('CITY')}")
        print(f"  LUC={p.get('LUC')} LU_DESC={p.get('LU_DESC')}")
        print(f"  Total Value: {p.get('TOTAL_VALUE')}")
        print(f"  Gross Area: {p.get('GROSS_AREA')}")
        break
else:
    print("PID=0306499000 not found in property records")
