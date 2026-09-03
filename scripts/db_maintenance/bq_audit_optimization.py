"""Audit BQ table optimization — partitioning, clustering, types."""
from google.cloud import bigquery

client = bigquery.Client(project="american-rel-infra")
DATASET = "American_Religious_Infrastructure"

# Key tables to audit
KEY_TABLES = [
    "churches", "church_enrichment", "church_external_ids", "church_sources",
    "church_contact_values", "church_metrics", "enrichment_change_log",
    "church_addresses", "geonames", "geonames_places", "geonames_postal",
    "address_components", "cdc_places_tract",
]

print(f"{'='*80}")
print(f"  BQ Optimization Audit — {DATASET}")
print(f"{'='*80}")

issues = []

for name in KEY_TABLES:
    full = f"{DATASET}.{name}"
    try:
        tbl = client.get_table(full)
    except:
        print(f"\n  ⚠️  {name} — NOT FOUND")
        continue

    size_mb = round(tbl.num_bytes / (1024*1024), 1) if tbl.num_bytes else 0
    row_count = tbl.num_rows if tbl.num_rows else 0

    # Schema type audit
    col_types = {}
    type_counts = {}
    for field in tbl.schema:
        t = field.field_type
        type_counts[t] = type_counts.get(t, 0) + 1
        col_types[field.name] = t

    # Check partitioning
    is_partitioned = tbl.time_partitioning is not None
    partition_field = tbl.time_partitioning.field if is_partitioned else None

    # Check clustering
    is_clustered = tbl.clustering_fields is not None
    cluster_cols = tbl.clustering_fields if is_clustered else []

    print(f"\n{'─'*60}")
    print(f"  📊 {name}")
    print(f"     Rows: {row_count:,}  |  Size: {size_mb:.1f} MB  |  Cols: {len(tbl.schema)}")
    print(f"     Types: {', '.join(f'{k}:{v}' for k,v in sorted(type_counts.items()))}")
    print(f"     Partitioned: {'✅' if is_partitioned else '❌'} {'(' + partition_field + ')' if partition_field else ''}")
    print(f"     Clustered:   {'✅' if is_clustered else '❌'} {'[' + ', '.join(cluster_cols) + ']' if cluster_cols else ''}")

    # Flag issues
    if not is_partitioned and size_mb > 100:
        issues.append(f"{name}: {size_mb:.0f} MB unpartitioned")
    if not is_clustered and row_count > 500_000:
        issues.append(f"{name}: {row_count:,} rows unclustered")

    # STRING-only audit - flag numeric-looking columns stored as STRING
    string_cols = [c for c, t in col_types.items() if t == "STRING"]
    numeric_looking = [c for c in string_cols if any(kw in c.lower() for kw in 
                      ["id", "count", "num", "year", "pop", "size", "sqft", "lat", "lon", 
                       "latitude", "longitude", "fips", "zip", "code", "score", "amount",
                       "value", "price", "rate", "pct", "rank"])]
    if numeric_looking and row_count > 100_000:
        # Only flag for large tables
        sample = numeric_looking[:8]
        issues.append(f"{name}: {len(numeric_looking)} numeric-like columns as STRING (e.g. {', '.join(sample)})")

print(f"\n{'='*80}")
print(f"  🔍 ISSUES FOUND ({len(issues)})")
print(f"{'='*80}")
if issues:
    for i in issues:
        print(f"  ⚠️  {i}")
else:
    print("  ✅ No issues found!")

# ── Check for tables never queried ──
print(f"\n{'='*80}")
print(f"  📅 Last modified dates (staleness check)")
print(f"{'='*80}")
all_tables = sorted([t for t in client.list_tables(DATASET) 
                     if t.table_type != "VIEW"],
                    key=lambda t: t.created or "", reverse=True)
for t in all_tables[:10]:
    print(f"  {t.table_id:<45} created: {str(t.created)[:19]}")
