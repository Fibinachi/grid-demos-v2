"""
Reconstruct provenance_log entries from the churches.source field.
Generates a JSON file; use --apply to write to DB.

Usage:
    .venv\Scripts\python.exe _reconstruct_provenance.py          # generate JSON
    .venv\Scripts\python.exe _reconstruct_provenance.py --apply  # apply to DB
"""
import sqlite3, os, sys, json, time
from datetime import datetime, timezone
from collections import defaultdict

DRY_RUN = '--dry-run' in sys.argv
APPLY = '--apply' in sys.argv
OUTPUT_JSON = 'data/provenance_reconstructed.json'
DB = 'churches.db'

SOURCE_SCRIPT_MAP = {
    'irs': '_import_irs.py',
    'holy_sites_import': 'merge_holy_sites_into_churches',
    'holy_sites_enrichment': 'merge_holy_sites_into_churches',
    'overture_full': '_import_overture.py',
    'overture_discovery': '_import_overture.py',
    'overture_canada': '_import_overture.py',
    'overture_mexico': '_import_overture.py',
    'overture': '_import_overture.py',
    'churchunion_scraper': 'scripts/scrapers/churchunion_scraper.py',
    'cra_2018': 'import_cra_2018',
    'cra_2011': 'import_cra_2011',
    'sbc_directory': 'scripts/scrapers/sbc_scraper.py',
    'sbc_scrape': 'scripts/scrapers/sbc_scraper.py',
    'csv_import': 'csv_import',
    'catholic_diocese_scrape': 'scripts/scrapers/catholic_diocese_scrape.py',
    'masstimes_nationwide': 'scripts/scrapers/masstimes_scraper.py',
    'coc_21stcc': 'scripts/scrapers/coc_scraper.py',
    'contacts': 'contacts_import',
    'ag_directory': 'scripts/scrapers/ag_scraper.py',
    'cog_scraper': 'scripts/scrapers/cog_scraper.py',
    'cogic_scraper': 'scripts/scrapers/cogic_scraper.py',
    'pcusa_api': 'scripts/scrapers/pcusa_api.py',
    'umc_national': 'scripts/scrapers/umc_scraper.py',
    'umc_scrape': 'scripts/scrapers/umc_scraper.py',
    'lcms_scraper': 'scripts/scrapers/lcms_scraper.py',
    'ou_api': 'scripts/scrapers/ou_api.py',
    'fwb_scraper': 'scripts/scrapers/fwb_scraper.py',
    'cs_directory_scraper': 'scripts/scrapers/cs_scraper.py',
    'opc_scraper': 'scripts/scrapers/opc_scraper.py',
    'ame_district_scrape': 'scripts/scrapers/ame_scraper.py',
    'arp_scraper': 'scripts/scrapers/arp_scraper.py',
    'arp_scrape': 'scripts/scrapers/arp_scraper.py',
    'wesleyan_district_scraper': 'scripts/scrapers/wesleyan_scraper.py',
    'nbc_pdf_scrape': 'scripts/scrapers/nbc_scraper.py',
    'ipeds_2023': '_import_ipeds.py',
    'lds_scrape': 'scripts/scrapers/lds_scraper.py',
    'lds_temples': 'scrape_lds_temples.py',
    'diocese_sitemap': 'scripts/scrapers/diocese_sitemap.py',
    'diocese_directory': 'scripts/scrapers/diocese_directory.py',
    'la_masstimes_parishes': 'scripts/scrapers/la_masstimes.py',
    'la_catholic_schools': 'scripts/scrapers/la_catholic.py',
    'megachurch_scraper': 'scripts/scrapers/megachurch_scraper.py',
    'wikipedia_cathedrals': 'import_cathedrals.py',
    'wikipedia_country_lists': 'import_wiki_country_lists.py',
    'wikipedia_list': 'import_wiki_lists.py',
    'wikipedia_largest': 'import_wiki_largest.py',
    'wikipedia_tallest_crosses': 'import_tallest_crosses.py',
    'wikipedia_tallest_domes': 'import_naves_domes.py',
    'wikipedia_highest_naves': 'import_naves_domes.py',
    'wikipedia_evangelical': 'import_wiki_evangelical.py',
    'wikipedia_orthodox_largest': 'import_wiki_orthodox.py',
    'wikipedia_hindu_temples': 'import_wiki_hindu.py',
    'wikipedia_hindu_outside': 'import_wiki_hindu.py',
    'wikipedia_tallest': 'import_wiki_tallest.py',
    'master': 'master_import',
    'guess': 'guess',
    'manual_scrape_20260611': 'manual_scrape',
    'archden_statement': 'scripts/scrapers/archden.py',
    'newspring_scraper': 'scripts/scrapers/newspring.py',
    'seacoast_scraper': 'scripts/scrapers/seacoast.py',
    'txbaptists_org': 'scripts/scrapers/txbaptists.py',
    'ncbaptist_audit': 'scripts/scrapers/ncbaptist.py',
    'cumberland_scrape': 'scripts/scrapers/cumberland.py',
    'bridgeport_guilds': 'scripts/scrapers/bridgeport.py',
}

