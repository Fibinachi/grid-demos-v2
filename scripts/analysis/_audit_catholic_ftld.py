"""Audit Catholic FTLD (Faith-Tradition-Legacy-Denomination) coverage."""
import sqlite3

db = sqlite3.connect('E:\\grid\\churches.db', timeout=30)

# How to identify Catholic entries: tradition contains 'Catholic' OR legacy='Catholic' OR name patterns
print("=== Identifying Catholic entries ===")

# Method 1: tradition contains Catholic
t1 = db.execute("SELECT COUNT(*) FROM churches WHERE tradition LIKE '%Catholic%'").fetchone()[0]
print(f'  tradition LIKE "%Catholic%": {t1:,}')

# Method 2: legacy = Catholic
t2 = db.execute("SELECT COUNT(*) FROM churches WHERE legacy = 'Catholic'").fetchone()[0]
print(f'  legacy = "Catholic": {t2:,}')

# Method 3: faith = christian AND (tradition LIKE '%Catholic%' OR legacy = 'Catholic')
t3 = db.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE faith = 'christian'
      AND (tradition LIKE '%Catholic%' OR legacy = 'Catholic')
""").fetchone()[0]
print(f'  christian AND (tradition LIKE Catholic OR legacy=Catholic): {t3:,}')

# Broader: all possible Catholic indicators
catholic_ids = set()
for method, sql in [
    ('tradition Catholic', "SELECT id FROM churches WHERE tradition LIKE '%Catholic%'"),
    ('legacy Catholic', "SELECT id FROM churches WHERE legacy = 'Catholic'"),
    ('tradition Catholic Churches', "SELECT id FROM churches WHERE tradition = 'Catholic Churches'"),
]:
    ids = set(r[0] for r in db.execute(sql).fetchall())
    catholic_ids.update(ids)
    print(f'  {method}: {len(ids):,}')

print(f'\nTotal unique Catholic entries: {len(catholic_ids):,}')

# FTLD coverage for Catholics
total = len(catholic_ids)
if total:
    id_list = list(catholic_ids)
    
    for col, label in [('faith', 'faith=christian'), ('legacy', 'legacy=Catholic'),
                        ('tradition', 'tradition set'), ('denomination', 'denomination set')]:
        if col == 'faith':
            filled = db.execute(f"SELECT COUNT(*) FROM churches WHERE id IN ({','.join('?'*len(id_list))}) AND faith = 'christian'", id_list).fetchone()[0]
        elif col == 'legacy':
            filled = db.execute(f"SELECT COUNT(*) FROM churches WHERE id IN ({','.join('?'*len(id_list))}) AND legacy = 'Catholic'", id_list).fetchone()[0]
        elif col == 'tradition':
            filled = db.execute(f"SELECT COUNT(*) FROM churches WHERE id IN ({','.join('?'*len(id_list))}) AND tradition IS NOT NULL AND tradition != ''", id_list).fetchone()[0]
        else:
            filled = db.execute(f"SELECT COUNT(*) FROM churches WHERE id IN ({','.join('?'*len(id_list))}) AND denomination IS NOT NULL AND denomination != ''", id_list).fetchone()[0]
        print(f'\n  {label}: {filled:,} ({filled*100//total}%)')

    # Distinct tradition values
    print('\n=== Distinct tradition values for Catholics ===')
    cur = db.execute(f"""
        SELECT tradition, COUNT(*) as cnt FROM churches 
        WHERE id IN ({','.join('?'*len(id_list))}) AND tradition IS NOT NULL AND tradition != ''
        GROUP BY tradition ORDER BY cnt DESC LIMIT 20
    """, id_list)
    for r in cur:
        print(f'  {r[1]:>6} | {r[0]}')

    # Distinct legacy values
    print('\n=== Distinct legacy values for Catholics ===')
    cur = db.execute(f"""
        SELECT legacy, COUNT(*) as cnt FROM churches 
        WHERE id IN ({','.join('?'*len(id_list))}) AND legacy IS NOT NULL AND legacy != ''
        GROUP BY legacy ORDER BY cnt DESC LIMIT 10
    """, id_list)
    for r in cur:
        print(f'  {r[1]:>6} | {r[0]}')

    # Distinct denomination values
    print('\n=== Distinct denomination values for Catholics ===')
    cur = db.execute(f"""
        SELECT denomination, COUNT(*) as cnt FROM churches 
        WHERE id IN ({','.join('?'*len(id_list))}) AND denomination IS NOT NULL AND denomination != ''
        GROUP BY denomination ORDER BY cnt DESC LIMIT 20
    """, id_list)
    for r in cur:
        print(f'  {r[1]:>6} | {r[0]}')

    # Entries with wrong/missing faith
    wrong_faith = db.execute(f"""
        SELECT faith, COUNT(*) FROM churches
        WHERE id IN ({','.join('?'*len(id_list))})
          AND (faith IS NULL OR faith = '' OR faith != 'christian')
        GROUP BY faith ORDER BY COUNT(*) DESC
    """, id_list).fetchall()
    print('\n=== Non-christian faith values for Catholic entries ===')
    for r in wrong_faith:
        print(f'  {r[1]:>6} | faith={r[0]}')

    # Check by country
    print('\n=== Catholic entries by country (top 15) ===')
    cur = db.execute(f"""
        SELECT country, COUNT(*) FROM churches 
        WHERE id IN ({','.join('?'*len(id_list))})
        GROUP BY country ORDER BY COUNT(*) DESC LIMIT 15
    """, id_list)
    for r in cur:
        print(f'  {r[1]:>6} | {r[0]}')

db.close()
