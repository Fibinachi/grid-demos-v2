"""Fix remaining monasteries with non-English names."""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()
fixes = 0

# ── French Christian signals ──
french_signals = [
    '%coeur de jesus%', '%sacr% coeur%', '%saint%coeur%',
    '%notre dame%', '%saint-%', '%sainte-%', '%st-%', '%ste-%',
    '%catholique%', '%chretien%', '%chr%tien%',
    '%j%sus%', '%christ%', '%marie%', '%vierge%',
    '%abbaye%', '%prieur%', '%basilique%', '%cathedrale%',
    '%paroisse%', '%eglise%',
]
for pat in french_signals:
    c.execute("""UPDATE churches SET faith='Christian',faith_tradition='Christianity'
        WHERE (faith IS NULL OR faith='') AND LOWER(name) LIKE ?""", (pat,))
    fixes += c.rowcount

# ── Polish / Slavic Christian signals ──
polish_signals = [
    '%cerkiew%',        # Orthodox/Eastern Catholic church
    '%najswietsz%', '%naj%wi%tsz%',  # Most Holy
    '%marii panny%',     # Virgin Mary (Polish)
    '%marii%',           # Mary
    '%bogurodzic%',      # Mother of God (Polish)
    '%za%ni%cia%',       # Dormition
    '%wniebowzi%cia%',   # Assumption
    '%%wi%tego%', '%swietego%', '%%wi%tej%', '%swietej%',  # Saint
    '%%wi%ty%', '%swiety%',     # Saint (masc)
    '%ko%ci%l%', '%kosciol%',  # Church
    '%parafia%',         # Parish
    '%diecezja%',        # Diocese
    '%archidiecezja%',   # Archdiocese
    '%klasztor%',        # Monastery
    '%bazylika%',        # Basilica
    '%katedra%',         # Cathedral
]
for pat in polish_signals:
    c.execute("""UPDATE churches SET faith='Christian',faith_tradition='Christianity'
        WHERE (faith IS NULL OR faith='') AND LOWER(name) LIKE ?""", (pat,))
    fixes += c.rowcount

# ── Greek / Cyrillic signals ──
greek_signals = [
    '%μον%', '%μοναστ%',    # Monastery (moni, monastiri)
    '%εκκλησ%', '%εκκλ%',    # Church (ekklisia)
    '%αγι%', '%αγιο%',        # Saint (agios/agia)
    '%χριστ%',               # Christ
    '%θεοτ%', '%θεοτοκ%',    # Theotokos
    '%παναγ%',               # Panagia (All-Holy = Mary)
    '%καθολικ%',             # Catholic
    '%ορθ%d%',               # Orthodox
    '%ιησο%', '%iησ%',      # Jesus
    '%μητροπολ%',            # Metropolitan
    '%αρχιεπισκ%',           # Archbishop
    '%επισκοπ%',             # Bishop
]
for pat in greek_signals:
    c.execute("""UPDATE churches SET faith='Christian',faith_tradition='Christianity'
        WHERE (faith IS NULL OR faith='') AND LOWER(name) LIKE ?""", (pat,))
    fixes += c.rowcount

# ── Catch-all: anything with "monaster" is overwhelmingly Christian ──
# (already handled above for English, French, Polish, Greek signals)
c.execute("""UPDATE churches SET faith='Christian',faith_tradition='Christianity'
    WHERE (faith IS NULL OR faith='') AND LOWER(name) LIKE '%monaster%'""")
fixes += c.rowcount

conn.commit()
c.execute("SELECT COUNT(*) FROM churches WHERE (faith IS NULL OR faith='') AND LOWER(name) LIKE '%monaster%'")
remaining = c.fetchone()[0]
print(f"Fixes applied: {fixes}")
print(f"Remaining unclassified monasteries: {remaining}")
conn.close()
