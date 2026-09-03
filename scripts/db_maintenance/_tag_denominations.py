"""
Tag religious orders and Orthodox traditions with specific denomination names.
Sets denomination column to the specific order/tradition.
"""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()
total = 0

def tag_denom(label, denom_name, where_clause):
    global total
    c.execute(f"UPDATE churches SET denomination=? WHERE (faith='Christian' OR faith IS NULL OR faith='') AND ({where_clause}) AND (denomination IS NULL OR denomination='')", (denom_name,))
    if c.rowcount > 0:
        print(f"  {label}: {c.rowcount}")
        total += c.rowcount

# ═══════════════════════════════════════════════════════════════════════════════
# Catholic Religious Orders
# ═══════════════════════════════════════════════════════════════════════════════
print("=== Catholic Orders ===")
tag_denom("Benedictine", "Catholic (Benedictine)", "LOWER(name) LIKE '%benedictine%' OR (LOWER(name) LIKE '%benedict%' AND LOWER(name) LIKE '%monastery%')")
tag_denom("Franciscan", "Catholic (Franciscan)", "LOWER(name) LIKE '%franciscan%'")
tag_denom("Dominican", "Catholic (Dominican)", "LOWER(name) LIKE '%dominican%' AND LOWER(name) NOT LIKE '%dominican republic%'")
tag_denom("Carmelite", "Catholic (Carmelite)", "LOWER(name) LIKE '%carmelite%' OR (LOWER(name) LIKE '%mount carmel%' AND LOWER(name) LIKE '%monastery%')")
tag_denom("Cistercian/Trappist", "Catholic (Cistercian)", "LOWER(name) LIKE '%cistercian%' OR LOWER(name) LIKE '%trappist%'")
tag_denom("Jesuit", "Catholic (Jesuit)", "LOWER(name) LIKE '%jesuit%' OR LOWER(name) LIKE '%society of jesus%'")
tag_denom("Poor Clare", "Catholic (Poor Clare)", "LOWER(name) LIKE '%poor clare%' OR LOWER(name) LIKE '%poor clares%' OR LOWER(name) LIKE '%st. clare%monastery%'")
tag_denom("Capuchin", "Catholic (Capuchin)", "LOWER(name) LIKE '%capuchin%'")
tag_denom("Augustinian", "Catholic (Augustinian)", "LOWER(name) LIKE '%augustinian%'")
tag_denom("Carthusian", "Catholic (Carthusian)", "LOWER(name) LIKE '%carthusian%'")
tag_denom("Basilian", "Catholic (Basilian)", "LOWER(name) LIKE '%basilian%'")
tag_denom("Norbertine", "Catholic (Norbertine/Premonstratensian)", "LOWER(name) LIKE '%norbertine%' OR LOWER(name) LIKE '%premonstratensian%'")
tag_denom("Servite", "Catholic (Servite)", "LOWER(name) LIKE '%servite%'")
tag_denom("Pauline", "Catholic (Pauline)", "LOWER(name) LIKE '%pauline father%' OR LOWER(name) LIKE '%pauline monk%' OR LOWER(name) LIKE '%order of st paul%' AND LOWER(name) LIKE '%monastery%'")
tag_denom("Passionist", "Catholic (Passionist)", "LOWER(name) LIKE '%passionist%'")
tag_denom("Redemptorist", "Catholic (Redemptorist)", "LOWER(name) LIKE '%redemptorist%'")
tag_denom("Marianist", "Catholic (Marianist)", "LOWER(name) LIKE '%marianist%' OR LOWER(name) LIKE '%society of mary%'")
tag_denom("Vincentian", "Catholic (Vincentian)", "LOWER(name) LIKE '%vincentian%' OR LOWER(name) LIKE '%congregation of the mission%'")
tag_denom("Salesian", "Catholic (Salesian)", "LOWER(name) LIKE '%salesian%' OR LOWER(name) LIKE '%don bosco%'")
tag_denom("Oblate", "Catholic (Oblate)", "LOWER(name) LIKE '%oblate%' AND LOWER(name) NOT LIKE '%secular%'")
tag_denom("Marist", "Catholic (Marist)", "LOWER(name) LIKE '%marist%' AND LOWER(name) NOT LIKE '%marianist%'")
tag_denom("Sulpician", "Catholic (Sulpician)", "LOWER(name) LIKE '%sulpician%' OR LOWER(name) LIKE '%st. sulpice%'")

