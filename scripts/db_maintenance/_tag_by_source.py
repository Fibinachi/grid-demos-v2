"""
1. Tag generic-name churches (Grace Church, Community Church, etc.) as Non-Denom
2. Tag by scraper source for known-denomination scrapers
"""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
total = 0

def tag_denom(label, denom, where_clause):
    global total
    c.execute(f"""UPDATE churches SET denomination=?
        WHERE faith='Christian' AND (denomination IS NULL OR denomination='')
        AND ({where_clause})""", (denom,))
    if c.rowcount > 0:
        print(f"  {label}: {c.rowcount:,}")
        total += c.rowcount

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Generic church names → Non-Denom (when no other denominational signal)
# ═══════════════════════════════════════════════════════════════════════════════
print("=== Generic name → Non-Denominational ===")

# Pattern: single-noun churches without denominational keywords
tag_denom("Grace Church", "Non-Denominational",
    "LOWER(name) LIKE '%grace%church%'")
tag_denom("Community Church", "Non-Denominational",
    "LOWER(name) LIKE '%community%church%'")
tag_denom("Bible Church", "Non-Denominational",
    "LOWER(name) LIKE '%bible%church%'")
tag_denom("Fellowship Church", "Non-Denominational",
    "LOWER(name) LIKE '%fellowship%church%'")
tag_denom("Faith Church", "Non-Denominational",
    "LOWER(name) LIKE '%faith%church%'")
tag_denom("Hope Church", "Non-Denominational",
    "LOWER(name) LIKE '%hope%church%'")
tag_denom("New Life Church", "Non-Denominational",
    "LOWER(name) LIKE '%new life%church%' OR LOWER(name) LIKE '%newlife%church%'")
tag_denom("Cross Church", "Non-Denominational",
    "LOWER(name) LIKE '%cross%church%' AND LOWER(name) NOT LIKE '%holy cross%'")
tag_denom("Calvary Church", "Non-Denominational",
    "LOWER(name) LIKE '%calvary%church%'")
tag_denom("Cornerstone Church", "Non-Denominational",
    "LOWER(name) LIKE '%cornerstone%church%'")
tag_denom("Living Water/Vineyard/etc", "Non-Denominational",
    "(LOWER(name) LIKE '%vineyard%church%' OR LOWER(name) LIKE '%living water%church%' OR LOWER(name) LIKE '%new hope%church%' OR LOWER(name) LIKE '%new beginning%church%' OR LOWER(name) LIKE '%harvest%church%' OR LOWER(name) LIKE '%life church%' OR LOWER(name) LIKE '%family church%' OR LOWER(name) LIKE '%river%church%' OR LOWER(name) LIKE '%rock%church%' OR LOWER(name) LIKE '%living word%' OR LOWER(name) LIKE '%living faith%' OR LOWER(name) LIKE '%victory%church%' OR LOWER(name) LIKE '%covenant%church%')")
tag_denom("St./Saint church", "Non-Denominational",
    "(LOWER(name) LIKE '%st. %church%' OR LOWER(name) LIKE '%st %church%' OR LOWER(name) LIKE '%saint%church%') AND LOWER(name) NOT LIKE '%catholic%' AND LOWER(name) NOT LIKE '%orthodox%' AND LOWER(name) NOT LIKE '%episcopal%' AND LOWER(name) NOT LIKE '%anglican%' AND LOWER(name) NOT LIKE '%lutheran%'")
tag_denom("First/United church", "Non-Denominational",
    "(LOWER(name) LIKE '%first%church%' OR LOWER(name) LIKE '%united church%') AND LOWER(name) NOT LIKE '%united methodist%' AND LOWER(name) NOT LIKE '%united church of christ%' AND LOWER(name) NOT LIKE '%ucc%'")

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Scraper source → denomination
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Scraper source → denomination ===")

