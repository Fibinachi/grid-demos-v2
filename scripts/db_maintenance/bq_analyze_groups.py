"""Categorize remaining BQ objects into logical groups for consolidation."""
from google.cloud import bigquery
from collections import defaultdict

client = bigquery.Client(project="american-rel-infra")
DATASET = "American_Religious_Infrastructure"

tables = list(client.list_tables(DATASET))

# Categorize
groups = defaultdict(list)
for t in tables:
    name = t.table_id
    tbl = client.get_table(f"{DATASET}.{name}")
    rows = tbl.num_rows or 0
    size = round(tbl.num_bytes / (1024*1024), 1) if tbl.num_bytes else 0
    entry = (name, rows, size, t.table_type)

    # Group by prefix pattern
    if name.startswith("div_"):
        groups["div_* (denominational division views)"].append(entry)
    elif name.startswith("church_census_") or name.startswith("church_election_"):
        groups["church_census/election_* (per-country enrichment)"].append(entry)
    elif name.startswith("church_"):
        groups["church_* (core data tables)"].append(entry)
    elif name.startswith("vw_"):
        groups["vw_* (utility views)"].append(entry)
    elif name.endswith("_hierarchy"):
        groups["*_hierarchy (denomination hierarchies)"].append(entry)
    elif name in ("anglican_hierarchy", "baptist_hierarchy", "catholic_hierarchy",
                  "chabad_hierarchy", "jw_hierarchy", "lds_hierarchy",
                  "lutheran_hierarchy", "moravian_hierarchy", "orthodox_hierarchy",
                  "sa_hierarchy", "ahmadiyya_hierarchy", "bahai_hierarchy"):
        groups["*_hierarchy (denomination hierarchies)"].append(entry)
    elif name.startswith("geonames"):
        groups["geonames_* (geographic reference)"].append(entry)
    elif name in ("rucc_codes", "county_acs", "county_fips_lookup", "taxonomy",
                  "sources", "zip_geo_lookup", "fcc_facilities", "emergency_stations"):
        groups["reference/lookup tables"].append(entry)
    elif name.startswith("broadcast"):
        groups["broadcast_* (broadcast media)"].append(entry)
    elif name.startswith("arda"):
        groups["arda_* (religious census data)"].append(entry)
    elif name.startswith("overture"):
        groups["overture_* (leftover staging)"].append(entry)
    elif name.startswith("election"):
        groups["election_* (election data)"].append(entry)
    elif name.startswith("cdc"):
        groups["cdc_* (health data)"].append(entry)
    elif name.startswith("source"):
        groups["source_* (source-specific imports)"].append(entry)
    elif name.startswith("tn_"):
        groups["tn_* (Tennessee parcels)"].append(entry)
    elif name.startswith("pss"):
        groups["pss_* (private schools)"].append(entry)
    elif name.startswith("eac"):
        groups["eac_* (election admin)"].append(entry)
    elif name.startswith("mapping"):
        groups["mapping_* (external datasets)"].append(entry)
    elif name.startswith("broadcast"):
        groups["broadcast_* (broadcast media)"].append(entry)
    elif name == "provenance_log":
        groups["provenance_log"].append(entry)
    else:
        groups["other"].append(entry)

print(f"{'='*80}")
print(f"  BQ Table Grouping Analysis — {len(tables)} objects remaining")
print(f"{'='*80}")

total_rows = 0
total_mb = 0

for group_name in sorted(groups.keys()):
    entries = groups[group_name]
    group_rows = sum(e[1] for e in entries)
    group_mb = sum(e[2] for e in entries)
    total_rows += group_rows
    total_mb += group_mb
    n_views = sum(1 for e in entries if e[3] == "VIEW")
    n_tables = len(entries) - n_views

    bar = "█" * min(30, int(group_mb / 50) + 1)
    icon = "👁️" if n_views == len(entries) else "📊" if n_tables == len(entries) else "🔀"

    print(f"\n  {icon} {group_name} ({n_tables}T + {n_views}V = {len(entries)} objects, {group_rows:,} rows, {group_mb:.0f} MB)")
    print(f"     {'─'*70}")

    # Show sample entries
    if len(entries) <= 15:
        for name, rows, size, ttype in sorted(entries, key=lambda x: -x[2]):
            tlabel = "V" if ttype == "VIEW" else "T"
            print(f"     {tlabel} {name:<45} {str(rows):>10}  {size:>8.1f} MB")
    else:
        # Show top 5 by size + count remaining
        sorted_entries = sorted(entries, key=lambda x: -x[2])
        for name, rows, size, ttype in sorted_entries[:5]:
            tlabel = "V" if ttype == "VIEW" else "T"
            print(f"     {tlabel} {name:<45} {str(rows):>10}  {size:>8.1f} MB")
        remaining = len(entries) - 5
        print(f"     ... and {remaining} more (smaller)")

# ── Consolidation recommendations ──
print(f"\n{'='*80}")
print(f"  🔧 CONSOLIDATION OPPORTUNITIES")
print(f"{'='*80}")

div_group = groups.get("div_* (denominational division views)", [])
if len(div_group) > 5:
    div_rows = sum(e[1] for e in div_group)
    div_mb = sum(e[2] for e in div_group)
    print(f"\n  1. div_* tables ({len(div_group)} tables, {div_rows:,} rows, {div_mb:.0f} MB)")
    print(f"     → Could merge into one 'church_division_stats' table with an extra")
    print(f"       'metric' column (age, education, income, poverty, etc.)")
    print(f"     → Or make them a single VIEW that UNIONs them")

census_group = groups.get("church_census/election_* (per-country enrichment)", [])
if len(census_group) > 10:
    census_rows = sum(e[1] for e in census_group)
    census_mb = sum(e[2] for e in census_group)
    print(f"\n  2. church_census/election_* tables ({len(census_group)} tables, {census_rows:,} rows, {census_mb:.0f} MB)")
    print(f"     → Could merge into one 'church_census_all' with a 'census_type' and 'country' column")
    print(f"     → Current catalog table (church_census_catalog) already tracks metadata")

hierarchy_group = groups.get("*_hierarchy (denomination hierarchies)", [])
if len(hierarchy_group) > 5:
    hier_rows = sum(e[1] for e in hierarchy_group)
    hier_mb = sum(e[2] for e in hierarchy_group)
    print(f"\n  3. *_hierarchy tables ({len(hierarchy_group)} tables, {hier_rows:,} rows, {hier_mb:.0f} MB)")
    print(f"     → Could merge into one 'church_hierarchy' with a 'denomination' column")
    print(f"     → BUT: each has different schema columns — consolidation may lose specificity")

# Div_* schema check
if div_group:
    print(f"\n  div_* schema sample (first 3):")
    for name, rows, size, ttype in sorted(div_group)[:3]:
        tbl = client.get_table(f"{DATASET}.{name}")
        cols = [f"{f.name}({f.field_type})" for f in tbl.schema[:6]]
        print(f"     {name}: {', '.join(cols)}")

print(f"\n  TOTAL: {len(tables)} objects, {total_rows:,} rows, {total_mb:.0f} MB")
