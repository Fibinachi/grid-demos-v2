"""Read Ireland charities XLSX - correct parsing."""
import openpyxl

wb = openpyxl.load_workbook(r'E:\grid\data\ireland_charities_register.xlsx', read_only=True, data_only=True)
ws = wb['Public Register']

# Row 1 is metadata, Row 2 is actual header
rows = list(ws.iter_rows(min_row=1, max_row=3, values_only=True))
meta = rows[0]
headers = [str(h).strip() if h else '' for h in rows[1]]
print(f'Meta row: {[m for m in meta if m]}')
print(f'\nColumns ({len(headers)}):')
for i, h in enumerate(headers):
    print(f'  [{i}] {h}')

# Row 3 is first data row
print(f'\nFirst data row:')
for i, v in enumerate(rows[2]):
    if v:
        print(f'  [{i}] {headers[i]}: {str(v)[:80]}')

# Count rows
ws = wb['Public Register']
total = sum(1 for _ in ws.iter_rows(min_row=3, values_only=True))
print(f'\nTotal data rows: {total:,}')

# Religious classification - scan for religious keywords in name (col 1) 
ws = wb['Public Register']
religious_keywords = {
    'Christian/Catholic': ['CATHOLIC', 'ROMAN CATH', 'PARISH', 'DIOCESE', 'ARCHDIOCESE', 'ST ', 'SAINT '],
    'Christian/Protestant': ['CHURCH OF IRELAND', 'PRESBYTERIAN', 'METHODIST', 'BAPTIST', 'LUTHERAN', 'QUAKER'],
    'Christian/Other': ['CHURCH', 'CHAPEL', 'CATHEDRAL', 'MISSION', 'GOSPEL', 'EVANGELICAL', 'PENTECOSTAL'],
    'Islam': ['MOSQUE', 'ISLAMIC', 'MASJID', 'MUSLIM'],
    'Judaism': ['SYNAGOGUE', 'JEWISH', 'SHALOM', 'BETH', 'YESHIVA'],
    'Other': ['HINDU', 'BUDDHIST', 'SIKH', 'GURDWARA', 'TEMPLE'],
}

faith_counts = {}
name_col = 1  # Registered Charity Name
sample_by_faith = {}

for row in ws.iter_rows(min_row=3, values_only=True):
    name = str(row[name_col]).upper() if row[name_col] else ''
    if not name:
        continue
    found = False
    for faith, keywords in religious_keywords.items():
        if any(kw in name for kw in keywords):
            faith_counts[faith] = faith_counts.get(faith, 0) + 1
            if faith not in sample_by_faith:
                sample_by_faith[faith] = []
            if len(sample_by_faith[faith]) < 5:
                sample_by_faith[faith].append(str(row[name_col])[:60])
            found = True
            break
    if not found and ('CHURCH' in name or 'CHRISTIAN' in name or 'GOD' in name):
        faith_counts['Christian/Other'] = faith_counts.get('Christian/Other', 0) + 1

print(f'\nReligious organization counts:')
for faith, cnt in sorted(faith_counts.items(), key=lambda x: -x[1]):
    print(f'  {faith}: {cnt:,}')
    for s in sample_by_faith.get(faith, []):
        print(f'    - {s}')

total_religious = sum(faith_counts.values())
print(f'\nTotal religious: {total_religious:,}')
print(f'Non-religious:   {total - total_religious:,}')

wb.close()
