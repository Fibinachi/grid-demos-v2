"""Check phone duplicates across different EINs"""
import sqlite3

c = sqlite3.connect('/home/ec2-user/grantwizard/churches.db')

cur = c.execute("SELECT phone, COUNT(DISTINCT ein) as eins, COUNT(*) as records FROM churches WHERE phone != '' AND phone IS NOT NULL AND ein != '' AND ein IS NOT NULL GROUP BY phone HAVING eins > 1 ORDER BY records DESC LIMIT 20")
dupes = cur.fetchall()
print('Phone numbers shared by multiple EINs:')
for phone, eins, records in dupes:
    cur.execute("SELECT id, name, ein FROM churches WHERE phone=? AND ein != '' LIMIT 5", (phone,))
    examples = cur.fetchall()
    print(f'  {phone}: {eins} EINs, {records} records')
    for ex in examples[:3]:
        print(f'    id={ex[0]} name={ex[1][:30]} ein={ex[2]}')

cur.execute("SELECT SUM(eins - 1) FROM (SELECT COUNT(DISTINCT ein) as eins FROM churches WHERE phone != '' AND phone IS NOT NULL AND ein != '' AND ein IS NOT NULL GROUP BY phone HAVING eins > 1)")
total_extra = cur.fetchone()[0] or 0
cur.execute("SELECT COUNT(*) FROM churches WHERE phone != '' AND phone IS NOT NULL")
total_with_phones = cur.fetchone()[0]
print(f'\nTotal extra phone records (beyond 1st EIN): {total_extra}')
print(f'Total records with phones: {total_with_phones}')
