"""
Restructure denominations into a clean parent-child taxonomy:

  Roman Catholic (Franciscan)
  Roman Catholic (Benedictine)
  Roman Catholic (Jesuit)
  ...
  Eastern Orthodox (Greek)
  Eastern Orthodox (Russian)
  ...
  Oriental Orthodox (Coptic)
  Oriental Orthodox (Armenian)
  ...
  Eastern Catholic (Maronite)
  Eastern Catholic (Melkite)
  ...

Also tag generic "Orthodox" records with the correct branch.
"""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
total = 0

def re_tag(label, new_denom, where_clause):
    global total
    c.execute(f"UPDATE churches SET denomination=? WHERE {where_clause}", (new_denom,))
    if c.rowcount > 0:
        print(f"  {label}: {c.rowcount}")
        total += c.rowcount

# ═══════════════════════════════════════════════════════════════════════════════
# 1. Restructure Catholic orders: "Catholic (X)" → "Roman Catholic (X)"
# ═══════════════════════════════════════════════════════════════════════════════
print("=== Roman Catholic Orders ===")
orders = [
    'Augustinian', 'Basilian', 'Benedictine', 'Capuchin', 'Carmelite',
    'Cistercian', 'Dominican', 'Franciscan', 'Jesuit', 'Marianist',
    'Marist', 'Norbertine/Premonstratensian', 'Oblate', 'Passionist',
    'Pauline', 'Poor Clare', 'Redemptorist', 'Salesian', 'Servite',
    'Vincentian',
]
for order in orders:
    re_tag(f"Catholic → Roman Catholic ({order})",
           f"Roman Catholic ({order})",
           f"denomination='Catholic ({order})'")

# Generic Catholic → Roman Catholic
re_tag("Generic Catholic → Roman Catholic",
       "Roman Catholic",
       "denomination='Catholic'")

# Catholic monastery/diocese source
re_tag("Catholic diocese source → Roman Catholic",
       "Roman Catholic",
       "(denomination IS NULL OR denomination='') AND source='catholic_diocese_scrape' AND faith='Christian'")

# Roman Catholic Church → Roman Catholic
re_tag("Roman Catholic Church → Roman Catholic",
       "Roman Catholic",
       "denomination='Roman Catholic Church'")

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 2. Restructure Eastern Orthodox
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Eastern Orthodox ===")
eo_mappings = [
    ("Eastern Orthodox (Greek)", "denomination='Eastern Orthodox (Greek)'"),
    ("Eastern Orthodox (Russian)", "denomination='Eastern Orthodox (Russian)'"),
    ("Eastern Orthodox (Serbian)", "denomination='Eastern Orthodox (Serbian)'"),
    ("Eastern Orthodox (Romanian)", "denomination='Eastern Orthodox (Romanian)'"),
    ("Eastern Orthodox (Bulgarian)", "denomination='Eastern Orthodox (Bulgarian)'"),
    ("Eastern Orthodox (Ukrainian)", "denomination='Eastern Orthodox (Ukrainian)'"),
    ("Eastern Orthodox (Georgian)", "denomination='Eastern Orthodox (Georgian)'"),
    ("Eastern Orthodox (Antiochian)", "denomination='Eastern Orthodox (Antiochian)'"),
    ("Eastern Orthodox (OCA)", "denomination='Eastern Orthodox (OCA)'"),
    ("Eastern Orthodox (Albanian)", "denomination LIKE '%albanian orthodox%'"),
    ("Eastern Orthodox (Macedonian)", "denomination LIKE '%macedonian orthodox%'"),
]
for new_denom, where_clause in eo_mappings:
    re_tag(f"→ {new_denom}", new_denom, where_clause)

# Tag remaining generic "Orthodox" by name patterns
re_tag("Greek Orthodox → Eastern Orthodox (Greek)", "Eastern Orthodox (Greek)",
       "denomination='Orthodox' AND (LOWER(name) LIKE '%greek orthodox%' OR LOWER(name) LIKE '%hellenic orthodox%')")
