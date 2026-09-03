"""Clean up stale BQ tables and demo views."""
from google.cloud import bigquery

client = bigquery.Client(project="american-rel-infra")
DATASET = "American_Religious_Infrastructure"

# ── What to drop ──────────────────────────────────────────────────

DROP_LIST = [
    # Demo views (13)
    "demo_360753", "demo_371594", "demo_375140", "demo_378576",
    "demo_contact_enriched", "demo_global_top10", "demo_muslim_world",
    "demo_us_catholic", "demo_northwest_territories", "demo_tamil_nadu",
    "demo_vermont", "demo_vt_churches", "demo_vt_summary",

    # 1865 CD directory tables (6) — already in churches.db
    "cd1865_clergy_assignments", "cd1865_clergy_personnel",
    "cd1865_dir_bishops", "cd1865_dir_clergy",
    "cd1865_dir_entries", "cd1865_dir_provenance",

    # ACS staging (3)
    "_acs_temp", "_acs_data", "_acs_update",

    # FIPS backfill staging (2)
    "_fips_backfill_result", "_fips_backfill_staging",

    # MX admin staging (2)
    "_mx_admin_result", "_mx_admin_staging",

    # Overture staging (7) — data already merged into churches
    "overture_canada_new", "overture_canada_staging",
    "overture_churches_new", "overture_churches_staging",
    "overture_mexico_new", "overture_mexico_staging",
    "overture_holy_staging",  # 1.8 GB, 12M rows

    # Misc stale
    "ms_building_footprints",
]

# ── Execute ───────────────────────────────────────────────────────

import sys
dry_run = "--dry-run" in sys.argv

total_dropped = 0
total_mb = 0.0
errors = []

for name in DROP_LIST:
    full = f"{DATASET}.{name}"
    try:
        tbl = client.get_table(full)
        size_mb = round(tbl.num_bytes / (1024*1024), 1) if tbl.num_bytes else 0
        row_count = tbl.num_rows if tbl.num_rows else 0

        if dry_run:
            print(f"  [WOULD DROP] {name:<40} {str(row_count):>10} rows  {size_mb:>8} MB")
        else:
            client.delete_table(full)
            print(f"  [DROPPED] {name:<40} {str(row_count):>10} rows  {size_mb:>8} MB")

        total_dropped += 1
        total_mb += size_mb
    except Exception as e:
        msg = str(e)
        if "Not found" in msg or "404" in msg:
            print(f"  [SKIP] {name:<40} (not found)")
        else:
            print(f"  [ERROR] {name:<40} {msg[:80]}")
            errors.append((name, msg))

print(f"\n{'='*60}")
if dry_run:
    print(f"  DRY RUN — Would drop {total_dropped} objects ({total_mb:.0f} MB)")
else:
    print(f"  Dropped {total_dropped} objects ({total_mb:.0f} MB freed)")
if errors:
    print(f"  {len(errors)} errors")
print(f"{'='*60}")
