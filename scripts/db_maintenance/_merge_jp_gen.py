"""Generate INSERT SQL from staging, then use sqlite3 CLI to execute."""
import sqlite3, subprocess, os

stag = sqlite3.connect("E:/grid/jp_shrines.db")
rows = stag.execute("SELECT name, lat, lon, qid FROM shrines").fetchall()
stag.close()

with open("E:/grid/_merge_jp.sql", "w", encoding="utf-8") as f:
    f.write("BEGIN IMMEDIATE;\n")
    for name, lat, lon, qid in rows:
        safe_name = name.replace("'", "''")
        f.write(
            "INSERT OR IGNORE INTO holy_sites"
            "(name,faith,tradition,country,lat,lon,"
            "source_primary,source_secondary,is_landmark,landmark_type,"
            "wikidata_qid,osm_id,confidence_score,website) "
            "VALUES('{}','Shinto',NULL,'JP',{},{},"
            "'wikidata',NULL,1,'shrine','{}',NULL,0.5,NULL);\n".format(
                safe_name, lat, lon, qid)
        )
    f.write("COMMIT;\n")

print("Generated _merge_jp.sql with {} INSERTs".format(len(rows)))

# Try executing with sqlite3 CLI
result = subprocess.run(
    [r"E:\grid\sqlite3_tools\sqlite3.exe", 
     "E:/grid/churches.db", 
     ".read E:/grid/_merge_jp.sql"],
    capture_output=True, text=True, timeout=120
)
print("stdout:", result.stdout[:500] if result.stdout else "(empty)")
print("stderr:", result.stderr[:500] if result.stderr else "(none)")
print("returncode:", result.returncode)
