"""Check pastor_name data in local DB"""
import sqlite3, os
db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "churches.db")
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM churches WHERE pastor_name != '' AND pastor_name IS NOT NULL")
count = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM churches")
total = cur.fetchone()[0]
print(f"Local DB: {total:,} total, {count:,} with pastor_name")
if count > 0:
    cur.execute("SELECT pastor_name, name FROM churches WHERE pastor_name != '' LIMIT 5")
    for r in cur.fetchall():
        print(f"  {r[0][:40]:40} | {r[1][:40]}")
else:
    print("Pastor_name column exists but is empty - need to run extract_pastors.py")

# Also check on orchestrator
print("\n--- Checking orchestrator DB ---")
import subprocess
r = subprocess.run(
    ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
     "-i", os.path.expanduser("~/.ssh/grantwizard-key.pem"),
     "ec2-user@18.118.136.255",
     "cd ~/grantwizard && python3 -c \"import sqlite3; conn=sqlite3.connect('churches.db'); cur=conn.cursor(); cur.execute('PRAGMA table_info(churches)'); cols=[c[1] for c in cur.fetchall()]; print(f'Columns: {len(cols)}'); print(f'Has pastor_name: {\"pastor_name\" in cols}'); cur.execute(\\\"SELECT COUNT(*) FROM churches WHERE pastor_name != '' AND pastor_name IS NOT NULL\\\"); print(f'With pastor_name: {cur.fetchone()[0]}'); conn.close()\""],
    capture_output=True, text=True, timeout=15
)
print(r.stdout)
if r.returncode != 0:
    print(f"SSH error: {r.stderr[:200]}")
conn.close()
