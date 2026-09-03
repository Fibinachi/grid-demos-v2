"""
Parse 2021 Official Catholic Directory into modern reference table.
Format: N—PARISH NAME, CITY (YEAR) — Address. T: phone. Clergy.

The founded year enables temporal matching: an 1860 clergy record
can only match parishes founded <= 1860.

Usage: python scripts/ingest/parse_2021_directory.py
"""
import re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from gw_db import connect

SRC = Path("E:/grid/data/directories/2021_formatted.txt")

RE_DIOCESE = re.compile(r'^(?:Archdiocese|Diocese)\s+of\s+([A-Za-z\s\-\']+?)(?:,\s*T:.*)?$')
RE_PARISH = re.compile(r'^(\d+)[—\-]\s*(.+?)(?:,\s*(.+?))?\s*\((\d{4})\)')
RE_ADDRESS = re.compile(r'^(.+?),?\s*(\d{5}(?:-\d{4})?)\.?\s*(?:T:|F:|$|Church@|www\.|\.com)')

def parse_2021():
    records = []
    current_diocese = None
    in_parishes = False
    
    with open(SRC, 'r', encoding='utf-8', errors='replace') as f:
        lines = [l.rstrip() for l in f.readlines()]
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Diocese header
        dm = RE_DIOCESE.match(line)
        if dm:
            current_diocese = dm.group(1).strip()
            in_parishes = False
            i += 1
            continue
        
        # Parish entry
        pm = RE_PARISH.match(line)
        if pm and current_diocese:
            in_parishes = True
            num = int(pm.group(1))
            parish_name = pm.group(2).strip()
            city = (pm.group(3) or '').strip()
            year = int(pm.group(4))
            
            # Collect address/clergy lines
            addr_lines = []
            j = i + 1
            while j < len(lines) and j < i + 15:
                nl = lines[j].strip()
                if RE_PARISH.match(nl) or RE_DIOCESE.match(nl):
                    break
                if nl and not re.match(r'^(School|Convent|Legal Name|The Portier|Total)', nl):
                    addr_lines.append(nl)
                j += 1
            
            addr_text = ' '.join(addr_lines)
            
            # Address + ZIP
            am = RE_ADDRESS.search(addr_text)
            address = am.group(1).strip() if am else addr_text[:150]
            zip_code = am.group(2) if am else None
            
            # Phone
            phone = None
            pm2 = re.search(r'T:\s*([\d\-\(\)\s\.]+)', addr_text)
            if pm2: phone = pm2.group(1).strip().rstrip('.')
            
            # Email
            email = None
            em = re.search(r'([\w\.]+@[\w\.]+)', addr_text)
            if em: email = em.group(1)
            
            # Clergy
            clergy = []
            for cm in re.finditer(
                r'(?:Rev(?:s?\.|erend)\s+)?(?:Msgr\.\s+)?(?:Very\s+Rev(?:\.|erend)?\.?\s+)?'
                r'((?:[A-Z][a-z]+(?:\s+[A-Z]\.)*\s+){1,3}[A-Z][a-z]+)',
                addr_text
            ):
                name = cm.group(1).strip()
                skip = ('Legal Name','Mailing Address','The Portier','Parish Office',
                        'School','Corpus Christi','St Dominic','Holy Family',
                        'Cathedral Basilica','St Francis','Immaculate Conception',
                        'Government St','Springhill Ave','McKenna Dr','Burma Rd',
                        'Joyce Rd','Stephens Rd','Conti St','Dauphin Island','Old Loudon',
                        'Rosa Rd','Williams Rd','Hopewell St','Lodge St','Delaware Ave',
                        'Main St','West Winfield','Total Students','Total Assisted',
                        'Total Population','Square Miles')
                if name not in skip and not re.match(r'^\d', name):
                    clergy.append(name)
            
            # Clean city
            if not city:
                cm2 = re.search(r'(?:,\s*)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b', addr_text)
                if cm2: city = cm2.group(1)
            
            records.append({
                'diocese': current_diocese, 'parish_name': parish_name,
                'city': city, 'founded': year,
                'address': address, 'zip': zip_code,
                'phone': phone, 'email': email,
                'clergy': '; '.join(clergy[:5]), 'parish_num': num,
            })
            
            i = j
            continue
        
        i += 1
    
    return records

def main():
    print("Parsing 2021 directory...")
    records = parse_2021()
    print(f"  {len(records)} parishes")
    
    for r in records[:10]:
        print(f"  {r['diocese'][:25]:<27} | {r['parish_name'][:30]:<32} | {str(r['founded']):<6} | {r['city'][:12]:<14} | {r['address'][:50]}")
    
    if records:
        db = connect()
        db.execute("DROP TABLE IF EXISTS catholic_parishes_2021")
        db.execute("""
            CREATE TABLE catholic_parishes_2021 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diocese TEXT, parish_name TEXT, city TEXT,
                founded INTEGER, address TEXT, zip TEXT,
                phone TEXT, email TEXT, clergy TEXT, parish_num INTEGER
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_cp2021_diocese ON catholic_parishes_2021(diocese)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_cp2021_founded ON catholic_parishes_2021(founded)")
        
        db.executemany("""
            INSERT INTO catholic_parishes_2021
            (diocese, parish_name, city, founded, address, zip, phone, email, clergy, parish_num)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, [(r['diocese'], r['parish_name'], r['city'], r['founded'],
               r['address'], r['zip'], r['phone'], r['email'], r['clergy'], r['parish_num'])
              for r in records])
        db.commit()
        
        # Stats
        for r in db.execute("SELECT diocese, COUNT(*) n FROM catholic_parishes_2021 GROUP BY diocese ORDER BY n DESC LIMIT 10").fetchall():
            print(f"  {r[0]:<40} {r[1]:>5}")
        
        total = db.execute("SELECT COUNT(*) FROM catholic_parishes_2021").fetchone()[0]
        pre1900 = db.execute("SELECT COUNT(*) FROM catholic_parishes_2021 WHERE founded <= 1900").fetchone()[0]
        pre1860 = db.execute("SELECT COUNT(*) FROM catholic_parishes_2021 WHERE founded <= 1860").fetchone()[0]
        print(f"\n  Total: {total:,} | Pre-1900: {pre1900:,} | Pre-1860: {pre1860:,}")
        print("  [OK] Done")
        db.close()

if __name__ == '__main__':
    main()
