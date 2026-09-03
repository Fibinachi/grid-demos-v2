"""
Add canonical_status column for religious orders and populate it.
Also restructure denominations into parent-child taxonomy.
"""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
total = 0

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Add canonical_status column if it doesn't exist
# ═══════════════════════════════════════════════════════════════════════════════
try:
    c.execute("ALTER TABLE churches ADD COLUMN canonical_status TEXT")
    print("Added canonical_status column")
except sqlite3.OperationalError:
    print("canonical_status column already exists")

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Restructure denominations: Catholic (X) → Roman Catholic (X)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Restructuring denominations ===")

# Catholic orders
orders = ['Augustinian','Basilian','Benedictine','Capuchin','Carmelite',
          'Cistercian','Dominican','Franciscan','Jesuit','Marianist',
          'Marist','Norbertine/Premonstratensian','Oblate','Passionist',
          'Pauline','Poor Clare','Redemptorist','Salesian','Servite','Vincentian']
for order in orders:
    c.execute("UPDATE churches SET denomination=? WHERE denomination=?",
              (f"Roman Catholic ({order})", f"Catholic ({order})"))
    if c.rowcount > 0:
        print(f"  Catholic → Roman Catholic ({order}): {c.rowcount}")
        total += c.rowcount

# Catholic → Roman Catholic
for old, new in [("Catholic","Roman Catholic"),("Roman Catholic Church","Roman Catholic")]:
    c.execute("UPDATE churches SET denomination=? WHERE denomination=?",(new,old))
    if c.rowcount > 0: print(f"  {old} → {new}: {c.rowcount}"); total += c.rowcount

# Orthodox restructure
eo_map = {
    "Eastern Orthodox (Greek)": "denomination='Eastern Orthodox (Greek)' OR denomination='Greek Orthodox Archdiocese of America'",
    "Eastern Orthodox (Russian)": "denomination='Eastern Orthodox (Russian)'",
    "Eastern Orthodox (Serbian)": "denomination='Eastern Orthodox (Serbian)'",
    "Eastern Orthodox (Romanian)": "denomination='Eastern Orthodox (Romanian)'",
    "Eastern Orthodox (Bulgarian)": "denomination='Eastern Orthodox (Bulgarian)'",
    "Eastern Orthodox (Ukrainian)": "denomination='Eastern Orthodox (Ukrainian)'",
    "Eastern Orthodox (Georgian)": "denomination='Eastern Orthodox (Georgian)'",
    "Eastern Orthodox (Antiochian)": "denomination='Eastern Orthodox (Antiochian)'",
    "Eastern Orthodox (OCA)": "denomination='Eastern Orthodox (OCA)' OR denomination='Orthodox Church in America'",
}
for new_denom, where_clause in eo_map.items():
    c.execute(f"UPDATE churches SET denomination=? WHERE {where_clause}",(new_denom,))
    if c.rowcount > 0: print(f"  → {new_denom}: {c.rowcount}"); total += c.rowcount

# Tag generic "Orthodox" by name
for pattern, denom in [
    ("%greek orthodox%","Eastern Orthodox (Greek)"),
    ("%russian orthodox%","Eastern Orthodox (Russian)"),
    ("%serbian orthodox%","Eastern Orthodox (Serbian)"),
    ("%romanian orthodox%","Eastern Orthodox (Romanian)"),
    ("%bulgarian orthodox%","Eastern Orthodox (Bulgarian)"),
    ("%ukrainian orthodox%","Eastern Orthodox (Ukrainian)"),
    ("%antiochian orthodox%","Eastern Orthodox (Antiochian)"),
]:
    c.execute("UPDATE churches SET denomination=? WHERE denomination='Orthodox' AND LOWER(name) LIKE ?",(denom,pattern))
    if c.rowcount > 0: print(f"  Orthodox + {pattern} → {denom}: {c.rowcount}"); total += c.rowcount

# Remainder: generic Orthodox → Eastern Orthodox
c.execute("UPDATE churches SET denomination='Eastern Orthodox' WHERE denomination='Orthodox'")
if c.rowcount > 0: print(f"  Generic Orthodox → Eastern Orthodox: {c.rowcount}"); total += c.rowcount

# Oriental Orthodox
oo_map = {
    "Oriental Orthodox (Coptic)": "denomination='Oriental Orthodox (Coptic)' OR denomination='Coptic Orthodox Church' OR denomination='Coptic Orthodox'",
    "Oriental Orthodox (Armenian)": "denomination='Oriental Orthodox (Armenian)' OR denomination LIKE '%armenian orthodox%' OR denomination LIKE '%armenian apostolic%'",
    "Oriental Orthodox (Ethiopian)": "denomination='Oriental Orthodox (Ethiopian)' OR denomination='Ethiopian Orthodox Tewahedo Church'",
    "Oriental Orthodox (Eritrean)": "denomination='Oriental Orthodox (Eritrean)'",
    "Oriental Orthodox (Syriac)": "denomination='Oriental Orthodox (Syriac)' OR denomination LIKE '%syriac orthodox%'",
    "Oriental Orthodox (Malankara)": "denomination='Oriental Orthodox (Malankara)' OR denomination LIKE '%malankara orthodox%'",
}
for new_denom, where_clause in oo_map.items():
    c.execute(f"UPDATE churches SET denomination=? WHERE {where_clause}",(new_denom,))
    if c.rowcount > 0: print(f"  → {new_denom}: {c.rowcount}"); total += c.rowcount

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Tag canonical_status for religious houses
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Tagging canonical_status ===")

