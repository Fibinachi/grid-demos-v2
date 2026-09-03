"""
Assess the deleted RC diocese corporation records — what data did they have?
Check ALL backup DBs.
"""
import sqlite3

DB = r'E:\grid\churches.db'
BACKUPS = [
    r'E:\grid\churches_pre_bqswap_20260615_081807.db',
    r'E:\grid\churches_gcs_backup.db',
    r'E:\grid\churches_recovered_all.db',
    r'E:\grid\churches_clean.db',
    r'E:\grid\churches_clean_snapshot.db',
    r'E:\grid\churches_pre_merge_20260615_084241.db',
    r'E:\grid\churches_pre_merge_20260615_084311.db',
]
STATE_MAP = {'ON': 'CA', 'QC': 'CA', 'BC': 'CA', 'AB': 'CA', 'SK': 'CA', 'MB': 'CA',
             'NS': 'CA', 'NB': 'CA', 'NL': 'CA', 'PE': 'CA', 'YT': 'CA', 'NT': 'CA', 'NU': 'CA'}

corp_patterns = [
    ('RC Diocese', '%ROMAN CATHOLIC EPISCOPAL CORPORATION%'),
    ('RC Diocese (The)', '%THE ROMAN CATHOLIC EPISCOPAL CORPORATION%'),
    ('Catholic Episcopal', '%CATHOLIC EPISCOPAL CORPORATION%'),
    ('Episcopal Corp', '%EPISCOPAL CORPORATION OF%'),
    ('LDS Presiding', '%CORPORATION OF THE PRESIDING BISHOP%'),
    ('LDS President', '%CORPORATION OF THE PRESIDENT%'),
]

for bpath in BACKUPS:
    try:
        bdb = sqlite3.connect(bpath)
        # Check schema
        cur = bdb.execute("PRAGMA table_info(churches)")
        cols = [c[1] for c in cur.fetchall()]
        print(f"\n=== {bpath} ({len(cols)} cols) ===")
        for label, pat in corp_patterns:
            cur = bdb.execute(f"SELECT COUNT(*) FROM churches WHERE name LIKE ?", (pat,))
            cnt = cur.fetchone()[0]
            if cnt:
                print(f"  {label}: {cnt} records")
                # Show a sample
                cur = bdb.execute(f"SELECT * FROM churches WHERE name LIKE ? LIMIT 1", (pat,))
                row = cur.fetchone()
                rdata = dict(zip(cols, row))
                nonnull = {k: v for k, v in rdata.items() if v is not None and str(v).strip() != '' and str(v).strip() != '0'}
                print(f"    Sample non-null: name={nonnull.get('name','')[:60]}")
                for k, v in sorted(nonnull.items()):
                    if k not in ('id', 'name'):
                        print(f"      {k}: {v}")
        bdb.close()
    except Exception as e:
        print(f"\n=== {bpath}: ERROR {e} ===")
