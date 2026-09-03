"""Final verification of taxonomy restructuring"""
import sqlite3
db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

print("=== Christian L2 nodes ===")
c.execute("SELECT id, name, full_path FROM taxonomy WHERE parent_id = 2 ORDER BY id")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id IN (SELECT id FROM taxonomy WHERE full_path LIKE ? || '%')", (r[2],))
    print(f"  ID {r[0]:>3}: {r[1]:20s} — {c.fetchone()[0]:>7,} churches  ({r[2]})")

print("\n=== Restorationist branch ===")
c.execute("SELECT id, name, full_path FROM taxonomy WHERE full_path LIKE 'Christian/Restorationist%' ORDER BY full_path")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = ?", (r[0],))
    print(f"  ID {r[0]:>3}: {r[2]:75s} — {c.fetchone()[0]:>7,}")

print("\n=== Other branch ===")
c.execute("SELECT id, name, full_path FROM taxonomy WHERE full_path LIKE 'Christian/Other%' ORDER BY full_path")
for r in c.fetchall():
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id = ?", (r[0],))
    print(f"  ID {r[0]:>3}: {r[2]:75s} — {c.fetchone()[0]:>7,}")

db.close()
