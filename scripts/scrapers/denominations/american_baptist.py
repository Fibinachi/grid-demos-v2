"""
American Baptist Churches USA — Scraper Hub
============================================
Central entry point for all ABCUSA data collection.

Primary source (recommended):
  scripts/scrapers/denominations/abc_regions/abcusa_netsuite_scraper.py
  → Scrapes the centralized NetSuite directory with ALL ABC churches.
    Requires Playwright. Has simple math CAPTCHA.

Fallback: 33 individual region convention stubs in abc_regions/ directory.
"""
import os, sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
REGIONS_DIR = os.path.join(PROJECT_DIR, 'scripts', 'scrapers', 'denominations', 'abc_regions')

REGION_SCRAPERS = [
    ("ABCCT", "Connecticut", "region_ct.py"),
    ("ABCME", "Maine", "region_me.py"),
    ("ABCMA", "Massachusetts", "region_ma.py"),
    ("ABCNH", "New Hampshire", "region_nh.py"),
    ("ABCRI", "Rhode Island", "region_ri.py"),
    ("ABCVT", "Vermont", "region_vt.py"),
    ("ABCNYS", "New York State", "region_ny.py"),
    ("ABCNJ", "New Jersey", "region_nj.py"),
    ("ABCPAD", "Pennsylvania & Delaware", "region_pad.py"),
    ("ABCMDDE", "Maryland/Delaware", "region_mdde.py"),
    ("ABCOH", "Ohio", "region_oh.py"),
    ("ABCIN", "Indiana", "region_in.py"),
    ("ABCGRR", "Great Rivers (IL)", "region_grr.py"),
    ("ABCMI", "Michigan", "region_mi.py"),
    ("ABCWI", "Wisconsin", "region_wi.py"),
    ("ABCMN", "Minnesota", "region_mn.py"),
    ("ABCIA", "Iowa", "region_ia.py"),
    ("ABCMO", "Missouri", "region_mo.py"),
    ("ABCKS", "Kansas", "region_ks.py"),
    ("ABCNE", "Nebraska", "region_ne.py"),
    ("ABCDAK", "Dakotas", "region_dak.py"),
    ("ABCROCK", "Rocky Mountains", "region_rockies.py"),
    ("ABCSOUTH", "The South", "region_south.py"),
    ("ABCPACSW", "Pacific Southwest", "region_pacsw.py"),
    ("ABCWEST", "The West", "region_west.py"),
    ("ABCLOSA", "Los Angeles Area", "region_losa.py"),
    ("ABCNORCAL", "Northern California", "region_norcal.py"),
    ("ABCNW", "Northwest", "region_nw.py"),
    ("ABCOR", "Oregon", "region_or.py"),
    ("ABCPR", "Puerto Rico", "region_pr.py"),
    ("ABCPHILA", "Philadelphia Baptist", "region_phila.py"),
    ("ABCCHI", "Chicago", "region_chi.py"),
]

def main():
    print("=== American Baptist Churches USA — Scraper Hub ===")
    print()
    print("Primary source (recommended):")
    print("  python scripts/scrapers/denominations/abc_regions/abcusa_netsuite_scraper.py")
    print()
    print("33 regional convention scrapers:")
    for code, name, fn in REGION_SCRAPERS:
        fpath = os.path.join(REGIONS_DIR, fn)
        exists = "✓" if os.path.exists(fpath) else "✗ stub"
        print(f"  {exists} {code:10s} {name:30s} {fn}")
    print()
    print(f"Total: {len(REGION_SCRAPERS)} regions")

if __name__ == '__main__':
    main()
