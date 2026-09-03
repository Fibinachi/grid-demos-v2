"""Download FCC broadcast licensees + match to churches. Proven pattern: download→parse→to_sql→UPDATE FROM."""
import csv, io, os, sqlite3, sys, time, urllib.request, zipfile, re
from datetime import datetime
import pandas as pd

PROJECT = "E:/grid"
DB = os.path.join(PROJECT, "churches.db")
DATA = os.path.join(PROJECT, "data", "fcc")
os.makedirs(DATA, exist_ok=True)

FCC_BASE = "https://transition.fcc.gov/ftp/Bureaus/MB/Databases"
FCC_TIMEOUT = 180
TODAY = datetime.utcnow().strftime("%Y-%m-%d")
NOW = datetime.utcnow().isoformat()
t0 = time.time()

def log(msg):
    print(f"[{time.time()-t0:6.1f}s] {msg}", flush=True)

# ── 1. Download & Parse ──
def download_and_parse(url, label):
    zip_path = os.path.join(DATA, f"{label.lower().replace(' ','_')}.zip")
    log(f"Downloading {label}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=FCC_TIMEOUT) as resp:
            log(f"  HTTP {resp.status}, {resp.length:,} bytes")
            with open(zip_path, 'wb') as f:
                f.write(resp.read())
    except Exception as e:
        log(f"  FAILED: {e}"); return []
    
    records = []
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for name in zf.namelist():
            if 'fac' in name.lower() or 'dat' in name.lower():
                with zf.open(name) as f:
                    text = f.read().decode('latin-1')
                    for row in csv.DictReader(io.StringIO(text), delimiter='|'):
                        records.append(row)
    os.unlink(zip_path)
    log(f"  {len(records):,} records")
    return records

def parse_record(r, stype):
    fid = (r.get('Facility ID','') or r.get('FACILITY_ID','') or '').strip()
    if not fid or fid == '0': return None
    call = (r.get('Call Sign','') or r.get('CALL_SIGN','') or '').strip()
    licensee = (r.get('Licensee','') or r.get('LICENSEE','') or r.get('NAME','') or '').strip()
    addr = (r.get('Address Line 1','') or r.get('ADDRESS_LINE1','') or r.get('STREET','') or '').strip()
    city = (r.get('City','') or r.get('CITY','') or '').strip()
    state = (r.get('State','') or r.get('STATE','') or '').strip()
    zp = (r.get('ZIP','') or r.get('ZIP Code','') or '').strip()
    freq = (r.get('Frequency','') or r.get('FREQUENCY','') or '').strip()
    chan = (r.get('Channel','') or r.get('CHANNEL','') or '').strip()
    comm = (r.get('Community','') or r.get('COMMUNITY','') or '').strip()
    sclass = (r.get('Class','') or r.get('CLASS','') or '').strip()
    status = (r.get('Status','') or r.get('STATUS','') or '').strip()
    try: lat = float(r.get('Latitude','') or r.get('LATITUDE','') or 0)
    except: lat = None
    try: lng = float(r.get('Longitude','') or r.get('LONGITUDE','') or 0)
    except: lng = None
    try: erp = float(r.get('ERP','') or r.get('erp','') or 0)
    except: erp = None
    try: haat = float(r.get('HAAT','') or r.get('haat','') or 0)
    except: haat = None
    
    return {
        'facility_id': fid, 'call_sign': call, 'licensee_name': licensee,
        'address': addr, 'city': city, 'state': state, 'zip': zp,
        'frequency': freq, 'channel': chan, 'community': comm,
        'station_class': sclass, 'status': status,
        'latitude': lat, 'longitude': lng, 'erp_kw': erp, 'haat_m': haat,
        'service_type': stype
    }

# Download all
log("=== Downloading FCC Broadcast Data ===")
all_records = []
for url, label in [
    (f"{FCC_BASE}/fm_fac.zip", "FM"),
    (f"{FCC_BASE}/lpfm_fac.zip", "LPFM"),
    (f"{FCC_BASE}/fm_tv_fac.zip", "FM Translator"),
    (f"{FCC_BASE}/am_fac.zip", "AM"),
]:
    raw = download_and_parse(url, label)
    parsed = [parse_record(r, label) for r in raw]
    all_records.extend([p for p in parsed if p])

# Dedup by facility_id
seen = set()
unique = []
for r in all_records:
    if r['facility_id'] not in seen:
        seen.add(r['facility_id'])
        unique.append(r)
log(f"\nTotal: {len(all_records):,} raw, {len(unique):,} unique facilities")

df_fcc = pd.DataFrame(unique)
log(f"  FM: {(df_fcc['service_type']=='FM').sum():,}")
log(f"  LPFM: {(df_fcc['service_type']=='LPFM').sum():,}")
log(f"  Translator: {(df_fcc['service_type']=='FM Translator').sum():,}")
log(f"  AM: {(df_fcc['service_type']=='AM').sum():,}")

# ── 2. Write to DB ──
log("\nWriting to fcc_broadcast_data table...")
db = sqlite3.connect(DB)
db.execute("PRAGMA synchronous=OFF")

# Create/truncate table
db.execute("DROP TABLE IF EXISTS fcc_broadcast_data")
db.execute("""
    CREATE TABLE fcc_broadcast_data (
        facility_id TEXT PRIMARY KEY, call_sign TEXT, licensee_name TEXT,
        address TEXT, city TEXT, state TEXT, zip TEXT,
        frequency TEXT, channel TEXT, community TEXT,
        station_class TEXT, status TEXT,
        latitude REAL, longitude REAL, erp_kw REAL, haat_m REAL,
        service_type TEXT, created_at TEXT
    )
""")
df_fcc["created_at"] = TODAY
df_fcc.to_sql("fcc_broadcast_data", db, if_exists="append", index=False)
log(f"  {len(df_fcc):,} rows written")

# ── 3. Match to churches ──
log("\nMatching licensees to churches...")
db_load = sqlite3.connect(DB)
churches = pd.read_sql_query("SELECT id, name, address, city, state, zip, latitude, longitude, ein FROM churches WHERE address IS NOT NULL AND address != ''", db_load)
db_load.close()
log(f"  {len(churches):,} churches loaded")

# Normalize for matching
def norm(s):
    return re.sub(r'[^a-z0-9]', '', str(s).lower()) if s else ''

df_fcc['addr_norm'] = df_fcc['address'].apply(norm)
df_fcc['name_norm'] = df_fcc['licensee_name'].apply(norm)
churches['addr_norm'] = churches['address'].apply(norm)
churches['name_norm'] = churches['name'].apply(norm)

# Match by normalized address + state
matches = []
addr_idx = churches.set_index(['addr_norm', 'state'])
name_idx = churches.set_index(['name_norm', 'state'])

for _, fcc in df_fcc.iterrows():
    key = (fcc['addr_norm'], fcc['state'])
    if key in addr_idx.index:
        matches.append({
            'church_id': int(addr_idx.loc[key, 'id']),
            'facility_id': fcc['facility_id'],
            'match_method': 'address',
            'confidence': 0.9
        })
    else:
        # Try name match
        key2 = (fcc['name_norm'], fcc['state'])
        if key2 in name_idx.index:
            matches.append({
                'church_id': int(name_idx.loc[key2, 'id']),
                'facility_id': fcc['facility_id'],
                'match_method': 'name',
                'confidence': 0.7
            })

match_df = pd.DataFrame(matches)
log(f"  {len(match_df):,} matches ({len(match_df[match_df['match_method']=='address']):,} address, {len(match_df[match_df['match_method']=='name']):,} name)")

# ── 4. Write matches via temp table ──
if len(match_df) > 0:
    log("\nWriting org_links...")
    db.execute("""
        CREATE TABLE IF NOT EXISTS org_links (
            church_id INTEGER, linked_type TEXT, linked_id TEXT,
            link_method TEXT, confidence REAL, created_at TEXT,
            PRIMARY KEY (church_id, linked_type, linked_id)
        )
    """)
    
    links = match_df.copy()
    links['linked_type'] = 'fcc_facility'
    links['linked_id'] = links['facility_id']
    links['created_at'] = TODAY
    links = links[['church_id', 'linked_type', 'linked_id', 'match_method', 'confidence', 'created_at']]
    links.columns = ['church_id', 'linked_type', 'linked_id', 'link_method', 'confidence', 'created_at']
    
    links.to_sql("_fcc_links", db, if_exists="replace", index=False)
    db.execute("""
        INSERT OR IGNORE INTO org_links (church_id, linked_type, linked_id, link_method, confidence, created_at)
        SELECT church_id, linked_type, linked_id, link_method, confidence, created_at FROM _fcc_links
    """)
    db.execute("DROP TABLE _fcc_links")
    log(f"  {len(links):,} org_links inserted")

# ── 5. Provenance ──
db.execute("""
    INSERT INTO provenance_log 
    (source, script_name, started_at, completed_at, churches_updated,
     churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, 'completed', ?)
""", ("fcc_broadcast", "download_fcc_broadcast_clean.py", TODAY, TODAY,
      len(match_df) if len(match_df) > 0 else 0, len(df_fcc),
      "fcc_broadcast_data,org_links",
      f"FCC broadcast licensees: {len(df_fcc):,} facilities ({dict(df_fcc['service_type'].value_counts())}). {len(match_df):,} church matches."))

db.commit()

# Stats
fm_count = db.execute("SELECT COUNT(1) FROM fcc_broadcast_data").fetchone()[0]
link_count = db.execute("SELECT COUNT(1) FROM org_links WHERE linked_type='fcc_facility'").fetchone()[0]
total_db = db.execute("SELECT COUNT(1) FROM churches").fetchone()[0]
db.close()

log(f"\n=== DONE in {time.time()-t0:.1f}s ===")
log(f"DB: {total_db:,} churches")
log(f"FCC facilities: {fm_count:,}")
log(f"Church matches: {link_count:,}")