scraper_denoms = {
    'cog_scraper': 'Church of God',
    'cogic_scraper': 'COGIC',
    'sbc_directory': 'Southern Baptist',
    'sbc_scrape': 'Southern Baptist',
    'umc_scrape': 'United Methodist',
    'umc_national': 'United Methodist',
    'pcusa_api': 'Presbyterian (PCUSA)',
    'lcms_scraper': 'Lutheran (LCMS)',
    'lds_scrape': 'LDS',
    'opc_scraper': 'Orthodox Presbyterian',
    'arp_scraper': 'ARP',
    'arp_scrape': 'ARP',
    'fwb_scraper': 'Free Will Baptist',
    'wesleyan_district_scraper': 'Wesleyan',
    'ame_district_scrape': 'AME',
    'nbc_pdf_scrape': 'National Baptist',
    'ag_directory': 'Assemblies of God',
    'seacoast_scraper': 'Non-Denominational',
    'newspring_scraper': 'Non-Denominational',
    'cs_directory_scraper': 'Christian Science',
    'coc_21stcc': 'Church of Christ',
    'Kentucky Baptist Convention (kybaptist.org)': 'Baptist',
    'txbaptists_org': 'Baptist',
    'kncsb_org': 'Baptist',
    'catholic_diocese_scrape': 'Roman Catholic',
    'diocese_directory': 'Roman Catholic',
    'diocese_sitemap': 'Roman Catholic',
    'masstimes_nationwide': 'Roman Catholic',
    'la_masstimes_parishes': 'Roman Catholic',
    'la_catholic_schools': 'Roman Catholic',
    'churchunion_scraper': None,  # varies, skip for now
}

for source, denom in scraper_denoms.items():
    if denom is None:
        continue
    c.execute("""UPDATE churches SET denomination=?
        WHERE faith='Christian' AND (denomination IS NULL OR denomination='')
        AND source=?""", (denom, source))
    if c.rowcount > 0:
        print(f"  {source}: {c.rowcount:,} → {denom}")
        total += c.rowcount
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 3. churchunion_scraper → try denomination from name
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== churchunion_scraper (name-based) ===")
churchunion_map = [
    ("Trinity", "LOWER(name) LIKE '%trinity%'"),
    ("St. Paul", "LOWER(name) LIKE '%st. paul%' OR LOWER(name) LIKE '%saint paul%'"),
    ("St. Mary", "LOWER(name) LIKE '%st. mary%' OR LOWER(name) LIKE '%saint mary%'"),
    ("St. John", "LOWER(name) LIKE '%st. john%' OR LOWER(name) LIKE '%saint john%'"),
    ("Calvary", "LOWER(name) LIKE '%calvary%'"),
    ("Grace", "LOWER(name) LIKE '%grace%'"),
    ("Christ Church", "LOWER(name) LIKE '%christ church%' OR LOWER(name) LIKE '%christ episcopal%'"),
    ("St. Mark", "LOWER(name) LIKE '%st. mark%' OR LOWER(name) LIKE '%saint mark%'"),
    ("St. Luke", "LOWER(name) LIKE '%st. luke%' OR LOWER(name) LIKE '%saint luke%'"),
    ("St. Peter", "LOWER(name) LIKE '%st. peter%' OR LOWER(name) LIKE '%saint peter%'"),
]
for label, where_clause in churchunion_map:
    c.execute(f"""UPDATE churches SET denomination=?
        WHERE faith='Christian' AND (denomination IS NULL OR denomination='')
        AND source='churchunion_scraper' AND ({where_clause})""", (label,))
    if c.rowcount > 0:
        print(f"  {label}: {c.rowcount:,}")
        total += c.rowcount
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n=== Total tagged: {total:,} ===")
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian' AND (denomination IS NULL OR denomination='')")
remaining = c.fetchone()[0]
print(f"Christian NULL denomination remaining: {remaining:,}")

# Log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_tag_by_source.py', TS, TS,
      total, 0, 'denomination', 'completed',
      f'Tagged {total} records: generic → Non-Denom + scraper source → denomination'))

conn.commit()
conn.close()
