"""Check existing BigQuery setup for WOF ingestion planning."""
import google.auth
from google.cloud import bigquery

c, _ = google.auth.default()
if hasattr(c, "with_quota_project"):
    c = c.with_quota_project("american-rel-infra")
bq = bigquery.Client(project="american-rel-infra", location="US", credentials=c)

# List existing datasets
print("=== BigQuery Datasets in american-rel-infra ===")
for ds in bq.list_datasets():
    print(f"  {ds.dataset_id}")

# Check churches table schema
print("\n=== Churches Table Schema (first 20 cols) ===")
table = bq.get_table("american-rel-infra.American_Religious_Infrastructure.churches")
print(f"Rows: {table.num_rows:,}")
print(f"Total columns: {len(table.schema)}")
print(f"{'Name':30s} {'Type':12s} {'Mode'}")
print("-"*55)
for field in table.schema[:25]:
    print(f"{field.name:30s} {field.field_type:12s} {field.mode}")
print("...")
for field in table.schema[25:]:
    print(f"{field.name:30s} {field.field_type:12s} {field.mode}")
