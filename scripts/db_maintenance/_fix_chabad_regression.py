"""Fix chabad -> chabad_house regression from NA scan."""
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

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({','.join('?'*len(na_countries))}) AND landmark_type='chabad'", na_countries)
n = c.fetchone()[0]
print(f"Entries with type 'chabad' (should be chabad_house): {n}")

if n:
    c.execute(f"UPDATE churches SET landmark_type='chabad_house' WHERE faith='Judaism' AND country IN ({','.join('?'*len(na_countries))}) AND landmark_type='chabad'", na_countries)
    print(f"Fixed: {c.rowcount}")
    conn.commit()

# Also check for any other normalization issues
for old, new in [('community center', 'community_center'), ('senior home', 'senior_home'), ('temple', 'synagogue')]:
    c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({','.join('?'*len(na_countries))}) AND landmark_type=?", na_countries + (old,))
    n = c.fetchone()[0]
    if n:
        print(f"Found {n} with '{old}'")

# Final check
c.execute(f"SELECT landmark_type, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({','.join('?'*len(na_countries))}) GROUP BY landmark_type ORDER BY COUNT(*) DESC", na_countries)
print("\nFinal type distribution:")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL':20s} {r[1]:>5,}")

conn.close()
