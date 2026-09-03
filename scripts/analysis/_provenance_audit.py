"""Final provenance audit — full picture for the user"""
import sqlite3

db = sqlite3.connect(r'E:\grid\churches.db')
TOTAL = 263712

print("=" * 70)
print("PROVENANCE AUDIT — GrantWizard Church Database")
print("=" * 70)

# ── website_source ──
print(f"\n1. WEBSITE SOURCE ({'':>55s})")

rs = db.execute("""
    SELECT website_source, 
           COUNT(*),
           ROUND(COUNT(*)*100.0/?1,1)
    FROM churches WHERE website != ''
    GROUP BY website_source
    UNION ALL
    SELECT 'no website (website is blank)',
           COUNT(*),
           ROUND(COUNT(*)*100.0/?1,1)
    FROM churches WHERE website='' OR website IS NULL
    ORDER BY 2 DESC
""", (TOTAL,)).fetchall()
for r in rs:
    bar = '█' * int(r[2])
    print(f"  {r[0]:35s} {r[1]:>8,} ({r[2]:>5.1f}%) {bar}")

# ── confidence tiers ──
print(f"\n2. WEBSITE CONFIDENCE TIERS")
rs = db.execute("""
    SELECT website_confidence, COUNT(*), ROUND(COUNT(*)*100.0/?1,1)
    FROM churches WHERE website != ''
    GROUP BY website_confidence
    ORDER BY website_confidence DESC
""", (TOTAL,)).fetchall()
for r in rs:
    conf_label = f"conf={r[0]}"
    if r[0] == 0.95: conf_label += "  (Overture — authoritative)"
    elif r[0] == 0.85: conf_label += " (OSM — authoritative)"
    elif r[0] == 0.7: conf_label += "  (DDG found, pending verification)"
    elif r[0] == 0.3: conf_label += "  (batch guess, unverified)"
    print(f"  {conf_label:50s} {r[1]:>8,} ({r[2]:>5.1f}%)")

# ── phone_source ──
print(f"\n3. PHONE SOURCE")
rs = db.execute("SELECT phone_source, COUNT(*) FROM churches WHERE phone != '' GROUP BY phone_source ORDER BY COUNT(*) DESC").fetchall()
for r in rs:
    print(f"  {r[0]:35s} {r[1]:>8,}")

# ── address_source ──
print(f"\n4. ADDRESS SOURCE")
rs = db.execute("SELECT address_source, COUNT(*) FROM churches WHERE address != '' GROUP BY address_source ORDER BY COUNT(*) DESC").fetchall()
for r in rs:
    print(f"  {r[0]:35s} {r[1]:>8,}")

# ── classification_source ──
print(f"\n5. CLASSIFICATION SOURCE (denom/family/faith_tradition)")
rs = db.execute("""
    SELECT classification_source, COUNT(*) 
    FROM churches WHERE classification_source != '' 
    GROUP BY classification_source 
    ORDER BY COUNT(*) DESC
""").fetchall()
for r in rs:
    print(f"  {r[0]:35s} {r[1]:>8,}")
no_class = db.execute("SELECT COUNT(*) FROM churches WHERE classification_source='' AND denomination != ''").fetchone()[0]
print(f"  {'denom set but no classification_source':35s} {no_class:>8,}")

# ── Data quality summary ──
print(f"\n{'='*70}")
print("DATA QUALITY SUMMARY")
print(f"{'='*70}")
checks = [
    ("Church name present", "SELECT COUNT(*) FROM churches WHERE name != ''"),
    ("Has website", "SELECT COUNT(*) FROM churches WHERE website != ''"),
    ("Has verified website", "SELECT COUNT(*) FROM churches WHERE website_scrape_status='verified'"),
    ("Has phone", "SELECT COUNT(*) FROM churches WHERE phone != ''"),
    ("Has address", "SELECT COUNT(*) FROM churches WHERE address != ''"),
    ("Has city", "SELECT COUNT(*) FROM churches WHERE city != ''"),
    ("Has state", "SELECT COUNT(*) FROM churches WHERE state != ''"),
    ("Has ZIP", "SELECT COUNT(*) FROM churches WHERE zip != '' AND zip != '0'"),
    ("Has lat/lng coordinates", "SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND longitude IS NOT NULL"),
    ("Has denomination", "SELECT COUNT(*) FROM churches WHERE denomination != ''"),
    ("Has EIN (tax ID)", "SELECT COUNT(*) FROM churches WHERE ein != ''"),
    ("Website provenance tagged", "SELECT COUNT(*) FROM churches WHERE website_source != '' AND website != ''"),
]
for label, q in checks:
    cnt = db.execute(q).fetchone()[0]
    pct = cnt / TOTAL * 100
    bar = '█' * int(pct/2)
    print(f"  {label:35s} {cnt:>8,} / {TOTAL:,} ({pct:5.1f}%) {bar}")

db.close()
