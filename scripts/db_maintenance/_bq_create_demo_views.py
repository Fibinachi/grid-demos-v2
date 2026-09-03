"""Create BQ demo views for Data Axle: Vermont, NWT, Tamil Nadu slices."""
from google.cloud import bigquery

client = bigquery.Client(project="american-rel-infra")
DATASET = "American_Religious_Infrastructure"
PROJECT = "american-rel-infra"

slices = {
    "demo_vermont": {
        "desc": "Vermont, USA — 1,947 worship sites. Rural New England: 96% Christian, Jewish enclaves, Buddhist centers. Good demo of US rural/suburban religious infrastructure with full enrichment.",
        "where": "state IN ('VT','Vermont') AND country='US'",
        "faiths": "Christian 1,865 · Jewish 33 · Other 25 · Buddhist 13 · Islam 8 · Hindu 2",
    },
    "demo_northwest_territories": {
        "desc": "Northwest Territories, Canada — 78 worship sites. Sparsest slice: subarctic Canada, indigenous communities, Christian missionary footprint. Shows GRID's coverage even in remote regions.",
        "where": "state IN ('NT','Northwest Territories') AND country='CA'",
        "faiths": "Christian 76 · Other 2",
    },
    "demo_tamil_nadu": {
        "desc": "Tamil Nadu, India — 28,356 worship sites. Our densest slice: majority Hindu with significant Christian & Muslim minorities. Shows GRID's international depth — temples, churches, mosques, Jain sites.",
        "where": "state='Tamil Nadu'",
        "faiths": "Hindu 21,804 · Christian 5,000 · Islam 1,370 · Other 76 · Jain 48 · Shinto 19 · Buddhist 18 · Catholic 11 · Sikh 10",
    },
}

for view_name, info in slices.items():
    view_id = f"{PROJECT}.{DATASET}.{view_name}"
    
    # Create enriched view with key columns
    sql = f"""
    CREATE OR REPLACE VIEW `{view_id}` AS
    SELECT 
        id, name, faith, tradition, landmark_type,
        address, city, state, zip, country,
        latitude, longitude,
        ntee_code, confidence_score,
        county, county_fips_5,
        taxonomy_id,
        continent, region_un, subregion
    FROM `{PROJECT}.{DATASET}.churches`
    WHERE {info['where']}
    """
    
    try:
        client.query(sql).result()
        # Get row count
        count = client.query(f"SELECT COUNT(*) as cnt FROM `{view_id}`").result()
        n = list(count)[0].cnt
        print(f"✅ {view_name}: {n:,} rows")
        print(f"   {info['desc']}")
        print(f"   Faiths: {info['faiths']}")
        print(f"   🔗 https://console.cloud.google.com/bigquery?project={PROJECT}&p={PROJECT}&d={DATASET}&t={view_name}&page=table")
        print()
    except Exception as e:
        print(f"❌ {view_name}: {e}")
        print()

print("Done! Share these links with Ben Weeks.")
