"""Parse Catholic Directory using only stdlib (urllib)."""
import re, json, csv, os, time, sys
import urllib.request, urllib.error

OUT = 'data/catholic_directory_1907'
API_KEY = os.environ['DEEPSEEK_API_KEY']

def call_api(payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        'https://api.deepseek.com/v1/chat/completions',
        data=data,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}'
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())

print('Loading...', flush=True)
ct = open(f'{OUT}/full_text.txt', encoding='utf-8').read()
ct = re.sub(r'-\n([a-z])', r'\1', ct)
sections = [m.end() for m in re.finditer(r'CLERGY,\s*CHURCHES,\s*MISSIONS\s+AND\s+SCHOOLS\.', ct)]
print(f'{len(sections)} sections', flush=True)

dioceses = []
for ss in sections:
    ctx = ct[max(0, ss-3000):ss]
    h = re.findall(r'((?:ARCH)?DIOCESE)\s+OF\s+([A-Z][A-Z\s.\-\']+?)(?:\.|\n)', ctx, re.IGNORECASE)
    if h:
        dioceses.append(f'{h[-1][0].upper()} OF {h[-1][1].strip().rstrip(".")}')
    else:
        dioceses.append('UNKNOWN')

system_prompt = "Extract ALL religious institutions as JSON array. Each has: name, type (church/school/orphanage/hospital/college/convent/seminary/other), parent_name, parent_type (church/diocese), city, address. Output ONLY raw JSON - no markdown."

all_records = []

for i in range(len(sections)):
    text = ct[sections[i]:sections[i+1] if i+1 < len(sections) else len(ct)]
    for m in ['RECAPITULATION', 'RELIGIOUS COMMUNITIES', 'INSTITUTIONS IN CHARGE']:
        p = text.find(m)
        if p > 0: text = text[:p]
    
    dio = dioceses[i]
    print(f'{i+1}/{len(sections)} {dio} ({len(text):,}c)...', end=' ', flush=True)
    
    payload = {
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'{dio}:\n{text}'}
        ],
        'temperature': 0.01,
        'max_tokens': 8192
    }
    
    try:
        resp = call_api(payload)
        content = resp['choices'][0]['message']['content'].strip()
        content = re.sub(r'```(?:json)?', '', content).strip()
        
        data = None
        try:
            data = json.loads(content)
        except:
            if content.startswith('['):
                last = content.rfind('}')
                if last > 0:
                    try:
                        data = json.loads(content[:last+1] + ']')
                    except:
                        pass
        
        if not data:
            print(f'FAIL')
            continue
        
        if isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list): data = v; break
            else:
                data = [data]
        elif not isinstance(data, list):
            data = [data]
        
        for rec in data:
            rec['diocese'] = dio
            rec['section'] = i+1
        
        all_records.extend(data)
        print(f'{len(data)} records')
    
    except Exception as e:
        print(f'ERR: {e}')
    
    if i < len(sections) - 1:
        time.sleep(0.3)

print(f'\nTotal: {len(all_records):,} records', flush=True)

csv_path = f'{OUT}/institutions_llm.csv'
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['diocese','section','name','type','parent_name','parent_type','city','address','religious_order'], extrasaction='ignore')
    w.writeheader()
    for r in all_records:
        w.writerow(r)
print(f'Saved: {csv_path}', flush=True)

json_path = f'{OUT}/institutions_llm.json'
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(all_records, f, indent=2, ensure_ascii=False)
print(f'Saved: {json_path}', flush=True)
print('Done!', flush=True)
