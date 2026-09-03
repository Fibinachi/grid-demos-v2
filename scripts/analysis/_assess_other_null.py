"""Assess Other and NULL faith groups for DeepSeek classification."""
import sqlite3

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Overall faith counts
print("=== FAITH BREAKDOWN ===")
for row in c.execute("SELECT faith, COUNT(*) FROM churches GROUP BY faith ORDER BY COUNT(*) DESC"):
    print(f"  {row[0] or 'NULL':30s} {row[1]:>10,}")

print()

# NULL faith
print("=== NULL FAITH COUNTS ===")
for row in c.execute("SELECT faith, COUNT(*) FROM churches WHERE faith IS NULL OR faith='' OR LOWER(faith)='null' GROUP BY faith"):
    print(f"  faith=[{row[0]}]  {row[1]:>10,}")

null_count = c.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith='' OR LOWER(faith)='null'").fetchone()[0]
print(f"  TOTAL NULL faith: {null_count:,}")

print()
print("=== NULL FAITH: sample entries (first 30) ===")
for row in c.execute("""SELECT id, name, city, country, landmark_type, tradition 
    FROM churches WHERE faith IS NULL OR faith='' OR LOWER(faith)='null'
    LIMIT 30"""):
    print(f"  {row[0]:>10} | {str(row[1] or ''):50s} | {str(row[2] or ''):20s} | {str(row[3] or ''):20s} | {str(row[4] or ''):20s} | {str(row[5] or ''):30s}")

print()
print("=== NULL FAITH: landmark_type breakdown ===")
for row in c.execute("SELECT landmark_type, COUNT(*) FROM churches WHERE faith IS NULL OR faith='' OR LOWER(faith)='null' GROUP BY landmark_type ORDER BY COUNT(*) DESC"):
    print(f"  {str(row[0] or 'NULL'):25s} {row[1]:>10,}")

print()
print("=== NULL FAITH: country breakdown ===")
for row in c.execute("SELECT country, COUNT(*) FROM churches WHERE faith IS NULL OR faith='' OR LOWER(faith)='null' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 20"):
    print(f"  {str(row[0] or 'NULL'):30s} {row[1]:>10,}")

print()

# Other faith
other_count = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Other'").fetchone()[0]
print(f"=== OTHER FAITH: {other_count:,} total ===")

print()
print("=== OTHER FAITH: tradition breakdown (top 30) ===")
for row in c.execute("SELECT tradition, COUNT(*) FROM churches WHERE faith='Other' GROUP BY tradition ORDER BY COUNT(*) DESC LIMIT 30"):
    print(f"  {str(row[0] or 'NULL'):30s} {row[1]:>10,}")

print()
print("=== OTHER FAITH: landmark_type breakdown ===")
for row in c.execute("SELECT landmark_type, COUNT(*) FROM churches WHERE faith='Other' GROUP BY landmark_type ORDER BY COUNT(*) DESC LIMIT 20"):
    print(f"  {str(row[0] or 'NULL'):25s} {row[1]:>10,}")

print()
print("=== OTHER FAITH: country breakdown (top 20) ===")
for row in c.execute("SELECT country, COUNT(*) FROM churches WHERE faith='Other' GROUP BY country ORDER BY COUNT(*) DESC LIMIT 20"):
    print(f"  {str(row[0] or 'NULL'):30s} {row[1]:>10,}")

print()
print("=== OTHER FAITH: sample entries (30) ===")
for row in c.execute("""SELECT id, name, city, country, landmark_type, tradition 
    FROM churches WHERE faith='Other' LIMIT 30"""):
    print(f"  {row[0]:>10} | {str(row[1] or ''):50s} | {str(row[2] or ''):20s} | {str(row[3] or ''):20s} | {str(row[4] or ''):20s} | {str(row[5] or ''):30s}")

conn.close()
