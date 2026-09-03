"""Show all FEMA NRI field names to pick the useful subset."""
import urllib.request, json

url = 'https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Census_Tracts/FeatureServer/0?f=json'
req = urllib.request.Request(url, headers={'User-Agent':'GRID/1.0'})
r = urllib.request.urlopen(req, timeout=15)
d = json.loads(r.read())

fields = d.get('fields', [])
print(f"Total fields: {len(fields)}")
print()

# Categorize fields
risk_fields = []
rating_fields = []
eal_fields = []
sovi_fields = []
resl_fields = []
geo_fields = []
hazard_fields = []
other = []

for f in fields:
    name = f['name']
    if name in ('OBJECTID','NRI_ID','STATE','STATEABBRV','STATEFIPS','COUNTY','COUNTYTYPE','COUNTYFIPS','STCOFIPS','TRACT'):
        geo_fields.append(name)
    elif 'RISK_SCORE' in name or 'RISK_RATNG' in name or name == 'RISK_SCORE':
        risk_fields.append(name)
    elif 'EAL_' in name or name == 'EAL_SCORE':
        eal_fields.append(name)
    elif 'SOVI_' in name or name == 'SOVI_SCORE':
        sovi_fields.append(name)
    elif 'RESL_' in name or name == 'RESL_SCORE':
        resl_fields.append(name)
    elif '_RISKS' in name:
        hazard_fields.append(name)
    elif '_RATNG' in name or 'RATING' in name:
        rating_fields.append(name)
    else:
        other.append(name)

print(f"Geography: {len(geo_fields)}")
for n in geo_fields: print(f"  {n}")
print(f"\nRisk Scores: {len(risk_fields)}")
for n in risk_fields: print(f"  {n}")
print(f"\nEAL Scores: {len(eal_fields)}")
for n in eal_fields: print(f"  {n}")
print(f"\nSOVI: {len(sovi_fields)}")
for n in sovi_fields: print(f"  {n}")
print(f"\nRESL: {len(resl_fields)}")
for n in resl_fields: print(f"  {n}")
print(f"\nHazard Risk Scores (_RISKS): {len(hazard_fields)}")
for n in hazard_fields: print(f"  {n}")
print(f"\nRatings (_RATNG): {len(rating_fields)}")
for n in rating_fields[:10]: print(f"  {n}")
print(f"  ... and {len(rating_fields)-10} more")
print(f"\nOther: {len(other)}")
for n in other: print(f"  {n}")
