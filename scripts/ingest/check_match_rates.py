import sqlite3
cath = sqlite3.connect('E:/grid/data/catholic_directory.db')
us_states = 'AL,AK,AZ,AR,CA,CO,CT,DE,FL,GA,HI,ID,IL,IN,IA,KS,KY,LA,ME,MD,MA,MI,MN,MS,MO,MT,NE,NV,NH,NJ,NM,NY,NC,ND,OH,OK,OR,PA,RI,SC,SD,TN,TX,UT,VT,VA,WA,WV,WI,WY,DC'
rows = cath.execute(f'SELECT directory_year, COUNT(*) as total, SUM(CASE WHEN grid_church_id IS NOT NULL THEN 1 ELSE 0 END) as matched FROM dir_entries WHERE state IN ({chr(39)+chr(39)+us_states.replace(chr(44),chr(39)+chr(39)+chr(44)+chr(39)+chr(39))}) GROUP BY directory_year ORDER BY directory_year').fetchall()
print('US Match rates by year:')
for r in rows:
    pct = 100 * r[2] / r[1] if r[1] > 0 else 0
    print(f'  {r[0]}: {r[2]:,}/{r[1]:,} ({pct:.1f}%)')
cath.close()