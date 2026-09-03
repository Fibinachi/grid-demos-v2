"""Find and restore the deleted LDS Corp of President record (id=359203)."""
import sqlite3

BACKUPS = [
    (r'E:\grid\churches_pre_bqswap_20260615_081807.db', 'pre_bqswap'),
    (r'E:\grid\churches_gcs_backup.db', 'gcs_backup'),
    (r'E:\grid\churches_recovered_all.db', 'recovered'),
    (r'E:\grid\churches_clean.db', 'clean'),
    (r'E:\grid\churches_clean_snapshot.db', 'clean_snapshot'),
    (r'E:\grid\churches_pre_merge_20260615_084241.db', 'pre_merge1'),
    (r'E:\grid\churches_pre_merge_20260615_084311.db', 'pre_merge2'),
]

# Get current DB column names
curdb = sqlite3.connect(r'E:\grid\churches.db')
cur_cols = [c[1] for c in curdb.execute("PRAGMA table_info(churches)").fetchall()]
curdb.close()
print(f"Current DB has {len(cur_cols)} columns")

for bpath, bname in BACKUPS:
    try:
        db = sqlite3.connect(bpath)
        b_cols = [c[1] for c in db.execute("PRAGMA table_info(churches)").fetchall()]
        cur = db.execute("SELECT * FROM churches WHERE id = 359203")
        r = cur.fetchone()
        if r:
            print(f"\n=== FOUND in: {bname} ({bpath}) ===")
            print(f"  Backup has {len(b_cols)} columns, current has {len(cur_cols)}")
            # Check which current columns exist in this backup
            common = [c for c in cur_cols if c in b_cols]
            missing = [c for c in cur_cols if c not in b_cols]
            print(f"  Common columns: {len(common)}")
            print(f"  Missing from backup: {missing}")
            # Show the data
            for i, val in enumerate(r):
                if val is not None and val != '':
                    print(f"  {b_cols[i]}: {val}")
            db.close()
            break
        db.close()
    except Exception as e:
        print(f"{bname}: {e}")
else:
    print("NOT FOUND in any backup")
