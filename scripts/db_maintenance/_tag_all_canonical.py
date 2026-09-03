"""
Broad canonical_status tagging across all churches, not just monasteries.
"""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()
total = 0

def tag(label, status, where_clause):
    global total
    c.execute(f"UPDATE churches SET canonical_status=? WHERE (canonical_status IS NULL OR canonical_status='') AND ({where_clause})", (status,))
    if c.rowcount > 0:
        print(f"  {label}: {c.rowcount:,}")
        total += c.rowcount

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Diocesan Right — default for Roman Catholic parishes & churches
# ═══════════════════════════════════════════════════════════════════════════════
print("=== Diocesan Right (under local bishop) ===")
tag("Roman Catholic (all)", "diocesan_right",
    "denomination LIKE 'Roman Catholic%'")
tag("Catholic diocese scrape", "diocesan_right",
    "source='catholic_diocese_scrape'")
tag("Catholic by faith+name", "diocesan_right",
    "faith='Christian' AND (LOWER(name) LIKE '%catholic%' OR LOWER(name) LIKE '%diocese%')")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Pontifical Right — exempt religious order houses (already done mostly)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Pontifical Right (exempt orders) ===")
pontifical = [
    ("Franciscan", "LOWER(name) LIKE '%franciscan%'"),
    ("Dominican", "LOWER(name) LIKE '%dominican%' AND LOWER(name) NOT LIKE '%dominican republic%'"),
    ("Benedictine", "LOWER(name) LIKE '%benedictine%'"),
    ("Jesuit", "LOWER(name) LIKE '%jesuit%'"),
    ("Carmelite", "LOWER(name) LIKE '%carmelite%' OR LOWER(name) LIKE '%mount carmel%'"),
    ("Cistercian/Trappist", "LOWER(name) LIKE '%cistercian%' OR LOWER(name) LIKE '%trappist%'"),
    ("Poor Clare", "LOWER(name) LIKE '%poor clare%'"),
    ("Capuchin", "LOWER(name) LIKE '%capuchin%'"),
    ("Augustinian", "LOWER(name) LIKE '%augustinian%'"),
    ("Passionist", "LOWER(name) LIKE '%passionist%'"),
    ("Redemptorist", "LOWER(name) LIKE '%redemptorist%'"),
    ("Salesian", "LOWER(name) LIKE '%salesian%'"),
    ("Oblate", "LOWER(name) LIKE '%oblate%' AND LOWER(name) NOT LIKE '%secular%'"),
    ("Vincentian", "LOWER(name) LIKE '%vincentian%'"),
    ("Marist", "LOWER(name) LIKE '%marist%' AND LOWER(name) NOT LIKE '%marianist%'"),
    ("Servite", "LOWER(name) LIKE '%servite%'"),
    ("Norbertine", "LOWER(name) LIKE '%norbertine%' OR LOWER(name) LIKE '%premonstratensian%'"),
    ("Marianist", "LOWER(name) LIKE '%marianist%'"),
    ("Basilian", "LOWER(name) LIKE '%basilian%'"),
    ("Pauline Fathers", "LOWER(name) LIKE '%pauline father%' OR LOWER(name) LIKE '%pauline monk%'"),
    ("Carthusian", "LOWER(name) LIKE '%carthusian%'"),
    ("Sulpician", "LOWER(name) LIKE '%sulpician%' OR LOWER(name) LIKE '%st. sulpice%'"),
]
for name, where_clause in pontifical:
    tag(f"Pontifical - {name}", "pontifical_right", where_clause)
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Eparchial — Orthodox churches under their bishop
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Eparchial (Orthodox — under bishop) ===")
tag("Eastern Orthodox", "eparchial",
    "denomination LIKE 'Eastern Orthodox%'")
tag("Oriental Orthodox", "eparchial",
    "denomination LIKE 'Oriental Orthodox%'")
tag("Orthodox by name", "eparchial",
    "faith='Christian' AND (LOWER(name) LIKE '%orthodox%' OR LOWER(name) LIKE '%coptic%' OR LOWER(name) LIKE '%armenian apostolic%' OR LOWER(name) LIKE '%ethiopian tewahedo%')")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Eastern Catholic — eparchial (under their eparch/bishop)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Eastern Catholic (under eparch) ===")
tag("Eastern Catholic", "eparchial",
    "denomination LIKE 'Eastern Catholic%' OR LOWER(name) LIKE '%greek catholic%' OR LOWER(name) LIKE '%maronite%' OR LOWER(name) LIKE '%melkite%' OR LOWER(name) LIKE '%syro-malabar%' OR LOWER(name) LIKE '%chaldean catholic%'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Anglican/Episcopal — diocesan
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Anglican/Episcopal (diocesan) ===")
tag("Anglican/Episcopal", "diocesan_right",
    "denomination='Anglican' OR LOWER(name) LIKE '%episcopal church%' OR LOWER(name) LIKE '%anglican church%'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 6. Buddhist — sangha
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Buddhist (sangha) ===")
tag("Buddhist", "sangha",
    "faith='Buddhist'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 7. Lutheran — synodical (under bishop/synod)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Lutheran (synodical) ===")
tag("Lutheran", "synodical",
    "denomination='Lutheran' OR LOWER(name) LIKE '%lutheran%'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 8. Methodist — connexional
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Methodist (connexional) ===")
tag("Methodist", "connexional",
    "denomination='Methodist' OR LOWER(name) LIKE '%methodist%'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 9. Presbyterian — presbyterian
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Presbyterian ===")
tag("Presbyterian", "presbyterian",
    "denomination='Presbyterian' OR LOWER(name) LIKE '%presbyterian%'")
conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n=== Total tagged: {total:,} ===\n")

c.execute("SELECT canonical_status, COUNT(*) FROM churches WHERE canonical_status IS NOT NULL GROUP BY canonical_status ORDER BY COUNT(*) DESC")
for s, cnt in c.fetchall():
    print(f"  {s:<25} {cnt:>10,}")

c.execute("SELECT COUNT(*) FROM churches WHERE canonical_status IS NULL")
null_count = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM churches")
total_churches = c.fetchone()[0]
print(f"\n  NULL                     {null_count:>10,}")
print(f"  ──────────────────────────────────")
print(f"  TOTAL                    {total_churches:>10,}")
print(f"  Coverage: {(total_churches-null_count)/total_churches*100:.1f}%")

conn.close()
