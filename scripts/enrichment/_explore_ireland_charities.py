"""Explore Ireland's Register of Charities."""
import csv, os, urllib.request, io

CSV_URL = "https://www.charitiesregulator.ie/media/d52jwriz/register-of-charities.csv"

# Try downloading
print("Downloading Register of Charities CSV...")
try:
    req = urllib.request.Request(CSV_URL, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/csv,application/csv',
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        content = resp.read()
    print(f"Downloaded {len(content):,} bytes")
    
    # Read first few lines
    text = content.decode('utf-8-sig')
    lines = text.split('\n')
    print(f"\nHeaders: {lines[0]}")
    print(f"\nFirst 5 rows:")
    for i, line in enumerate(lines[1:6]):
        print(f"  {line[:200]}")
    
    # Save locally
    csv_path = r'E:\grid\data\ireland_charities_register.csv'
    with open(csv_path, 'wb') as f:
        f.write(content)
    print(f"\nSaved to {csv_path}")
    
    # Parse with csv module for column count
    reader = csv.reader(io.StringIO(text))
    headers = next(reader)
    print(f"\nColumn count: {len(headers)}")
    print(f"Columns: {headers}")
    
    # Quick faith categorization
    religious_keywords = ['CHURCH', 'MOSQUE', 'ISLAMIC', 'CATHOLIC', 'BAPTIST', 
                          'METHODIST', 'LUTHERAN', 'EPISCOPAL', 'PRESBYTERIAN',
                          'ORTHODOX', 'PENTECOSTAL', 'EVANGELICAL', 'GOSPEL',
                          'CHRISTIAN', 'SYNAGOGUE', 'TEMPLE', 'HINDU', 'BUDDHIST',
                          'SIKH', 'GURDWARA', 'MASJID', 'CHAPEL', 'CATHEDRAL',
                          'MONASTERY', 'CONVENT', 'PRIORY', 'ABBEY', 'MISSION',
                          'PARISH', 'DIOCESE', 'ARCHDIOCESE', 'MINISTRY',
                          'SALVATION ARMY', 'QUAKER', 'UNITARIAN', 'LDS',
                          'MORMON', 'JEHOVAH', 'CHRISTADELPHIAN', 'MENNONITE',
                          'SHALOM', 'BETH', 'SHUL', 'YESHIVA']
    
    # Check charity name column
    name_col = None
    for i, h in enumerate(headers):
        if 'name' in h.lower() or 'charity' in h.lower():
            name_col = i
            break
    
    if name_col is not None:
        print(f"\nCharity name column: {headers[name_col]} (index {name_col})")
        
        religious = 0
        total_rows = 0
        for row in reader:
            total_rows += 1
            if len(row) > name_col:
                name = row[name_col].upper()
                if any(kw in name for kw in religious_keywords):
                    religious += 1
        
        print(f"\nTotal rows: {total_rows}")
        print(f"Religious-sounding names: {religious}")
    
except Exception as e:
    print(f"Error: {e}")
