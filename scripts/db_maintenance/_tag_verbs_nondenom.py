"""Tag non-denom verb/concept-name churches."""
import sqlite3, datetime
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()
total = 0

# Verb/concept words that signal non-denom modern churches
verb_patterns = [
    '%converge%', '%elevate%', '%ignite%', '%thrive%', '%embrace%',
    '%genesis%', '%oasis%', '%pillar%', '%bridge%', '%journey%',
    '%wellspring%', '%pulse%', '%mosaic%', '%vantage%', '%beacon%',
    '%refuge%', '%harbor%', '%sanctuary%', '%ascent%', '%catalyst%',
    '%restore%', '%redeem%', '%uprising%', '%awaken%', '%revive%',
    '%flourish%', '%overflow%', '%genesis%', '%exodus%', '%kairos%',
    '%epic%', '%radiant%', '%vibrant%', '%legacy%', '%destiny%',
    '%kingdom%', '%dominion%', '%sojourn%', '%wayfarer%', '%pilgrim%',
    '%outpost%', '%crossing%', '%conduit%', '%portal%', '%nexus%',
    '%the gathering%', '%the table%', '%the porch%', '%the living room%',
    '%the well%', '%the grove%', '%the orchard%', '%the loft%',
    '%the upper room%', '%the sanctuary%', '%the river%',
    '% collective%', '% city%', '% house%',  # e.g. "Redemption City", "Hope House"
]

print("=== Tagging verb/concept non-denom churches ===")
for pattern in verb_patterns:
    c.execute(f"""UPDATE churches SET faith='Christian', faith_tradition='Christianity',
        denomination='Non-Denominational'
        WHERE (faith IS NULL OR faith='') AND LOWER(name) LIKE '{pattern}'
        AND LOWER(name) NOT LIKE '%church%' AND LOWER(name) NOT LIKE '%chapel%'
        AND LOWER(name) NOT LIKE '%baptist%' AND LOWER(name) NOT LIKE '%methodist%'
        AND LOWER(name) NOT LIKE '%catholic%' AND LOWER(name) NOT LIKE '%lutheran%'
        AND LOWER(name) NOT LIKE '%presbyterian%' AND LOWER(name) NOT LIKE '%episcopal%'""")
    if c.rowcount > 0:
        print(f"  {pattern}: {c.rowcount}")
        total += c.rowcount

conn.commit()

# Also tag remaining overture_full with "church" word as non-denom if no other signal
c.execute("""UPDATE churches SET faith='Christian', faith_tradition='Christianity',
    denomination='Non-Denominational'
    WHERE (faith IS NULL OR faith='') AND source='overture_full'
    AND LOWER(name) LIKE '%church%'
    AND LOWER(name) NOT LIKE '%baptist%' AND LOWER(name) NOT LIKE '%methodist%'
    AND LOWER(name) NOT LIKE '%catholic%' AND LOWER(name) NOT LIKE '%lutheran%'
    AND LOWER(name) NOT LIKE '%presbyterian%' AND LOWER(name) NOT LIKE '%episcopal%'
    AND LOWER(name) NOT LIKE '%adventist%' AND LOWER(name) NOT LIKE '%nazarene%'
    AND LOWER(name) NOT LIKE '%pentecostal%' AND LOWER(name) NOT LIKE '%holiness%'
    AND LOWER(name) NOT LIKE '%anglican%' AND LOWER(name) NOT LIKE '%orthodox%'
    AND LOWER(name) NOT LIKE '%united methodist%' AND LOWER(name) NOT LIKE '%evangelical%'""")
print(f"  Generic overture church → non-denom: {c.rowcount}")
total += c.rowcount
conn.commit()

# Scrapers with known denominations → tag by source
scraper_faith = {
    'cog_scraper': ('Christian', 'Church of God'),
    'cogic_scraper': ('Christian', 'COGIC'),
    'churchunion_scraper': ('Christian', None),  # varies
    'ag_directory': ('Christian', 'Assemblies of God'),
    'sbc_directory': ('Christian', 'Southern Baptist'),
    'umc_scrape': ('Christian', 'United Methodist'),
    'pcusa_api': ('Christian', 'Presbyterian (PCUSA)'),
    'lcms_scraper': ('Christian', 'Lutheran (LCMS)'),
    'lds_scrape': ('Christian', 'LDS'),
    'opc_scraper': ('Christian', 'Orthodox Presbyterian'),
    'arp_scraper': ('Christian', 'ARP'),
    'fwb_scraper': ('Christian', 'Free Will Baptist'),
    'cs_directory_scraper': ('Christian', None),
    'wesleyan_district_scraper': ('Christian', 'Wesleyan'),
    'ame_district_scrape': ('Christian', 'AME'),
    'nbc_pdf_scrape': ('Christian', 'National Baptist'),
    'seacoast_scraper': ('Christian', 'Non-Denominational'),
    'newspring_scraper': ('Christian', 'Non-Denominational'),
}

print("\n=== Scraper source-based tagging ===")
for source, (faith, denom) in scraper_faith.items():
    if denom:
        c.execute("""UPDATE churches SET faith=?, faith_tradition=?, denomination=?
            WHERE (faith IS NULL OR faith='') AND source=?""",
            (faith, faith, denom, source))
    else:
        c.execute("""UPDATE churches SET faith=?, faith_tradition=?
            WHERE (faith IS NULL OR faith='') AND source=?""",
            (faith, faith, source))
    if c.rowcount > 0:
        print(f"  {source}: {c.rowcount} → {faith}" + (f" ({denom})" if denom else ""))
        total += c.rowcount
conn.commit()

print(f"\nTotal tagged: {total}")
c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith=''")
print(f"Remaining NULL-faith: {c.fetchone()[0]:,}")
conn.close()
