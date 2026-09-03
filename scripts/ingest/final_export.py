import sqlite3, json

conn = sqlite3.connect('E:/grid/wpa.db')

total = conn.execute("SELECT COUNT(*) FROM wpa_churches").fetchone()[0]
print(f"WPA Database: {total} entries")

# Check data quality
print("\nQuality breakdown:")
stats = []
for state, count in conn.execute("SELECT state, COUNT(*) FROM wpa_churches GROUP BY state ORDER BY COUNT(*) DESC").fetchall():
    stats.append((state, count))

for state, count in stats:
    print(f"  {state}: {count}")

# Save final JSON
entries = [{"state": r[0], "church_name": r[1]} for r in conn.execute("SELECT state, church_name FROM wpa_churches ORDER BY state, church_name").fetchall()]
with open('E:/grid/data/wpa/wpa_final.json', 'w', encoding='utf-8') as f:
    json.dump(entries, f, indent=2)

print(f"\nSaved to wpa_final.json")

conn.close()