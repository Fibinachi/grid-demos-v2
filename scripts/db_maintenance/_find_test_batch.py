import sqlite3, re

db = sqlite3.connect("E:\\grid\\churches.db")
non_roman = re.compile(r'[\u0400-\u04FF\u0370-\u03FF\u0600-\u06FF\u0590-\u05FF\u4E00-\u9FFF\u3400-\u4DBF\u3040-\u309F\u30A0-\u30FF\uAC00-\uD7AF\u0E00-\u0E7F]')

# Find first 100 non-roman IDs
cur = db.execute('SELECT id, name FROM churches WHERE name IS NOT NULL AND name != ""')
ids = []
for row in cur:
    if non_roman.search(row[1]):
        ids.append((row[0], row[1][:80]))
    if len(ids) >= 100:
        break

print(f"First 100 non-roman IDs: {ids[0][0]} to {ids[-1][0]}")
min_id = ids[0][0]
max_id = ids[-1][0]

# Get the actual batch
cur = db.execute('SELECT id, name, COALESCE(name_original,"") FROM churches WHERE id >= ? AND id <= ? ORDER BY id', (min_id, max_id))
batch = cur.fetchall()
print(f"Batch size: {len(batch)}")
non_roman_count = sum(1 for r in batch if non_roman.search(r[1]))
print(f"Non-roman in batch: {non_roman_count}")

# Show a few examples
print("\n=== Sample non-roman records ===")
for r in ids[:10]:
    print(f"  id={r[0]}: {r[1]}")
db.close()
