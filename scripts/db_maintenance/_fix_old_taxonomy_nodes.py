"""Fix remaining old taxonomy references + clean up old nodes."""
import sqlite3
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Map old taxonomy IDs → new taxonomy IDs
OLD_TO_NEW = {
    32: 547,   # Conservative → Conservative (Rabbinic)
    33: 541,   # Judaism → Other
    34: 540,   # Karaite → Karaite
    35: 542,   # Orthodox → Orthodox (Rabbinic)
    36: 541,   # Other → Other
    37: 549,   # Reconstructionist → Reconstructionist (Rabbinic)
    38: 548,   # Reform → Reform (Rabbinic)
    235: 542,  # Chabad → Orthodox
    236: 544,  # Hasidic → Orthodox (Hasidic)
    237: 543,  # Jewish (Chabad) → Orthodox (Chabad)
    238: 543,  # Orthodox (Chabad) → Orthodox (Chabad)
    239: 544,  # Orthodox (Hasidic) → Orthodox (Hasidic)
    240: 550,  # Sephardic → Sephardic
    241: 552,  # Humanistic Judaism → Humanistic
    242: 553,  # Jewish → Rabbinic (general)
    243: 541,  # Orthodox Union → Other
}

# Step 1: Reassign any churches still on old nodes
total_fixed = 0
for old_id, new_id in OLD_TO_NEW.items():
    c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=?", (old_id,))
    cnt = c.fetchone()[0]
    if cnt > 0:
        c.execute("UPDATE churches SET taxonomy_id=? WHERE taxonomy_id=?", (new_id, old_id))
        total_fixed += cnt
        print(f"  id={old_id} → {new_id}: {cnt} entries")

print(f"\nTotal reassigned: {total_fixed}")

# Step 2: Reparent old nodes to the new hierarchy so the tree displays correctly
for old_id, new_id in OLD_TO_NEW.items():
    c.execute("UPDATE taxonomy SET parent_id=? WHERE id=?", (new_id, old_id))

print("Old nodes reparented under new hierarchy")

# Step 3: Verify
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
total = c.fetchone()[0]
print(f"\nTotal Judaism: {total:,}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND taxonomy_id IN (32,33,34,35,36,37,38,235,236,237,238,239,240,241,242,243)")
print(f"On old nodes: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND taxonomy_id IS NULL")
print(f"NULL taxonomy_id: {c.fetchone()[0]}")

print("\nFinal taxonomy distribution:")
c.execute("""SELECT t.name, COUNT(*) FROM churches ch 
JOIN taxonomy t ON ch.taxonomy_id = t.id 
WHERE ch.faith='Judaism' 
GROUP BY t.name ORDER BY COUNT(*) DESC""")
for name, cnt in c.fetchall():
    print(f"  {name}: {cnt:,} ({cnt/total*100:.1f}%)")

conn.commit()
conn.close()
print("\nDone.")
