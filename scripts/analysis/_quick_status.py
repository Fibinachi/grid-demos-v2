#!/usr/bin/env python3
import sqlite3, os
db = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "churches.db"))
print("=== DB State ===")
t = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
w = db.execute("SELECT COUNT(*) FROM churches WHERE website IS NOT NULL AND website != ''").fetchone()[0]
e = db.execute("SELECT COUNT(*) FROM churches WHERE email IS NOT NULL AND email != ''").fetchone()[0]
f = db.execute("SELECT COUNT(*) FROM churches WHERE website_scrape_status = 'found'").fetchone()[0]
p = db.execute("SELECT COUNT(*) FROM churches WHERE website_scrape_status = 'pending'").fetchone()[0]
print(f"  Total records:      {t:>7,}")
print(f"  Websites:           {w:>7,} ({w/t*100:.1f}%)")
print(f"  Emails:             {e:>7,} ({e/t*100:.1f}%)")
print(f"  Scrape found:       {f:>7,}")
print(f"  Scrape pending:     {p:>7,}")
print(f"  Batch additions:    {f-4725:>+7,} (was 4,725 before batch)")
db.close()