re_tag("Russian Orthodox → Eastern Orthodox (Russian)", "Eastern Orthodox (Russian)",
       "denomination='Orthodox' AND LOWER(name) LIKE '%russian orthodox%'")
re_tag("Serbian Orthodox → Eastern Orthodox (Serbian)", "Eastern Orthodox (Serbian)",
       "denomination='Orthodox' AND LOWER(name) LIKE '%serbian orthodox%'")
re_tag("Romanian Orthodox → Eastern Orthodox (Romanian)", "Eastern Orthodox (Romanian)",
       "denomination='Orthodox' AND LOWER(name) LIKE '%romanian orthodox%'")
re_tag("Bulgarian Orthodox → Eastern Orthodox (Bulgarian)", "Eastern Orthodox (Bulgarian)",
       "denomination='Orthodox' AND LOWER(name) LIKE '%bulgarian orthodox%'")
re_tag("Ukrainian Orthodox → Eastern Orthodox (Ukrainian)", "Eastern Orthodox (Ukrainian)",
       "denomination='Orthodox' AND LOWER(name) LIKE '%ukrainian orthodox%'")
re_tag("Antiochian Orthodox → Eastern Orthodox (Antiochian)", "Eastern Orthodox (Antiochian)",
       "denomination='Orthodox' AND LOWER(name) LIKE '%antiochian orthodox%'")

# Greek Orthodox Archdiocese of America → Eastern Orthodox (Greek)
re_tag("GOA → Eastern Orthodox (Greek)", "Eastern Orthodox (Greek)",
       "denomination='Greek Orthodox Archdiocese of America'")
re_tag("OCA → Eastern Orthodox (OCA)", "Eastern Orthodox (OCA)",
       "denomination='Orthodox Church in America'")

# Generic Orthodox → Eastern Orthodox (default remaining)
re_tag("Generic Orthodox → Eastern Orthodox", "Eastern Orthodox",
       "denomination='Orthodox' OR denomination='Eastern Orthodox'")

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 3. Restructure Oriental Orthodox
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Oriental Orthodox ===")
oo_mappings = [
    ("Oriental Orthodox (Coptic)", "denomination='Oriental Orthodox (Coptic)' OR denomination='Coptic Orthodox Church' OR denomination='Coptic Orthodox'"),
    ("Oriental Orthodox (Armenian)", "denomination='Oriental Orthodox (Armenian)' OR denomination LIKE '%armenian orthodox%' OR denomination LIKE '%armenian apostolic%'"),
    ("Oriental Orthodox (Ethiopian)", "denomination='Oriental Orthodox (Ethiopian)' OR denomination='Ethiopian Orthodox Tewahedo Church'"),
    ("Oriental Orthodox (Eritrean)", "denomination='Oriental Orthodox (Eritrean)' OR denomination LIKE '%eritrean orthodox%'"),
    ("Oriental Orthodox (Syriac)", "denomination='Oriental Orthodox (Syriac)' OR denomination LIKE '%syriac orthodox%'"),
    ("Oriental Orthodox (Malankara)", "denomination='Oriental Orthodox (Malankara)' OR denomination LIKE '%malankara orthodox%' OR denomination LIKE '%indian orthodox%'"),
]
for new_denom, where_clause in oo_mappings:
    re_tag(f"→ {new_denom}", new_denom, where_clause)

# Tag Oriental Orthodox by name patterns for NULL-denom records
re_tag("Coptic → Oriental Orthodox (Coptic)", "Oriental Orthodox (Coptic)",
       "(denomination IS NULL OR denomination='') AND LOWER(name) LIKE '%coptic%'")
re_tag("Armenian Apostolic → Oriental Orthodox (Armenian)", "Oriental Orthodox (Armenian)",
       "(denomination IS NULL OR denomination='') AND (LOWER(name) LIKE '%armenian apostolic%' OR LOWER(name) LIKE '%armenian orthodox%')")
