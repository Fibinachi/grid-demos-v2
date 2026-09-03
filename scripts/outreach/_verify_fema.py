"""Verify FEMA NRI import."""
import sqlite3
db = sqlite3.connect('churches.db')
db.row_factory = sqlite3.Row

print("FEMA NRI:")
r = db.execute("SELECT COUNT(*) as n, COUNT(DISTINCT TRACTFIPS) as t, COUNT(DISTINCT COUNTYFIPS) as c FROM fema_nri_tract").fetchone()
print(f"  {r['n']:,} rows, {r['t']:,} tracts, {r['c']:,} counties")

print("\nSample (first 3):")
for r in db.execute("SELECT TRACTFIPS, STATEABBRV, COUNTY, RISK_SCORE, RISK_RATNG, HRCN_RISKS, TRND_RISKS, WFIR_RISKS, POPULATION FROM fema_nri_tract LIMIT 3"):
    print(f"  {r['TRACTFIPS']} ({r['STATEABBRV']}, {r['COUNTY']}): RISK={r['RISK_SCORE']:.1f} {r['RISK_RATNG']} | Hurricane={r['HRCN_RISKS']:.1f} Tornado={r['TRND_RISKS']:.1f} Wildfire={r['WFIR_RISKS']:.1f} | Pop={r['POPULATION']:,.0f}")

print("\nVermont (first 5 tracts):")
for r in db.execute("SELECT TRACTFIPS, COUNTY, RISK_SCORE, RISK_RATNG, HRCN_RISKS, IFLD_RISKS, WNTW_RISKS, SOVI_SCORE FROM fema_nri_tract WHERE STATEABBRV='VT' LIMIT 5"):
    print(f"  {r['TRACTFIPS']} ({r['COUNTY']}): RISK={r['RISK_SCORE']:.1f} ({r['RISK_RATNG']}) | Hurricane={r['HRCN_RISKS']:.1f} InlandFlood={r['IFLD_RISKS']:.1f} WinterWx={r['WNTW_RISKS']:.1f} | SoVI={r['SOVI_SCORE']:.1f}")

print("\nHighest risk counties (top 5):")
for r in db.execute("SELECT COUNTY, STATEABBRV, ROUND(AVG(RISK_SCORE),1) as avg_risk FROM fema_nri_tract GROUP BY COUNTYFIPS, STATEABBRV ORDER BY avg_risk DESC LIMIT 5"):
    print(f"  {r['COUNTY']}, {r['STATEABBRV']}: avg RISK={r['avg_risk']}")

print("\nDB sizes:")
for table in ['fema_nri_tract','cdc_places_tract','fbi_ucr_crime','fbi_srs_state','fbi_nibrs_agency_2024','churches']:
    try:
        ct = db.execute(f"SELECT COUNT(*) as n FROM {table}").fetchone()['n']
        print(f"  {table}: {ct:,} rows")
    except:
        print(f"  {table}: MISSING")

# Check SRS state data
print("\nSRS State Crime (most recent year):")
for r in db.execute("SELECT year, state_abbr, population, violent_crime, homicide, property_crime FROM fbi_srs_state WHERE state_abbr='VT' ORDER BY year DESC LIMIT 3"):
    print(f"  {r['year']} VT: pop={r['population']:,}, violent={r['violent_crime']:,}, homicide={r['homicide']}, property={r['property_crime']:,}")

# Check NIBRS agency data
print("\nNIBRS Agency (VT sample):")
for r in db.execute("SELECT State, \"Agency Type\", \"Agency Name\", Population1, \"Total Offenses\" FROM fbi_nibrs_agency_2024 WHERE State='VERMONT' LIMIT 5"):
    print(f"  {r['Agency Name']} ({r['Agency Type']}): pop={r['Population1']:,}, offenses={r['Total Offenses']}")

db.close()
