"""Strip non-religious exempt parcels from FL religious parcels CSV."""
import csv, re
from pathlib import Path

RELIGIOUS_PATTERNS = [
    'CHURCH','CHAPEL','TEMPLE','MOSQUE','SYNAGOGUE','PARISH',
    'DIOCESE','ARCHDIOCESE','EPISCOPATE','SYNOD','PRESBYTERY',
    'MINISTRY','MINISTRIES','FELLOWSHIP','WORSHIP','CONGREGATION',
    'ASSEMBLY OF GOD','TABERNACLE','CATHEDRAL','BASILICA','SHRINE',
    'MONASTERY','CONVENT','ABBEY','PARSONAGE','RECTORY','VICARAGE',
    'BAPTIST','METHODIST','PRESBYTERIAN','LUTHERAN','EPISCOPAL',
    'CATHOLIC','ORTHODOX','PENTECOSTAL','EVANGELICAL','HOLINESS',
    'GOSPEL','ZION','BETHEL','CALVARY','EMMANUEL','EBENEZER',
    'SALVATION ARMY','SEVENTH-DAY ADVENTIST','SDA ','JEHOVAH',
    'LATTER-DAY SAINTS','LDS','MORMON','NAZARENE','WESLEYAN',
    'CHRISTIAN','CHRIST ','MESSIANIC','BIBLE','BIBLICAL',
    'KINGDOM HALL','ISLAMIC','MUSLIM','BUDDHIST','HINDU','SIKH',
    'GURDWARA','JAIN','BAHAI','JUDAISM','JEWISH','HEBREW',
    'ISRAEL','TORAH','RABBINICAL','CHABAD',
    'CONFERENCE ASSOC','CONF ASSOC',
    'MISSIONARY','MISSIONS','MISSION BOARD',
    'CAMP MEETING','RETREAT CENTER',
    'ISKCON','KRISHNA','HARE KRISHNA',
    'THE WAY INTERNATIONAL','CAMPUS CRUSADE',
    'INDEPENDENT BA','INDEPENDENT BAPTIST',
]

def looks_religious(name):
    name = name.upper()
    for pat in RELIGIOUS_PATTERNS:
        if re.search(pat, name):
            return True
    return False

CSV_PATH = Path("E:/grid/data/fl_dor/fl_religious_parcels_2025.csv")

# Read, filter
kept = 0
trashed = 0
rows_keep = []

with open(CSV_PATH, encoding="utf-8") as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames
    for row in reader:
        cat = row.get("religious_category", "")
        if cat in ("church", "parsonage", "religious_auxiliary", "cemetery"):
            rows_keep.append(row)
            kept += 1
        elif looks_religious(row.get("OWN_NAME", "")):
            rows_keep.append(row)
            kept += 1
        else:
            trashed += 1

# Write back
with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows_keep)

from collections import Counter
cats = Counter(r["religious_category"] for r in rows_keep)
print(f"Kept: {kept:,}  |  Trashed: {trashed:,}")
for c, n in cats.most_common():
    print(f"  {c:25s} {n:6,}")
print(f"File size: {CSV_PATH.stat().st_size / (1024*1024):.1f} MB")
