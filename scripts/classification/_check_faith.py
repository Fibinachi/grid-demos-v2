import sqlite3
db = sqlite3.connect('churches.db')

# NULL/empty faith
null_faith = db.execute("SELECT COUNT(*) FROM churches WHERE faith IS NULL OR faith = ''").fetchone()[0]
print(f'NULL/empty faith: {null_faith}')

# NULL tradition  
null_trad = db.execute('SELECT COUNT(*) FROM churches WHERE tradition IS NULL').fetchone()[0]
print(f'NULL tradition: {null_trad:,}')

# Generic tradition
generic = ['Christian','Muslim','Jewish','Hindu','Buddhist','Sikh','Jain','Taoist','Shinto','Bahai','Other']
ph = ','.join(['?']*len(generic))
gen_trad = db.execute(f'SELECT COUNT(*) FROM churches WHERE tradition IN ({ph})', generic).fetchone()[0]
print(f'Generic tradition: {gen_trad:,}')
print(f'Total unclassified (null + generic): {null_trad + gen_trad:,}')

# Non-Religious count
nr = db.execute("SELECT COUNT(*) FROM churches WHERE faith='Non-Religious'").fetchone()[0]
print(f'\nNon-Religious: {nr:,}')

db.close()
