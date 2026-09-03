#!/usr/bin/env python3
"""
Master orchestrator for Catholic Directory imports.

Builds the storage database and imports the first (1865) and last (2021)
Catholic directories fully — every parish, cathedral, deanery, mission,
school, cemetery, hospital, convent, and clergy assignment.

Usage:
    python scripts/ingest/_import_catholic_dir_full.py                  # Full pipeline
    python scripts/ingest/_import_catholic_dir_full.py --build-only     # Just build DB
    python scripts/ingest/_import_catholic_dir_full.py --2021-only      # Just 2021
    python scripts/ingest/_import_catholic_dir_full.py --1865-only      # Just 1865
    python scripts/ingest/_import_catholic_dir_full.py --dry-run        # Preview all
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path("E:/grid/scripts/ingest")


def run_step(description, args):
    """Run a sub-script and check for errors."""
    print(f"\n{'='*60}")
    print(f"▶ {description}")
    print(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, "-u", str(args[0])] + args[1:],
        cwd="E:/grid",
    )
    if result.returncode != 0:
        print(f"❌ Step failed with code {result.returncode}")
        return False
    return True


def main():
    import argparse
    p = argparse.ArgumentParser(
        description="Full Catholic Directory import pipeline (1865 + 2021)"
    )
    p.add_argument("--build-only", action="store_true", help="Only build/verify DB schema")
    p.add_argument("--2021-only", action="store_true", help="Only import 2021")
    p.add_argument("--1865-only", action="store_true", help="Only import 1865")
    p.add_argument("--dry-run", action="store_true", help="Preview all imports, no writes")
    p.add_argument("--rebuild-db", action="store_true", help="Drop & recreate DB first")
    args = p.parse_args()

    all_steps = not (args.build_only or args.__dict__.get("2021_only") or args.__dict__.get("1865_only"))
    do_2021 = all_steps or args.__dict__.get("2021_only")
    do_1865 = all_steps or args.__dict__.get("1865_only")

    dry_flag = ["--dry-run"] if args.dry_run else []
    rebuild_flag = ["--rebuild"] if args.rebuild_db else []

    # Step 1: Build DB
    if not run_step("Build Catholic Directory storage database", [
        SCRIPTS_DIR / "_build_catholic_dir_db.py",
    ] + rebuild_flag):
        return

    if args.build_only:
        print("\n✅ Database built. Ready for import.")
        return

    # Step 2: Import 2021
    if do_2021:
        if not run_step("Import 2021 Catholic Directory", [
            SCRIPTS_DIR / "_import_catholic_dir_2021.py",
        ] + dry_flag):
            return

    # Step 3: Import 1865
    if do_1865:
        if not run_step("Import 1865 Catholic Directory (DeepSeek)", [
            SCRIPTS_DIR / "_import_catholic_dir_1865.py",
        ] + dry_flag):
            return

    # Summary
    print(f"\n{'='*60}")
    print("✅ Catholic Directory import pipeline complete!")
    print(f"{'='*60}")
    print(f"  Database: E:/grid/data/catholic_directory.db")
    print(f"\nQuery examples:")
    print(f"  sqlite3 E:/grid/data/catholic_directory.db")
    print(f"  SELECT directory_year, COUNT(*) FROM dir_entries GROUP BY directory_year;")
    print(f"  SELECT entity_type, COUNT(*) FROM dir_entries GROUP BY entity_type ORDER BY 2 DESC;")
    print(f"  SELECT * FROM vw_diocese_summary ORDER BY total_entries DESC LIMIT 10;")


if __name__ == "__main__":
    main()