# Generic Catholic monastery signals
tag_denom("Catholic monastery (generic)", "Catholic", 
    "LOWER(name) LIKE '%monastery%' AND (source='catholic_diocese_scrape' OR LOWER(name) LIKE '%immaculate heart%' OR LOWER(name) LIKE '%sacred heart%' OR LOWER(name) LIKE '%our lady%monastery%' OR LOWER(name) LIKE '%holy cross%monastery%' OR LOWER(name) LIKE '%holy spirit%monastery%' OR LOWER(name) LIKE '%holy ghost%monastery%' OR LOWER(name) LIKE '%holy trinity%monastery%' OR LOWER(name) LIKE '%st. joseph%monastery%')")

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# Orthodox Traditions
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Orthodox Traditions ===")
tag_denom("Greek Orthodox", "Eastern Orthodox (Greek)", "LOWER(name) LIKE '%greek orthodox%' OR LOWER(name) LIKE '%hellenic orthodox%'")
tag_denom("Russian Orthodox", "Eastern Orthodox (Russian)", "LOWER(name) LIKE '%russian orthodox%'")
tag_denom("Serbian Orthodox", "Eastern Orthodox (Serbian)", "LOWER(name) LIKE '%serbian orthodox%'")
tag_denom("Romanian Orthodox", "Eastern Orthodox (Romanian)", "LOWER(name) LIKE '%romanian orthodox%'")
tag_denom("Bulgarian Orthodox", "Eastern Orthodox (Bulgarian)", "LOWER(name) LIKE '%bulgarian orthodox%'")
tag_denom("Ukrainian Orthodox", "Eastern Orthodox (Ukrainian)", "LOWER(name) LIKE '%ukrainian orthodox%'")
tag_denom("Georgian Orthodox", "Eastern Orthodox (Georgian)", "LOWER(name) LIKE '%georgian orthodox%'")
tag_denom("Antiochian Orthodox", "Eastern Orthodox (Antiochian)", "LOWER(name) LIKE '%antiochian orthodox%'")
tag_denom("OCA", "Eastern Orthodox (OCA)", "LOWER(name) LIKE '%orthodox church in america%' OR LOWER(name) LIKE '%oca%' AND LOWER(name) LIKE '%orthodox%'")
tag_denom("Coptic Orthodox", "Oriental Orthodox (Coptic)", "LOWER(name) LIKE '%coptic orthodox%' OR LOWER(name) LIKE '%coptic church%'")
tag_denom("Armenian Apostolic", "Oriental Orthodox (Armenian)", "LOWER(name) LIKE '%armenian apostolic%' OR LOWER(name) LIKE '%armenian orthodox%' OR (LOWER(name) LIKE '%armenian%' AND LOWER(name) LIKE '%church%')")
tag_denom("Syriac Orthodox", "Oriental Orthodox (Syriac)", "LOWER(name) LIKE '%syriac orthodox%'")
tag_denom("Ethiopian Orthodox", "Oriental Orthodox (Ethiopian)", "LOWER(name) LIKE '%ethiopian orthodox%' OR LOWER(name) LIKE '%ethiopian tewahedo%'")
tag_denom("Eritrean Orthodox", "Oriental Orthodox (Eritrean)", "LOWER(name) LIKE '%eritrean orthodox%' OR LOWER(name) LIKE '%eritrean tewahedo%'")
tag_denom("Malankara Orthodox", "Oriental Orthodox (Malankara)", "LOWER(name) LIKE '%malankara orthodox%' OR LOWER(name) LIKE '%indian orthodox%'")

# Eastern Catholic (Byzantine rite Catholics)
tag_denom("Ukrainian Greek Catholic", "Eastern Catholic (Ukrainian)", "LOWER(name) LIKE '%ukrainian greek catholic%' OR LOWER(name) LIKE '%ukrainian catholic%'")
tag_denom("Melkite Greek Catholic", "Eastern Catholic (Melkite)", "LOWER(name) LIKE '%melkite%'")
tag_denom("Maronite", "Eastern Catholic (Maronite)", "LOWER(name) LIKE '%maronite%'")
tag_denom("Syro-Malabar", "Eastern Catholic (Syro-Malabar)", "LOWER(name) LIKE '%syro-malabar%'")
tag_denom("Syro-Malankara", "Eastern Catholic (Syro-Malankara)", "LOWER(name) LIKE '%syro-malankara%'")
tag_denom("Chaldean Catholic", "Eastern Catholic (Chaldean)", "LOWER(name) LIKE '%chaldean catholic%'")
tag_denom("Armenian Catholic", "Eastern Catholic (Armenian)", "LOWER(name) LIKE '%armenian catholic%'")
tag_denom("Greek Catholic (generic)", "Eastern Catholic", "LOWER(name) LIKE '%greek catholic%' AND LOWER(name) NOT LIKE '%ukrainian%' AND LOWER(name) NOT LIKE '%melkite%'")

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# Protestant Denominations
# ═══════════════════════════════════════════════════════════════════════════════
print("\n=== Protestant ===")
tag_denom("Lutheran", "Lutheran", "LOWER(name) LIKE '%lutheran%'")
tag_denom("Anglican/Episcopal", "Anglican", "LOWER(name) LIKE '%anglican%' OR LOWER(name) LIKE '%episcopal church%' AND LOWER(name) NOT LIKE '%methodist%'")
tag_denom("Methodist", "Methodist", "LOWER(name) LIKE '%methodist%'")
tag_denom("Presbyterian", "Presbyterian", "LOWER(name) LIKE '%presbyterian%'")
tag_denom("Baptist", "Baptist", "LOWER(name) LIKE '%baptist%'")
tag_denom("Pentecostal", "Pentecostal", "LOWER(name) LIKE '%pentecostal%' OR LOWER(name) LIKE '%assemblies of god%' OR LOWER(name) LIKE '%assembly of god%'")
tag_denom("Reformed", "Reformed", "LOWER(name) LIKE '%reformed church%' OR LOWER(name) LIKE '%united church of christ%'")
tag_denom("Adventist", "Adventist", "LOWER(name) LIKE '%adventist%' OR LOWER(name) LIKE '%seventh-day%'")
tag_denom("Congregational", "Congregational", "LOWER(name) LIKE '%congregational%' AND LOWER(name) NOT LIKE '%church of christ%'")

conn.commit()

# ═══════════════════════════════════════════════════════════════════════════════
# Log
# ═══════════════════════════════════════════════════════════════════════════════
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_tag_denominations.py', TS, TS,
      total, 0, 'denomination', 'completed',
      f'Tagged {total} records with specific denomination (order/tradition)'))

conn.commit()

print(f"\nTotal denomination tags: {total}")
print("\nDenomination breakdown:")
c.execute("SELECT denomination, COUNT(*) FROM churches WHERE denomination LIKE '%Catholic%' OR denomination LIKE '%Orthodox%' GROUP BY denomination ORDER BY COUNT(*) DESC")
for denom, cnt in c.fetchall():
    print(f"  {str(denom)[:55]:<55} {cnt:>6,}")

conn.close()
print("Done!")
