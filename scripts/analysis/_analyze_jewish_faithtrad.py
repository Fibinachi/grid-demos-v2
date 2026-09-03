"""Deeper analysis of what faith_tradition='Jewish' vs 'Judaism' vs NULL means."""
import sqlite3
c = sqlite3.connect(r'E:\grid\churches.db')

print("=== faith_tradition='Judaism' - do they have denomination? ===")
denoms = c.execute("SELECT denomination, COUNT(*) FROM churches WHERE faith='Jewish' AND faith_tradition='Judaism' GROUP BY denomination ORDER BY COUNT(*) DESC LIMIT 15").fetchall()
for d in denoms:
    print(f"  {str(d[0] or 'NULL'):40s} {d[1]:>8}")

print("\n--- Sample Judaism entries ---")
for r in c.execute("SELECT rowid, name, source, denomination, country FROM churches WHERE faith='Jewish' AND faith_tradition='Judaism' AND source='holy_sites_import' LIMIT 20"):
    print(f"  rowid={r[0]:>8}  cnt={r[4]:2s}  src={str(r[2])[:20]:20s}  denom={str(r[3] or '-'):25s}  {str(r[1])[:60]:60s}")

print("\n--- US Judaism entries (sample) ---")
for r in c.execute("SELECT rowid, name, source, denomination, landmark_type FROM churches WHERE faith='Jewish' AND faith_tradition='Judaism' AND country='US' AND source='irs+holy_sites_enrichment' LIMIT 30"):
    print(f"  rowid={r[0]:>8}  lm={str(r[4] or '-'):15s}  denom={str(r[3] or '-'):25s}  src={str(r[2])[:20]:20s}  {str(r[1])[:60]:60s}")

print("\n=== faith_tradition=NULL - what's there? ===")
null_src = c.execute("SELECT source, COUNT(*) FROM churches WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition='') GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10").fetchall()
for s in null_src:
    print(f"  {str(s[0]):30s} {s[1]:>8}")

print("\n--- NULL faith_tradition sample ---")
for r in c.execute("SELECT rowid, name, source, denomination, country FROM churches WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition='') AND source='holy_sites_import' LIMIT 20"):
    print(f"  rowid={r[0]:>8}  cnt={r[4]:2s}  src={str(r[2])[:20]:20s}  denom={str(r[3] or '-'):25s}  {str(r[1])[:60]:60s}")

print("\n--- US NULL faith_tradition IRS/holy_sites ---")
for r in c.execute("SELECT rowid, name, source, denomination, landmark_type FROM churches WHERE faith='Jewish' AND (faith_tradition IS NULL OR faith_tradition='') AND country='US' AND source LIKE '%irs%' LIMIT 20"):
    print(f"  rowid={r[0]:>8}  lm={str(r[4] or '-'):15s}  denom={str(r[3] or '-'):25s}  src={str(r[2])[:20]:20s}  {str(r[1])[:60]:60s}")

c.close()
