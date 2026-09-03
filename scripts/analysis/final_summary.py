#!/usr/bin/env python3
"""Final summary of all work done today."""
import csv, os
base = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(base, 'theology_master_list.csv')) as f:
    rows = list(csv.DictReader(f))

high = [r for r in rows if r['PRIORITY'] == 'HIGH']
med = [r for r in rows if r['PRIORITY'] == 'MEDIUM']
have_email = [r for r in rows if r['HAS_EMAIL'] == 'YES']
need_email = [r for r in rows if r['HAS_EMAIL'] == 'NEED SCRAPING']

print("\n" + "=" * 60)
print("FINAL MASTER LIST SUMMARY")
print("=" * 60)
print(f"Total theology foundations: {len(rows)}")
print(f"HIGH priority:              {len(high)}")
print(f"MEDIUM priority:            {len(med)}")
print(f"Already have email:         {len(have_email)}")
print(f"Still need email:           {len(need_email)}")
print(f"\nReady-to-send HIGH:         {len([r for r in high if r['HAS_EMAIL']=='YES'])}")
print(f"Need-scrape HIGH:           {len([r for r in high if r['HAS_EMAIL']=='NEED SCRAPING'])}")

# Key files created
print("\n" + "=" * 60)
print("KEY FILES CREATED TODAY")
print("=" * 60)
print("  theology_master_list.csv     - Full 10,573 foundation master list")
print("  theology_priority_send.csv   - 387 HIGH priority, ready to send")
print("  theology_need_scrape.csv     - 173 still need email scraping")
print("  theology_high_priority.csv   - 65 HIGH from tier1 specifically")
print("  classified_tier1.csv/tier2/tier3 - Full classifications")
print("  classified_theology.csv      - 111 ProPublica-found orgs")
print("  propublica_theology_foundations.csv - Raw search results")
print("  priority_all.csv            - 63 domains sent to EC2 fleet")
print("  foundation_grants_extracted.csv - Ford/Carnegie/etc financial data")
print("  parse_990pf_grants.py       - IRS grantee extractor tool")
print("  classify_foundations.py     - Theology classifier tool")
print("  propublica_search.py        - ProPublica API searcher")

# EC2 status
print("\n" + "=" * 60)
print("EC2 FLEET STATUS")
print("=" * 60)
print("  Main EC2 (18.220.3.141):   scraper killed, inbox monitor running")
print("  Tier1   (13.58.64.223):    done, idle")
print("  Tier2   (18.219.220.68):   done, idle")
print("  Tier3   (13.59.175.171):   done, idle")
print("  All scrapers repurposed to priority lists - completed.")
