"""Quick check on Christian misclassifications in Jewish data."""
import sqlite3
c = sqlite3.connect(r'E:\grid\churches.db')

print("=== Christian misclassifications (have Christian faith_tradition but faith=Jewish) ===")
total = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Jewish' AND faith_tradition IN ('Christian','Baptist','Lutheran','Catholic','Pentecostal','Methodist','Anglican','Presbyterian','Churches of Christ','Anabaptist')").fetchone()[0]
print(f"Total: {total}")

print("\n--- Assembleia / Igreja / Spanish Christian patterns ---")
for r in c.execute("SELECT rowid, name, faith_tradition, denomination, source, country FROM churches WHERE faith='Jewish' AND faith_tradition='Pentecostal' LIMIT 20"):
    print(f"  rowid={r[0]:>8}  src={str(r[4])[:15]:15s}  cnt={r[5]:2s}  trad={str(r[2] or '-'):15s}  denom={str(r[3] or '-'):30s}  {str(r[1])[:55]:55s}")

print("\n--- Baptist entries ---")
for r in c.execute("SELECT rowid, name, faith_tradition, denomination, source, country FROM churches WHERE faith='Jewish' AND faith_tradition='Baptist' LIMIT 15"):
    print(f"  rowid={r[0]:>8}  src={str(r[4])[:15]:15s}  cnt={r[5]:2s}  trad={str(r[2] or '-'):15s}  denom={str(r[3] or '-'):30s}  {str(r[1])[:55]:55s}")

print("\n--- Lutheran entries ---")
for r in c.execute("SELECT rowid, name, faith_tradition, denomination, source, country FROM churches WHERE faith='Jewish' AND faith_tradition='Lutheran' LIMIT 15"):
    print(f"  rowid={r[0]:>8}  src={str(r[4])[:15]:15s}  cnt={r[5]:2s}  trad={str(r[2] or '-'):15s}  denom={str(r[3] or '-'):30s}  {str(r[1])[:55]:55s}")

print("\n--- AME/AME Zion/Congregational/Christian faith_tradition but Christian-sounding denom ---")
for r in c.execute("SELECT rowid, name, faith_tradition, denomination, source, country FROM churches WHERE faith='Jewish' AND faith_tradition='Christian' AND country='US' ORDER BY source LIMIT 30"):
    print(f"  rowid={r[0]:>8}  src={str(r[4])[:15]:15s}  cnt={r[5]:2s}  trad={str(r[2] or '-'):15s}  denom={str(r[3] or '-'):30s}  {str(r[1])[:55]:55s}")

print("\n=== Christian misclassifications count ===")
for r in c.execute("SELECT faith_tradition, COUNT(*) FROM churches WHERE faith='Jewish' AND faith_tradition IN ('Christian','Baptist','Lutheran','Catholic','Pentecostal','Methodist','Anglican','Presbyterian','Churches of Christ','Anabaptist','Unitarian Universalist','Independent catholic') GROUP BY faith_tradition ORDER BY COUNT(*) DESC"):
    print(f"  {str(r[0]):30s} {r[1]:>8}")

print("\n=== Muslim entries tagged Jewish ===")
for r in c.execute("SELECT rowid, name, faith_tradition, denomination, source, country FROM churches WHERE faith='Jewish' AND faith_tradition='Muslim' LIMIT 20"):
    print(f"  rowid={r[0]:>8}  src={str(r[4])[:15]:15s}  cnt={r[5]:2s}  trad={str(r[2] or '-'):15s}  denom={str(r[3] or '-'):30s}  {str(r[1])[:55]:55s}")

c.close()
