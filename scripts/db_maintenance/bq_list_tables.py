"""List all BQ tables and views in the GRID dataset."""
from google.cloud import bigquery

client = bigquery.Client(project="american-rel-infra")
dataset = "American_Religious_Infrastructure"

tables = list(client.list_tables(dataset))
print(f"\n{'='*70}")
print(f"  BigQuery: {dataset}")
print(f"  Total objects: {len(tables)}")
print(f"{'='*70}")

# Separate tables and views
regular = []
views = []
for t in tables:
    tbl = client.get_table(f"{dataset}.{t.table_id}")
    row_count = tbl.num_rows if hasattr(tbl, 'num_rows') and tbl.num_rows else "?"
    size_mb = round(tbl.num_bytes / (1024*1024), 1) if hasattr(tbl, 'num_bytes') and tbl.num_bytes else "?"
    info = (t.table_id, t.table_type, row_count, size_mb, tbl.created)
    if t.table_type == "VIEW":
        views.append(info)
    else:
        regular.append(info)

print("\n📊 REGULAR TABLES:")
print(f"{'Name':<45} {'Rows':>10} {'Size(MB)':>10} {'Created'}")
print("-" * 85)
for name, ttype, rows, size, created in sorted(regular, key=lambda x: x[0]):
    print(f"  {name:<43} {str(rows):>10} {str(size):>10} {str(created)[:19]}")

print(f"\n👁️ VIEWS:")
print(f"{'Name':<45} {'Rows':>10} {'Created'}")
print("-" * 85)
for name, ttype, rows, size, created in sorted(views, key=lambda x: x[0]):
    print(f"  {name:<43} {str(rows):>10} {str(created)[:19]}")

# Flag potential cleanup candidates
print(f"\n🔍 POTENTIAL CLEANUP:")
print("-" * 70)
demo_views = [v for v in views if "demo" in v[0].lower()]
stale = [t for t in regular if "1865" in t[0] or "old" in t[0].lower() or "backup" in t[0].lower() or "temp" in t[0].lower() or "test" in t[0].lower()]

if demo_views:
    print(f"  Demo views ({len(demo_views)}):")
    for v in demo_views:
        print(f"    🗑️  {v[0]}")

if stale:
    print(f"  Stale/temp tables ({len(stale)}):")
    for v in stale:
        print(f"    🗑️  {v[0]}")

if not demo_views and not stale:
    print("  No obvious cleanup candidates found.")

print(f"\n  Total objects: {len(tables)} (tables: {len(regular)}, views: {len(views)})")
