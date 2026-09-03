"""Fix remaining normalization issues from NA scan."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

na_countries = ('Canada','MX','Mexico','PR','Puerto Rico',
    'GT','Guatemala','BZ','Belize','SV','El Salvador',
    'HN','Honduras','NI','Nicaragua','CR','Costa Rica','PA','Panama',
    'CU','Cuba','JM','Jamaica','HT','Haiti','DO','Dominican Republic',
    'BS','Bahamas','BB','Barbados','TT','Trinidad and Tobago',
    'GD','Grenada','LC','Saint Lucia','VC','Saint Vincent',
    'DM','Dominica','AG','Antigua','KN','Saint Kitts',
    'VI','Virgin Islands','KY','Cayman Islands',
    'BM','Bermuda','AW','Aruba','CW','Curacao',
    'GL','Greenland','MQ','Martinique','GP','Guadeloupe')

placeholders = ','.join('?' for _ in na_countries)

fixes = {
    'community center': 'community_center',
    'mikvah': 'mikveh',
    'educational centre': 'school',
    'educational program': 'school',
    'community centre': 'community_center',
}

for old_val, new_val in fixes.items():
    c.execute(f"SELECT id, name, landmark_type FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND landmark_type=?", na_countries + (old_val,))
    rows = c.fetchall()
    if rows:
        for row in rows:
            c.execute("UPDATE churches SET landmark_type=? WHERE id=?", (new_val, row[0]))
            c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, 'landmark_type', ?, ?, 'deepseek_na_normalize')",
                      (row[0], old_val, new_val))
        print(f"Fixed {len(rows)}: '{old_val}' -> '{new_val}'")
        conn.commit()

# Also fix odd types
odd_fixes = {
    'community organization': 'organization',
    'outreach organization': 'organization',
    'institution': 'organization',
    'other': 'organization',
}

for old_val, new_val in odd_fixes.items():
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND landmark_type=?", na_countries + (old_val,))
    n = c.fetchone()[0]
    if n:
        c.execute(f"UPDATE churches SET landmark_type=? WHERE faith='Judaism' AND country IN ({placeholders}) AND landmark_type=?", (new_val,) + na_countries + (old_val,))
        print(f"Fixed {c.rowcount}: '{old_val}' -> '{new_val}'")
        conn.commit()

# Final check
c.execute(f"SELECT landmark_type, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) GROUP BY landmark_type ORDER BY COUNT(*) DESC", na_countries)
print("\nFinal type distribution:")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL':25s} {r[1]:>5,}")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({placeholders}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", na_countries)
print(f"\nStill problematic: {c.fetchone()[0]}")

conn.close()
