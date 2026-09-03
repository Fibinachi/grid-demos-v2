"""Audit column fill rates across churches — identify dead/underused columns."""
import sqlite3

db = sqlite3.connect('E:/grid/churches.db')
total = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]

# Get all columns
cols = [(r[1], r[2]) for r in db.execute("PRAGMA table_info(churches)")]

# Sample fill rates (faster than COUNT per column)
print("--- churches column fill rates (2,228,489 rows) ---")
print(f"{'Column':<30} {'Filled':>10} {'Rate':>8}")
print("-" * 50)

dead = []
low = []
medium = []
high = []

SAMPLE_SIZE = 100000
for col_name, col_type in cols:
    if col_name in ('id',):
        continue
    # Check if column has any non-null values
    cnt = db.execute(f"SELECT COUNT(*) FROM churches WHERE {col_name} IS NOT NULL AND {col_name} != '' LIMIT 1").fetchone()[0]
    if cnt == 0:
        dead.append(col_name)
        continue
    # Quick sample-based fill rate
    filled = db.execute(f"""
        SELECT COUNT(*) FROM (
            SELECT {col_name} FROM churches 
            WHERE {col_name} IS NOT NULL AND {col_name} != ''
            LIMIT {SAMPLE_SIZE}
        )
    """).fetchone()[0]
    
    # Approximate from total
    actual = db.execute(f"""
        SELECT COUNT(*) FROM churches 
        WHERE {col_name} IS NOT NULL AND {col_name} != ''
    """).fetchone()[0]
    pct = 100 * actual / total
    
    bar = "█" * int(pct / 5) if pct > 0 else ""
    print(f"{col_name:<30} {actual:>10,} {pct:>7.1f}% {bar}")
    
    if pct < 0.1:
        dead.append(col_name)
    elif pct < 5:
        low.append(col_name)
    elif pct < 30:
        medium.append(col_name)
    else:
        high.append(col_name)

print(f"\n--- Summary ---")
print(f"Total columns: {len(cols)}")
print(f"Completely dead (0%): {len(dead)}")
print(f"Near-dead (<0.1%): {sum(1 for c in dead)}")
print(f"Low fill (<5%): {len(low)}")
print(f"Medium (5-30%): {len(medium)}")
print(f"High (>30%): {len(high)}")

# Show dead columns
print(f"\n--- Dead columns (0% fill) ---")
for c in dead:
    print(f"  {c}")

# Show low-fill columns (possible cleanup candidates)
print(f"\n--- Low fill (<5%) ---")
for c in low:
    print(f"  {c}")

db.close()
