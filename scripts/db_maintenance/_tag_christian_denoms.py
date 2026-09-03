"""Tag denomination for ALL Christian records that have clear name signals."""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()

# How many Christian records have NULL denomination?
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian' AND (denomination IS NULL OR denomination='')")
total_null = c.fetchone()[0]
print(f"Christian records with NULL denomination: {total_null:,}")

# How many of those have clear denomination signals in the name?
c.execute("""SELECT COUNT(*) FROM churches WHERE faith='Christian' AND (denomination IS NULL OR denomination='')
AND (LOWER(name) LIKE '%baptist%' OR LOWER(name) LIKE '%methodist%' 
  OR LOWER(name) LIKE '%lutheran%' OR LOWER(name) LIKE '%catholic%'
  OR LOWER(name) LIKE '%presbyterian%' OR LOWER(name) LIKE '%episcopal%'
  OR LOWER(name) LIKE '%pentecostal%' OR LOWER(name) LIKE '%adventist%'
  OR LOWER(name) LIKE '%nazarene%' OR LOWER(name) LIKE '%holiness%'
  OR LOWER(name) LIKE '%anglican%' OR LOWER(name) LIKE '%orthodox%'
  OR LOWER(name) LIKE '%mennonite%' OR LOWER(name) LIKE '%reformed%'
  OR LOWER(name) LIKE '%evangelical%' OR LOWER(name) LIKE '%brethren%'
  OR LOWER(name) LIKE '%cogic%' OR LOWER(name) LIKE '%wesleyan%'
  OR LOWER(name) LIKE '%assembly of god%' OR LOWER(name) LIKE '%church of god%'
  OR LOWER(name) LIKE '%united church of christ%' OR LOWER(name) LIKE '%ucc %'
  OR LOWER(name) LIKE '%united methodist%')""")
clear_signals = c.fetchone()[0]
print(f"With clear denomination signals in name: {clear_signals:,}")
print()

