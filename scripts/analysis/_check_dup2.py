"""Compare duplicates more carefully."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

for id_ in [2324230, 3718835]:
    c.execute("SELECT id, name, name_transliterated, name_original, faith, tradition, city, state, country, latitude, longitude, landmark_type FROM churches WHERE id=?", (id_,))
    r = c.fetchone()
    print(f"=== ID {id_} ===")
    print(f"  Name:      {r[1]}")
    print(f"  Translit:  {r[2]}")
    print(f"  Original:  {r[3]}")
    print(f"  Faith:     {r[4]}")
    print(f"  Tradition: {r[5]}")
    print(f"  City:      {r[6]}")
    print(f"  State:     {r[7]}")
    print(f"  Country:   {r[8]}")
    print(f"  GPS:       {r[9]}, {r[10]}")
    print(f"  Type:      {r[11]}")
    print()

conn.close()