print("=== Step 1: Parse source chains ===")
conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=30)
c = conn.cursor()

c.execute("""
    SELECT source, COUNT(*) as n, MIN(osm_timestamp), MAX(osm_timestamp)
    FROM churches WHERE source IS NOT NULL AND source != ''
    GROUP BY source ORDER BY n DESC
""")

source_chains = []
for src, n, min_osm, max_osm in c.fetchall():
    parts = src.split('+')
    base_ops = [b.strip() for b in parts[0].split(',') if b.strip()]
    enrich_ops = [e.strip() for e in parts[1:] if e.strip()]
    for op in base_ops:
        source_chains.append((op, 'import', n, min_osm, max_osm, src))
    for op in enrich_ops:
        source_chains.append((op, 'enrich', n, min_osm, max_osm, src))

print(f"  {len(source_chains):,} source-operation pairs")

print("\n=== Step 2: Aggregate ===")
ops = defaultdict(lambda: {'import_count': 0, 'enrich_count': 0,
    'imported': 0, 'enriched': 0, 'min_osm': None, 'examples': []})

for op_name, op_type, n, min_osm, max_osm, full_src in source_chains:
    d = ops[op_name]
    d[f'{op_type}_count'] += 1
    if op_type == 'import': d['imported'] += n
    else: d['enriched'] += n
    if min_osm and (d['min_osm'] is None or min_osm < d['min_osm']):
        d['min_osm'] = min_osm
    if len(d['examples']) < 3:
        d['examples'].append(full_src)

print("\n=== Step 3: Date anchors ===")
c.execute("SELECT source, MIN(started_at) FROM provenance_log WHERE started_at IS NOT NULL GROUP BY source")
existing_dates = {r[0]: r[1] for r in c.fetchall() if r[0]}

c.execute("""
    SELECT c.source, MIN(e.last_updated)
    FROM churches c JOIN church_enrichment e ON c.id = e.church_id
    WHERE e.last_updated IS NOT NULL AND c.source IS NOT NULL
    GROUP BY c.source
""")
enrich_dates = {}
for src, min_d in c.fetchall():
    base = src.split('+')[0].split(',')[0].strip()
    if base not in enrich_dates or (min_d and min_d < enrich_dates[base]):
        enrich_dates[base] = min_d

conn.close()

print("\n=== Step 4: Build entries ===\n")
reconstructed = []
for op_name, data in sorted(ops.items(), key=lambda x: -(x[1]['imported'] + x[1]['enriched'])):
    total = data['imported'] + data['enriched']
    if total < 10:
        continue

    script = SOURCE_SCRIPT_MAP.get(op_name, f'{op_name} (unknown)')
    date_est = None
    date_src = "none"

    if op_name in existing_dates:
        date_est = existing_dates[op_name]; date_src = "existing_provenance_log"
    elif data['min_osm']:
        date_est = data['min_osm']; date_src = "osm_timestamp"
    elif op_name in enrich_dates:
        date_est = enrich_dates[op_name]; date_src = "enrichment_last_updated"

    entry = {
        'source': op_name,
        'script_name': script,
        'started_at': date_est,
        'date_source': date_src,
        'churches_inserted': data['imported'],
        'churches_updated': data['enriched'],
        'records_matched': total,
        'status': 'reconstructed',
        'notes': f'Reconstructed from source field. Date: {date_src}. Examples: {data["examples"][:3]}',
    }
    reconstructed.append(entry)
    print(f"  {op_name:35s} imported={data['imported']:>10,} enriched={data['enriched']:>10,}  [{date_src}]")

with open(OUTPUT_JSON, 'w') as f:
    json.dump({
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'description': 'Reconstructed provenance_log entries from churches.source field',
        'entries': reconstructed,
    }, f, indent=2)

print(f"\n✓ {len(reconstructed)} entries → {OUTPUT_JSON}")

if APPLY:
    print("\n=== Applying to DB ===")
    try:
        conn = sqlite3.connect(DB, timeout=60)
        conn.execute("PRAGMA busy_timeout=60000")
        c = conn.cursor()
        c.execute("DELETE FROM provenance_log WHERE status='reconstructed'")
        for e in reconstructed:
            c.execute("""INSERT INTO provenance_log
                (source, script_name, started_at, churches_updated,
                 churches_inserted, records_matched, status, notes)
                VALUES (?,?,?,?,?,?,'reconstructed',?)""",
                (e['source'], e['script_name'], e['started_at'],
                 e['churches_updated'], e['churches_inserted'],
                 e['records_matched'], e['notes']))
        conn.commit()
        conn.close()
        print(f"✓ Applied {len(reconstructed)} entries")
    except sqlite3.OperationalError as er:
        if 'locked' in str(er).lower():
            print(f"⚠ DB locked. Re-run with --apply later. Data saved in {OUTPUT_JSON}")
        else: raise
else:
    print(f"Run with --apply to write to DB when the other agent finishes.")
