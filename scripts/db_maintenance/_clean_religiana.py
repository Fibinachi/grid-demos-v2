"""Clean up Religiana entries for a fresh start."""
import sqlite3

conn = sqlite3.connect('E:/grid/churches.db')
c = conn.cursor()
c.execute("DELETE FROM churches WHERE source='religiana'")
c.execute("DELETE FROM church_sources WHERE source_name='religiana'")
conn.commit()
c.execute("SELECT COUNT(*) FROM churches WHERE source='religiana'")
remaining = c.fetchone()[0]
print(f'Cleaned up. Remaining religiana entries: {remaining}')
conn.close()
