"""Remove duplicate website records."""
import sqlite3

d = r'E:\grid'
conn = sqlite3.connect(d + '/churches.db')
cur = conn.cursor()

cur.execute("SELECT website, GROUP_CONCAT(id), GROUP_CONCAT(ein), GROUP_CONCAT(email) FROM churches WHERE website != '' AND website IS NOT NULL GROUP BY website HAVING COUNT(*) > 1")
dupes = cur.fetchall()

removed = 0
for website, ids, eins, emails in dupes:
    id_list = ids.split(',')
    ein_list = eins.split(',')
    email_list = emails.split(',')
    
    scores = []
    for i, rid in enumerate(id_list):
        score = 0
        if ein_list[i] and ein_list[i].strip(): score += 10
        if email_list[i] and email_list[i].strip(): score += 5
        scores.append((score, rid))
    
    scores.sort(reverse=True)
    keep_id = scores[0][1]
    
    for rid in id_list:
        if rid != keep_id:
            cur.execute('DELETE FROM churches WHERE id = ?', (rid,))
            removed += 1

conn.commit()
print(f'Removed: {removed} duplicate records')
cur.execute('SELECT COUNT(*) FROM churches')
print(f'Total: {cur.fetchone()[0]:,}')
conn.close()
