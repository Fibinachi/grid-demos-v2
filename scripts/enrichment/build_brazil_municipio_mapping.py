"""Build TSE→IBGE municipality mapping using IBGE API."""
import requests, csv, json
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(r'E:\grid\data\election')
DATA_DIR.mkdir(parents=True, exist_ok=True)

def unaccent(text):
    replacements = {
        'á':'a','à':'a','ã':'a','â':'a','ä':'a',
        'é':'e','è':'e','ê':'e','ë':'e',
        'í':'i','ì':'i','î':'i','ï':'i',
        'ó':'o','ò':'o','õ':'o','ô':'o','ö':'o',
        'ú':'u','ù':'u','û':'u','ü':'u',
        'ç':'c',
        'Á':'A','À':'A','Ã':'A','Â':'A','Ä':'A',
        'É':'E','È':'E','Ê':'E','Ë':'E',
        'Í':'I','Ì':'I','Î':'I','Ï':'I',
        'Ó':'O','Ò':'O','Õ':'O','Ô':'O','Ö':'O',
        'Ú':'U','Ù':'U','Û':'U','Ü':'U',
        'Ç':'C',
    }
    for a, p in replacements.items():
        text = text.replace(a, p)
    return text

def normalize(name):
    if not name:
        return ''
    # Remove accents, lowercase
    name = unaccent(name.strip().lower())
    # Normalize apostrophes and quotes
    name = name.replace("'", '').replace('"', '').replace('`', '')
    # Handle Portuguese contractions: "d agua" → "dagua", "d avila" → "davila"
    import re
    name = re.sub(r'\bd\s+(?=[a-z])', 'd', name)
    # Normalize spaces
    name = ' '.join(name.split())
    return name

# STEP 1: Download IBGE municipalities from API
print('Downloading IBGE municipality list...')
ibge_file = DATA_DIR / 'ibge_municipios.json'
if not ibge_file.exists():
    url = 'https://servicodados.ibge.gov.br/api/v1/localidades/municipios'
    resp = requests.get(url, timeout=60, headers={'User-Agent': 'GRID/1.0'})
    data = resp.json()
    with open(ibge_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    print(f'  Saved {len(data)} municipalities')
else:
    with open(ibge_file, encoding='utf-8') as f:
        data = json.load(f)
    print(f'  Loaded {len(data)} municipalities from cache')

# Build: (state_abbrev, normalized_name) → ibge_code
ibge_muns = {}
skipped = 0
for mun in data:
    ibge_id = str(mun['id'])
    name = normalize(mun['nome'])
    # Get UF from the hierarchy: microrregiao > mesorregiao > UF > sigla
    try:
        uf = mun['microrregiao']['mesorregiao']['UF']['sigla']
    except (TypeError, KeyError):
        skipped += 1
        continue
    key = (uf, name)
    if key not in ibge_muns:
        ibge_muns[key] = ibge_id

print(f'  {len(ibge_muns)} unique IBGE municipality names (skipped {skipped} with missing data)')

# STEP 2: Load TSE municipality codes
print('Loading TSE municipality codes...')
tse_file = DATA_DIR / 'municipios-tse.csv'
if not tse_file.exists():
    url = 'https://raw.githubusercontent.com/turicas/eleicoes-brasil/master/data/municipios-tse.csv'
    resp = requests.get(url, timeout=30, headers={'User-Agent': 'GRID/1.0'})
    with open(tse_file, 'w', encoding='utf-8') as f:
        f.write(resp.text)

tse_muns = {}
with open(tse_file, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        uf = row['uf'].strip().upper()
        name = normalize(row['municipio'])
        code = row['codigo'].strip()
        if uf and name and code:
            key = (uf, name)
            if key not in tse_muns:
                tse_muns[key] = code

print(f'  {len(tse_muns)} TSE municipality codes')

# STEP 3: Match by (state, normalized_name)
print('Matching TSE↔IBGE...')

# Build TSE→IBGE mapping
tse_to_ibge = {}
matched = 0
unmatched_ibge = 0
unmatched_tse = 0

# Match TSE→IBGE
for (uf, name), tse_code in tse_muns.items():
    ibge_code = ibge_muns.get((uf, name))
    if ibge_code:
        tse_to_ibge[tse_code] = ibge_code
        matched += 1
    else:
        unmatched_tse += 1

# Count unmatched IBGE
for (uf, name), ibge_code in ibge_muns.items():
    if (uf, name) not in tse_muns:
        unmatched_ibge += 1

print(f'  Matched: {matched:,}')
print(f'  Unmatched TSE: {unmatched_tse}')
print(f'  Unmatched IBGE: {unmatched_ibge}')

# Show some unmatched examples
if unmatched_tse > 0:
    print('\n  Sample unmatched TSE municipalities:')
    count = 0
    for (uf, name), tse_code in tse_muns.items():
        if (uf, name) not in ibge_muns:
            print(f'    {uf} / {name} (TSE={tse_code})')
            count += 1
            if count >= 10:
                break

# STEP 4: Save mapping
mapping_file = DATA_DIR / 'tse_ibge_mapping.json'
tse_to_ibge_simple = {str(k): str(v) for k, v in tse_to_ibge.items()}
with open(mapping_file, 'w') as f:
    json.dump(tse_to_ibge_simple, f)
print(f'\nSaved mapping to {mapping_file} ({len(tse_to_ibge_simple)} entries)')

# Also save the reverse
ibge_to_tse = {str(v): str(k) for k, v in tse_to_ibge.items()}
reverse_file = DATA_DIR / 'ibge_tse_mapping.json'
with open(reverse_file, 'w') as f:
    json.dump(ibge_to_tse, f)
print(f'Saved reverse mapping to {reverse_file} ({len(ibge_to_tse)} entries)')