# ── Tag them ─────────────────────────────────────────────────────────────────
total = 0
denom_map = [
    ("Baptist", "LOWER(name) LIKE '%baptist%' OR LOWER(name) LIKE '%bautista%'"),
    ("Methodist", "LOWER(name) LIKE '%methodist%' OR LOWER(name) LIKE '%metodista%'"),
    ("Lutheran", "LOWER(name) LIKE '%lutheran%' OR LOWER(name) LIKE '%luteran%' OR LOWER(name) LIKE '%luthérien%'"),
    ("Catholic", "LOWER(name) LIKE '%catholic%' OR LOWER(name) LIKE '%católica%' OR LOWER(name) LIKE '%catholique%'"),
    ("Presbyterian", "LOWER(name) LIKE '%presbyterian%' OR LOWER(name) LIKE '%presbiterian%' OR LOWER(name) LIKE '%presbytérien%'"),
    ("Episcopal", "LOWER(name) LIKE '%episcopal%'"),
    ("Pentecostal", "LOWER(name) LIKE '%pentecostal%' OR LOWER(name) LIKE '%pentecostés%' OR LOWER(name) LIKE '%pentecôtiste%'"),
    ("Adventist", "LOWER(name) LIKE '%adventist%' OR LOWER(name) LIKE '%adventista%'"),
    ("Nazarene", "LOWER(name) LIKE '%nazarene%' OR LOWER(name) LIKE '%nazareno%'"),
    ("Holiness", "LOWER(name) LIKE '%holiness%'"),
    ("Anglican", "LOWER(name) LIKE '%anglican%' OR LOWER(name) LIKE '%anglicano%'"),
    ("Orthodox", "LOWER(name) LIKE '%orthodox%' OR LOWER(name) LIKE '%ortodox%'"),
    ("Mennonite", "LOWER(name) LIKE '%mennonite%' OR LOWER(name) LIKE '%menonita%'"),
    ("Reformed", "LOWER(name) LIKE '%reformed%' OR LOWER(name) LIKE '%reformada%' OR LOWER(name) LIKE '%reformée%'"),
    ("Evangelical", "LOWER(name) LIKE '%evangelical%' OR LOWER(name) LIKE '%evangélic%'"),
    ("Brethren", "LOWER(name) LIKE '%brethren%' OR LOWER(name) LIKE '%hermanos%'"),
    ("COGIC", "LOWER(name) LIKE '%cogic%' OR LOWER(name) LIKE '%church of god in christ%'"),
    ("Wesleyan", "LOWER(name) LIKE '%wesleyan%' OR LOWER(name) LIKE '%wesleyn%'"),
    ("Assemblies of God", "LOWER(name) LIKE '%assembly of god%' OR LOWER(name) LIKE '%assemblies of god%' OR LOWER(name) LIKE '%asamblea% de dios%'"),
    ("Church of God", "LOWER(name) LIKE '%church of god%' AND LOWER(name) NOT LIKE '%assembl%' AND LOWER(name) NOT LIKE '%in christ%'"),
    ("United Church of Christ", "LOWER(name) LIKE '%united church of christ%' OR LOWER(name) LIKE '%ucc %' OR LOWER(name) LIKE '% ucc%'"),
    ("United Methodist", "LOWER(name) LIKE '%united methodist%'"),
    ("Congregational", "LOWER(name) LIKE '%congregational%'"),
    ("Disciples of Christ", "LOWER(name) LIKE '%disciples of christ%' OR LOWER(name) LIKE '%discípulos de cristo%'"),
    ("Christian Church", "LOWER(name) LIKE '%christian church%' AND LOWER(name) NOT LIKE '%disciples%'"),
    ("Quaker/Friends", "LOWER(name) LIKE '%quaker%' OR LOWER(name) LIKE '%friends meeting%' OR LOWER(name) LIKE '%friends church%'"),
    ("Jehovah's Witnesses", "LOWER(name) LIKE '%jehovah%witness%' OR LOWER(name) LIKE '%testigos de jehova%'"),
    ("Mormon/LDS", "LOWER(name) LIKE '%latter-day%' OR LOWER(name) LIKE '%latter day%' OR LOWER(name) LIKE '%mormon%' OR LOWER(name) LIKE '%lds%' OR LOWER(name) LIKE '%saint%latter%'"),
    ("Salvation Army", "LOWER(name) LIKE '%salvation army%' OR LOWER(name) LIKE '%ejército de salvación%'"),
    ("Non-Denominational", "LOWER(name) LIKE '%non-denom%' OR LOWER(name) LIKE '%non denom%' OR LOWER(name) LIKE '%nondenom%' OR LOWER(name) LIKE '%community church%' AND LOWER(name) NOT LIKE '%baptist%' AND LOWER(name) NOT LIKE '%methodist%' AND LOWER(name) NOT LIKE '%lutheran%' AND LOWER(name) NOT LIKE '%presbyterian%'"),
]

for label, where_clause in denom_map:
    c.execute(f"""UPDATE churches SET denomination=? 
        WHERE faith='Christian' AND (denomination IS NULL OR denomination='')
        AND ({where_clause})""", (label,))
    if c.rowcount > 0:
        print(f"  {label}: {c.rowcount:,}")
        total += c.rowcount

conn.commit()

# Also: source-based denomination for known scraper sources
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
}

print()
for source, denom in scraper_denoms.items():
    c.execute("""UPDATE churches SET denomination=?
        WHERE faith='Christian' AND (denomination IS NULL OR denomination='')
        AND source=?""", (denom, source))
    if c.rowcount > 0:
        print(f"  {source}: {c.rowcount:,} → {denom}")
        total += c.rowcount
conn.commit()

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian' AND (denomination IS NULL OR denomination='')")
remaining = c.fetchone()[0]
print(f"\nTotal tagged: {total:,}")
print(f"Christian with NULL denomination remaining: {remaining:,}")
conn.close()