re_tag("Ethiopian Tewahedo → Oriental Orthodox (Ethiopian)", "Oriental Orthodox (Ethiopian)",
       "(denomination IS NULL OR denomination='') AND (LOWER(name) LIKE '%ethiopian orthodox%' OR LOWER(name) LIKE '%ethiopian tewahedo%')")

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 4. Restructure Eastern Catholic
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Eastern Catholic ===")
ec_mappings = [
    ("Eastern Catholic (Ukrainian)", "denomination='Eastern Catholic (Ukrainian)' OR LOWER(name) LIKE '%ukrainian greek catholic%'"),
    ("Eastern Catholic (Melkite)", "denomination='Eastern Catholic (Melkite)' OR LOWER(name) LIKE '%melkite%'"),
    ("Eastern Catholic (Maronite)", "denomination='Eastern Catholic (Maronite)' OR LOWER(name) LIKE '%maronite%'"),
    ("Eastern Catholic (Syro-Malabar)", "denomination='Eastern Catholic (Syro-Malabar)' OR LOWER(name) LIKE '%syro-malabar%'"),
    ("Eastern Catholic (Syro-Malankara)", "denomination='Eastern Catholic (Syro-Malankara)' OR LOWER(name) LIKE '%syro-malankara%'"),
    ("Eastern Catholic (Chaldean)", "denomination='Eastern Catholic (Chaldean)' OR LOWER(name) LIKE '%chaldean catholic%'"),
    ("Eastern Catholic (Armenian)", "denomination='Eastern Catholic (Armenian)' OR LOWER(name) LIKE '%armenian catholic%'"),
    ("Eastern Catholic (Ruthenian)", "Eastern Catholic (Ruthenian)", "LOWER(name) LIKE '%ruthenian catholic%' OR LOWER(name) LIKE '%byzantine catholic%'"),
    ("Eastern Catholic (Romanian)", "Eastern Catholic (Romanian)", "LOWER(name) LIKE '%romanian greek catholic%'"),
    ("Eastern Catholic (Hungarian)", "Eastern Catholic (Hungarian)", "LOWER(name) LIKE '%hungarian greek catholic%'"),
    ("Eastern Catholic (Slovak)", "Eastern Catholic (Slovak)", "LOWER(name) LIKE '%slovak greek catholic%'"),
]
for new_denom, where_clause in ec_mappings:
    re_tag(f"→ {new_denom}", new_denom, where_clause)

# Greek Catholic (not Ukrainian etc) → Eastern Catholic
re_tag("Greek Catholic → Eastern Catholic", "Eastern Catholic",
       "denomination='Eastern Catholic' OR LOWER(name) LIKE '%greek catholic%' AND denomination IS NULL")

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# 5. Log
# ═══════════════════════════════════════════════════════════════════════════════
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_restructure_denominations.py', TS, TS,
      total, 0, 'denomination', 'completed',
      f'Restructured {total} denominations into parent-child taxonomy'))

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════════
print(f"\n=== Total restructured: {total} ===\n")

print("Roman Catholic orders:")
c.execute("SELECT denomination, COUNT(*) FROM churches WHERE denomination LIKE 'Roman Catholic%' GROUP BY denomination ORDER BY COUNT(*) DESC")
for denom, cnt in c.fetchall():
    print(f"  {denom:<55} {cnt:>6,}")

print("\nEastern Orthodox:")
c.execute("SELECT denomination, COUNT(*) FROM churches WHERE denomination LIKE 'Eastern Orthodox%' GROUP BY denomination ORDER BY COUNT(*) DESC")
for denom, cnt in c.fetchall():
    print(f"  {denom:<55} {cnt:>6,}")

print("\nOriental Orthodox:")
c.execute("SELECT denomination, COUNT(*) FROM churches WHERE denomination LIKE 'Oriental Orthodox%' GROUP BY denomination ORDER BY COUNT(*) DESC")
for denom, cnt in c.fetchall():
    print(f"  {denom:<55} {cnt:>6,}")

print("\nEastern Catholic:")
c.execute("SELECT denomination, COUNT(*) FROM churches WHERE denomination LIKE 'Eastern Catholic%' GROUP BY denomination ORDER BY COUNT(*) DESC")
for denom, cnt in c.fetchall():
    print(f"  {denom:<55} {cnt:>6,}")

conn.close()
print("\nDone!")
