"""Check name columns for JW entries."""
import sqlite3
conn = sqlite3.connect(r'E:\grid\churches.db')
c = conn.cursor()
cols = [r[1] for r in c.execute('PRAGMA table_info(churches)').fetchall()]
print('name-related columns:', [x for x in cols if 'name' in x.lower()])

for col in ['name_original', 'normalized_name', 'name_transliterated']:
    if col in cols:
        filled = c.execute(
            "SELECT COUNT(*) FROM churches WHERE (name LIKE '%Kingdom%Hall%' OR name LIKE '%Jehovah%') "
            f"AND {col} IS NOT NULL AND {col} != ''"
        ).fetchone()[0]
        print(f'  {col}: {filled:,} populated')

# Also check if there's a language column
lang_cols = [x for x in cols if 'lang' in x.lower() or 'language' in x.lower()]
print(f'Language-related columns: {lang_cols}')
conn.close()
