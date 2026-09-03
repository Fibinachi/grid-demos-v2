import sqlite3
c = sqlite3.connect('E:/grid/churches.db').cursor()
c.execute("SELECT DISTINCT country FROM churches WHERE source='osm_import' ORDER BY country")
codes = [r[0] for r in c.fetchall()]
print(f"{len(codes)} countries already imported:")
print(' '.join(codes))
with open('E:/grid/_osm_checkpoint.txt', 'w') as f:
    f.write('\n'.join(codes))
print(f"\nCheckpoint saved")
