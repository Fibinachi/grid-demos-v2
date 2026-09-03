"""Parse Catholic Directory using curl.exe subprocess for API calls."""
import re, json, csv, os, subprocess, tempfile, time

OUT = 'data/catholic_directory_1907'

print('Loading...')
ct = open(f'{OUT}/full_text.txt', encoding='utf-8').read()
ct = re.sub(r'-\n([a-z])', r'\1', ct)
sections = [m.end() for m in re.finditer(r'CLERGY,\s*CHURCHES,\s*MISSIONS\s+AND\s+SCHOOLS\.', ct)]
print(f'{len(sections)} sections')

dioceses = []
for ss in sections:
    ctx = ct[max(0, ss-3000):ss]
    h = re.findall(r'((?:ARCH)?DIOCESE)\s+OF\s+([A-Z][A-Z\s.\-\']+?)(?:\.|\n)', ctx, re.IGNORECASE)
    if h:
        dioceses.append(f'{h[-1][0].upper()} OF {h[-1][1].strip().rstrip(".")}')
    else:
        dioceses.append('UNKNOWN')

api_key = os.environ['DEEPSEEK_API_KEY']

system_prompt = "Extract ALL religious institutions from this 1907 Catholic Directory as JSON array. Each object has: name, type (church/school/orphanage/hospital/college/convent/seminary/chapel/home/other), parent_name, parent_type (church/diocese), city, address, religious_order. Output ONLY raw JSON - no markdown."

all_records = []

for i in range(len(sections)):
    text = ct[sections[i]:sections[i+1] if i+1 < len(sections) else len(ct)]
    for m in ['RECAPITULATION', 'RELIGIOUS COMMUNITIES', 'INSTITUTIONS IN CHARGE']:
        p = text.find(m)
        if p > 0: text = text[:p]
    
    dio = dioceses[i]
    print(f'{i+1}/{len(sections)} {dio} ({len(text):,}c)...', end=' ', flush=True)
    
    payload = json.dumps({
        'model': 'deepseek-chat',
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': f'Section {i+1}: {dio}\n\n{text}'}
        ],
        'temperature': 0.01,
        'max_tokens': 8192
    })
    
    # Write payload to temp file (avoids cmdline escaping issues)
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    tmp.write(payload)
    tmp.close()
    
    try:
        result = subprocess.run([
            'curl.exe', '-s', '--max-time', '180',
            '-X', 'POST', 'https://api.deepseek.com/v1/chat/completions',
            '-H', 'Content-Type: application/json',
            '-H', f'Authorization: Bearer {api_key}',
            '-d', f'@{tmp.name}'
        ], capture_output=True, text=True, timeout=200)
        
        if result.returncode != 0:
            print(f'CURL error: {result.stderr[:100]}')
            continue
        
        resp = json.loads(result.stdout)
        content = resp['choices'][0]['message']['content'].strip()
        
        # Strip code fences
        content = re.sub(r'```(?:json)?', '', content).strip()
        
        # Try to parse
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
            print(f'PARSE FAIL - starts: {content[:80]}')
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
    
    except subprocess.TimeoutExpired:
        print('TIMEOUT')
    except Exception as e:
        print(f'ERROR: {e}')
    finally:
        os.unlink(tmp.name)
    
    if i < len(sections) - 1:
        time.sleep(0.3)

print(f'\nTotal: {len(all_records):,} records')
types = {}
for r in all_records:
    t = r.get('type', '?')
    types[t] = types.get(t, 0) + 1
for t, c in sorted(types.items(), key=lambda x: -x[1]):
    print(f'  {t}: {c}')

csv_path = f'{OUT}/institutions_llm.csv'
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['diocese','section','name','type','parent_name','parent_type','city','address','religious_order'], extrasaction='ignore')
    w.writeheader()
    for r in all_records:
        w.writerow(r)
print(f'Saved: {csv_path}')

json_path = f'{OUT}/institutions_llm.json'
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(all_records, f, indent=2, ensure_ascii=False)
print(f'Saved: {json_path}')
print('Done!')
