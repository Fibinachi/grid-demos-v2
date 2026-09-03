"""Tag canonical_status for monasteries and religious houses only."""
import sqlite3
conn = sqlite3.connect('churches.db', timeout=30)
c = conn.cursor()
total = 0

def tag_status(label, status, where_clause):
    global total
    c.execute(f"UPDATE churches SET canonical_status=? WHERE (canonical_status IS NULL OR canonical_status='') AND ({where_clause})", (status,))
    if c.rowcount > 0:
        print(f"  {label}: {c.rowcount}")
        total += c.rowcount

# ── Pontifical Right (exempt orders) ────────────────────────────────────────
print("=== Pontifical Right (report directly to Vatican) ===")
tag_status("Franciscan","pontifical_right","LOWER(name) LIKE '%franciscan%'")
tag_status("Dominican","pontifical_right","LOWER(name) LIKE '%dominican%' AND LOWER(name) NOT LIKE '%dominican republic%'")
tag_status("Benedictine","pontifical_right","LOWER(name) LIKE '%benedictine%'")
tag_status("Jesuit","pontifical_right","LOWER(name) LIKE '%jesuit%'")
tag_status("Carmelite","pontifical_right","LOWER(name) LIKE '%carmelite%' OR LOWER(name) LIKE '%mount carmel%'")
tag_status("Cistercian/Trappist","pontifical_right","LOWER(name) LIKE '%cistercian%' OR LOWER(name) LIKE '%trappist%'")
tag_status("Poor Clare","pontifical_right","LOWER(name) LIKE '%poor clare%'")
tag_status("Capuchin","pontifical_right","LOWER(name) LIKE '%capuchin%'")
tag_status("Augustinian","pontifical_right","LOWER(name) LIKE '%augustinian%'")
tag_status("Passionist","pontifical_right","LOWER(name) LIKE '%passionist%'")
tag_status("Redemptorist","pontifical_right","LOWER(name) LIKE '%redemptorist%'")
tag_status("Salesian","pontifical_right","LOWER(name) LIKE '%salesian%'")
tag_status("Oblate","pontifical_right","LOWER(name) LIKE '%oblate%' AND LOWER(name) NOT LIKE '%secular%'")
tag_status("Vincentian","pontifical_right","LOWER(name) LIKE '%vincentian%'")
tag_status("Marist","pontifical_right","LOWER(name) LIKE '%marist%' AND LOWER(name) NOT LIKE '%marianist%'")
tag_status("Servite","pontifical_right","LOWER(name) LIKE '%servite%'")
tag_status("Norbertine","pontifical_right","LOWER(name) LIKE '%norbertine%' OR LOWER(name) LIKE '%premonstratensian%'")
tag_status("Marianist","pontifical_right","LOWER(name) LIKE '%marianist%'")
tag_status("Basilian","pontifical_right","LOWER(name) LIKE '%basilian%'")
tag_status("Pauline","pontifical_right","LOWER(name) LIKE '%pauline father%' OR LOWER(name) LIKE '%pauline monk%'")

# Catholic monastery by denomination
tag_status("Roman Catholic orders","pontifical_right","denomination LIKE 'Roman Catholic (%' AND LOWER(name) LIKE '%monastery%'")

conn.commit()

# ── Diocesan Right ──────────────────────────────────────────────────────────
print("\n=== Diocesan Right (under local bishop) ===")
tag_status("Catholic diocese source","diocesan_right","source='catholic_diocese_scrape' AND LOWER(name) LIKE '%monastery%'")
tag_status("Generic Catholic monastery","diocesan_right","denomination='Roman Catholic' AND LOWER(name) LIKE '%monastery%'")

conn.commit()

# ── Eparchial (Orthodox — under their bishop) ───────────────────────────────
print("\n=== Eparchial (Orthodox monastic — under bishop) ===")
tag_status("Eastern Orthodox","eparchial","denomination LIKE 'Eastern Orthodox%' AND LOWER(name) LIKE '%monastery%'")
tag_status("Oriental Orthodox","eparchial","denomination LIKE 'Oriental Orthodox%' AND LOWER(name) LIKE '%monastery%'")

conn.commit()

# ── Buddhist monastic ───────────────────────────────────────────────────────
print("\n=== Buddhist monastic ===")
tag_status("Buddhist monastery","sangha","faith='Buddhist' AND LOWER(name) LIKE '%monastery%'")

conn.commit()

# ── Final: tag remaining monasteries as unknown ─────────────────────────────
tag_status("Remaining (unknown type)","unknown","LOWER(name) LIKE '%monastery%'")

conn.commit()

print(f"\nTotal tagged: {total}")
c.execute("SELECT canonical_status, COUNT(*) FROM churches WHERE canonical_status IS NOT NULL GROUP BY canonical_status")
for s, cnt in c.fetchall():
    print(f"  {s:<25} {cnt:>6,}")
conn.close()
