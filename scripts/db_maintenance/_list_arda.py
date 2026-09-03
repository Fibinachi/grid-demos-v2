import sqlite3
c = sqlite3.connect('file:churches.db?mode=ro', uri=True)
print("=== ALL ARDA CODES ===")
codes = [r[0] for r in c.execute("SELECT DISTINCT arda_code FROM arda_denom_lookup ORDER BY arda_code")]
for code in codes:
    keyword = c.execute("SELECT keyword FROM arda_denom_lookup WHERE arda_code=?", (code,)).fetchone()[0]
    print(f"  {code:8s} {keyword}")

print(f"\nTotal ARDA codes: {len(codes)}")

print("\n=== ALL OUR DENOMINATIONS ===")
denoms = [r[0] for r in c.execute("SELECT DISTINCT denomination FROM churches WHERE denomination IS NOT NULL AND denomination != '' ORDER BY denomination")]
for d in denoms:
    cnt = c.execute("SELECT COUNT(1) FROM churches WHERE denomination=?", (d,)).fetchone()[0]
    print(f"  {d[:60]:60s} {cnt:,}")

print(f"\nTotal our denominations: {len(denoms)}")

# Also check arda_counts for what codes have data by county
print("\n=== ARDA CODES WITH COUNTY DATA (top 30) ===")
for r in c.execute("""
    SELECT denom_code, COUNT(DISTINCT county_fips) as counties, SUM(arda_congregations) as churches, SUM(arda_adherents) as adherents
    FROM arda_counts 
    GROUP BY denom_code 
    ORDER BY SUM(arda_adherents) DESC 
    LIMIT 30
"""):
    print(f"  {r[0]:8s} {r[1]:,} counties  {r[2]:,} churches  {r[3]:,} adherents")

c.close()
