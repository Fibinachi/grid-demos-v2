"""
Import FBI crime data from manually downloaded files:
  1. estimated_crimes_1979_2024.csv — SRS state-level (1979-2024)
  2. NIBRS_United_States_Offense_Type_by_Agency_2024.xlsx — NIBRS agency-level (2024)

Usage: python scripts/enrichment/import_fbi_crime.py
"""
import csv, sqlite3, time, openpyxl
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT / "churches.db"

def progress_bar(i, total, start, label=""):
    if total == 0: return
    elapsed = max(time.time() - start, 0.001)
    rate = (i + 1) / elapsed
    eta = (total - i - 1) / rate / 60 if rate > 0 else 0
    pct = (i + 1) / total * 100
    filled = int(30 * (i + 1) / total)
    bar = chr(0x2588) * filled + chr(0x2591) * (30 - filled)
    print(f"\r    {bar} {i+1:,}/{total:,} ({pct:.0f}%) {rate:.0f}/s ETA={eta:.0f}m {label}", end="", flush=True)

def import_srs_state(db):
    """Import estimated_crimes_1979_2024.csv — state-level SRS data."""
    csv_path = PROJECT / "estimated_crimes_1979_2024.csv"
    if not csv_path.exists():
        print("  estimated_crimes_1979_2024.csv not found — skipping")
        return 0

    print("\n  Importing SRS state-level crime data (1979-2024)...")

    # Create table
    db.execute("DROP TABLE IF EXISTS fbi_srs_state")
    db.execute("""
        CREATE TABLE fbi_srs_state (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER,
            state_abbr TEXT,
            state_name TEXT,
            population INTEGER,
            violent_crime INTEGER,
            homicide INTEGER,
            rape_legacy INTEGER,
            rape_revised INTEGER,
            robbery INTEGER,
            aggravated_assault INTEGER,
            property_crime INTEGER,
            burglary INTEGER,
            larceny INTEGER,
            motor_vehicle_theft INTEGER,
            caveats TEXT
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_srs_state_year ON fbi_srs_state(state_abbr, year)")

    rows = []
    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rows.append((
                    int(row.get('year', 0) or 0),
                    row.get('state_abbr', ''),
                    row.get('state_name', ''),
                    int(float(row.get('population', 0) or 0)),
                    int(float(row.get('violent_crime', 0) or 0)),
                    int(float(row.get('homicide', 0) or 0)),
                    int(float(row.get('rape_legacy', 0) or 0)),
                    int(float(row.get('rape_revised', 0) or 0)),
                    int(float(row.get('robbery', 0) or 0)),
                    int(float(row.get('aggravated_assault', 0) or 0)),
                    int(float(row.get('property_crime', 0) or 0)),
                    int(float(row.get('burglary', 0) or 0)),
                    int(float(row.get('larceny', 0) or 0)),
                    int(float(row.get('motor_vehicle_theft', 0) or 0)),
                    row.get('caveats', ''),
                ))
            except (ValueError, TypeError):
                pass

    db.executemany("""
        INSERT INTO fbi_srs_state (year, state_abbr, state_name, population,
            violent_crime, homicide, rape_legacy, rape_revised, robbery, aggravated_assault,
            property_crime, burglary, larceny, motor_vehicle_theft, caveats)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    db.commit()

    count = db.execute("SELECT COUNT(*) FROM fbi_srs_state").fetchone()[0]
    years = db.execute("SELECT MIN(year), MAX(year) FROM fbi_srs_state").fetchone()
    states = db.execute("SELECT COUNT(DISTINCT state_abbr) FROM fbi_srs_state WHERE state_abbr != ''").fetchone()[0]
    print(f"    {count:,} rows | {states} states | {years[0]}-{years[1]}")

    return count

def import_nibrs_agency(db):
    """Import NIBRS agency-level 2024 data from XLSX."""
    xlsx_path = PROJECT / "data/geo_reference/NIBRS_United_States_Offense_Type_by_Agency_2024.xlsx"
    if not xlsx_path.exists():
        print("  NIBRS XLSX not found — skipping")
        return 0

    print("\n  Importing NIBRS agency-level data (2024)...")

    wb = openpyxl.load_workbook(str(xlsx_path), read_only=True)
    ws = wb.active

    # This XLSX has complex merged headers. Row 5 has main categories, row 6 has sub-categories.
    # Build a combined header from rows 5+6.
    row5 = [c.value for c in next(ws.iter_rows(min_row=5, max_row=5))]
    row6 = [c.value for c in next(ws.iter_rows(min_row=6, max_row=6))]

    headers = []
    for i in range(len(row5)):
        h5 = (row5[i] or '').replace('\n', ' ').strip()
        h6 = (row6[i] or '').replace('\n', ' ').strip()
        if h5 and h6 and h5 != h6:
            headers.append(f"{h5}_{h6}")
        elif h5:
            headers.append(h5)
        elif h6:
            headers.append(h6)
        else:
            headers.append(f"col_{i}")

    print(f"    {len(headers)} columns: {headers[:8]}...")

    # Create table dynamically
    col_defs = ",\n    ".join(f'"{h}" REAL' if any(kw in h.lower() for kw in ('population','offense','crime','assault','homicide','robbery','burglary','larceny','theft','arson','count','drug','weapon','fraud','sex','kidnap'))
              else f'"{h}" TEXT' for h in headers)

    db.execute("DROP TABLE IF EXISTS fbi_nibrs_agency_2024")
    db.execute(f'CREATE TABLE fbi_nibrs_agency_2024 (id INTEGER PRIMARY KEY AUTOINCREMENT, {col_defs})')
    db.execute("CREATE INDEX IF NOT EXISTS idx_nibrs_state ON fbi_nibrs_agency_2024(State)")

    # Read data rows (start at row 7)
    inserted = 0
    start_time = time.time()
    batch = []

    for row in ws.iter_rows(min_row=7, values_only=True):
        if not row[0]:  # Skip empty rows
            continue
        values = list(row)
        # Pad to match header count
        while len(values) < len(headers):
            values.append(None)
        batch.append(tuple(values[:len(headers)]))

        if len(batch) >= 500:
            ph = ",".join(["?"] * len(headers))
            cols = ",".join(f'"{h}"' for h in headers)
            db.executemany(f"INSERT INTO fbi_nibrs_agency_2024 ({cols}) VALUES ({ph})", batch)
            db.commit()
            inserted += len(batch)
            batch = []
            progress_bar(inserted, 12441, start_time, f"{inserted:,} agencies")

    if batch:
        ph = ",".join(["?"] * len(headers))
        cols = ",".join(f'"{h}"' for h in headers)
        db.executemany(f"INSERT INTO fbi_nibrs_agency_2024 ({cols}) VALUES ({ph})", batch)
        db.commit()
        inserted += len(batch)

    wb.close()

    states = db.execute("SELECT COUNT(DISTINCT State) FROM fbi_nibrs_agency_2024").fetchone()[0]
    print(f"\n    {inserted:,} agencies across {states} states")
    return inserted

def main():
    db = sqlite3.connect(str(DB_PATH), timeout=120)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=OFF")

    print("=" * 60)
    print("  FBI CRIME DATA IMPORT")
    print("=" * 60)

    import_srs_state(db)
    import_nibrs_agency(db)

    # Summary
    print("\n" + "=" * 60)
    print("  CRIME DATA SUMMARY")
    print("=" * 60)
    for t in ['fbi_srs_state', 'fbi_nibrs_agency_2024', 'fema_nri_tract', 'cdc_places_tract']:
        cur = db.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{t}'")
        if cur.fetchone():
            cnt = db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"  {t}: {cnt:,} rows")

    # Quick VT stats from SRS
    print("\n  Vermont crime (SRS 2024):")
    vt = db.execute("""
        SELECT * FROM fbi_srs_state WHERE state_abbr='VT' AND year=2024
    """).fetchone()
    if vt:
        pop = vt['population']
        print(f"    Population: {pop:,}")
        print(f"    Violent: {vt['violent_crime']:,} ({1000*vt['violent_crime']//pop:.1f}/1K)")
        print(f"    Property: {vt['property_crime']:,} ({1000*vt['property_crime']//pop:.1f}/1K)")
        print(f"    Homicide: {vt['homicide']}")

    db.close()
    print("\n✅ Done!")

if __name__ == "__main__":
    main()