# Pontifical right: major exempt orders (report directly to Vatican)
pontifical_orders = [
    ("Franciscan", "LOWER(name) LIKE '%franciscan%'"),
    ("Dominican", "LOWER(name) LIKE '%dominican%' AND LOWER(name) NOT LIKE '%dominican republic%'"),
    ("Benedictine", "LOWER(name) LIKE '%benedictine%'"),
    ("Jesuit", "LOWER(name) LIKE '%jesuit%'"),
    ("Carmelite", "LOWER(name) LIKE '%carmelite%'"),
    ("Cistercian/Trappist", "LOWER(name) LIKE '%cistercian%' OR LOWER(name) LIKE '%trappist%'"),
    ("Poor Clare", "LOWER(name) LIKE '%poor clare%' OR LOWER(name) LIKE '%poor clares%'"),
    ("Capuchin", "LOWER(name) LIKE '%capuchin%'"),
    ("Augustinian", "LOWER(name) LIKE '%augustinian%'"),
    ("Carthusian", "LOWER(name) LIKE '%carthusian%'"),
    ("Passionist", "LOWER(name) LIKE '%passionist%'"),
    ("Redemptorist", "LOWER(name) LIKE '%redemptorist%'"),
    ("Salesian", "LOWER(name) LIKE '%salesian%'"),
    ("Oblate", "LOWER(name) LIKE '%oblate%'"),
    ("Vincentian", "LOWER(name) LIKE '%vincentian%'"),
    ("Marist", "LOWER(name) LIKE '%marist%' AND LOWER(name) NOT LIKE '%marianist%'"),
    ("Servite", "LOWER(name) LIKE '%servite%'"),
    ("Norbertine", "LOWER(name) LIKE '%norbertine%' OR LOWER(name) LIKE '%premonstratensian%'"),
]

for order_name, where_clause in pontifical_orders:
    c.execute(f"""
        UPDATE churches SET canonical_status='pontifical_right'
        WHERE (canonical_status IS NULL OR canonical_status='')
          AND ({where_clause})
          AND LOWER(name) LIKE '%monastery%'
    """)
    if c.rowcount > 0:
        print(f"  Pontifical right - {order_name}: {c.rowcount}")
        total += c.rowcount

# Also tag monasteries by source/denomination
c.execute("""
    UPDATE churches SET canonical_status='pontifical_right'
    WHERE (canonical_status IS NULL OR canonical_status='')
      AND LOWER(name) LIKE '%monastery%'
      AND denomination LIKE 'Roman Catholic (%'
""")
print(f"  Pontifical right (by denomination): {c.rowcount}")
total += c.rowcount

# Diocesan right: monasteries from catholic_diocese_scrape (likely diocesan)
c.execute("""
    UPDATE churches SET canonical_status='diocesan_right'
    WHERE (canonical_status IS NULL OR canonical_status='')
      AND LOWER(name) LIKE '%monastery%'
      AND source='catholic_diocese_scrape'
""")
print(f"  Diocesan right (diocese source): {c.rowcount}")
total += c.rowcount

# Orthodox monasteries → under their bishop/eparch
c.execute("""
    UPDATE churches SET canonical_status='eparchial'
    WHERE (canonical_status IS NULL OR canonical_status='')
      AND LOWER(name) LIKE '%monastery%'
      AND denomination LIKE 'Eastern Orthodox%'
""")
print(f"  Eparchial (Orthodox): {c.rowcount}")
total += c.rowcount

c.execute("""
    UPDATE churches SET canonical_status='eparchial'
    WHERE (canonical_status IS NULL OR canonical_status='')
      AND LOWER(name) LIKE '%monastery%'
      AND denomination LIKE 'Oriental Orthodox%'
""")
print(f"  Eparchial (Oriental Orthodox): {c.rowcount}")
total += c.rowcount

# Remaining monasteries that couldn't be classified
c.execute("""
    UPDATE churches SET canonical_status='unknown'
    WHERE (canonical_status IS NULL OR canonical_status='')
      AND LOWER(name) LIKE '%monastery%'
""")
print(f"  Unknown (remaining): {c.rowcount}")
total += c.rowcount

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n=== Total changes: {total} ===\n")

print("Denominations:")
c.execute("""SELECT denomination, COUNT(*) FROM churches 
WHERE denomination LIKE 'Roman Catholic%' OR denomination LIKE '%Orthodox%' OR denomination LIKE 'Eastern Catholic%'
GROUP BY denomination ORDER BY COUNT(*) DESC""")
for denom, cnt in c.fetchall():
    print(f"  {denom:<55} {cnt:>6,}")

print("\nCanonical status:")
c.execute("SELECT canonical_status, COUNT(*) FROM churches WHERE canonical_status IS NOT NULL GROUP BY canonical_status ORDER BY COUNT(*) DESC")
for status, cnt in c.fetchall():
    print(f"  {status:<25} {cnt:>6,}")

# Log
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_add_canonical_status.py', TS, TS,
      total, 0, 'denomination,canonical_status', 'completed',
      f'Restructured denominations + added canonical_status column. {total} changes.'))

conn.commit()
conn.close()
print("\nDone!")
