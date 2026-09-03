"""Import denomination directory CSVs into churches DB."""
import csv, json, os, sqlite3, re, sys
from datetime import datetime
from difflib import SequenceMatcher

DB = r'E:\grid\churches.db'
DENOM_DIR = r'E:\grid\data\denom'

files = [
    ('sbc_churches.csv', 'sbc', 'Southern Baptist Convention'),
    ('acna_churches.csv', 'acna', 'Anglican Church in North America'),
]

def jw(s1, s2):
    if not s1 or not s2: return 0.0
    s1, s2 = s1.lower(), s2.lower()
    if s1 == s2: return 1.0
    ls1, ls2 = len(s1), len(s2)
    md = max(ls1, ls2)//2 - 1
    if md < 0: md = 0
    s1m, s2m = [False]*ls1, [False]*ls2
    m = t = 0
    for i in range(ls1):
        for j in range(max(0,i-md), min(i+md+1,ls2)):
            if s2m[j] or s1[i]!=s2[j]: continue
            s1m[i]=s2m[j]=True; m+=1; break
    if m==0: return 0.0
    k=0
    for i in range(ls1):
        if not s1m[i]: continue
        while k<ls2 and not s2m[k]: k+=1
        if k<ls2 and s1[i]!=s2[k]: t+=1
        k+=1
    j = (m/ls1 + m/ls2 + (m-t/2)/m)/3.0
    p = 0
    for i in range(min(ls1,ls2,4)):
        if s1[i]==s2[i]: p+=1
        else: break
    return j + (p*0.1*(1-j))

def clean_name(n):
    n = re.sub(r'[^a-z0-9\s]', '', n.lower())
    return re.sub(r'\s+', ' ', n).strip()

def import_csv(filepath, source_label, default_denom):
    print(f"\n--- {source_label} ({filepath}) ---")
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    print(f"  Records: {len(rows):,}")
    
    db = sqlite3.connect(DB)
    matched = 0
    inserted = 0
    skipped = 0
    
    for row in rows:
        name = (row.get('church_name') or row.get('name') or '').strip()
        city = (row.get('city') or '').strip()
        state = (row.get('state') or '').strip()
        website = (row.get('website') or '').strip()
        phone = (row.get('phone') or '').strip()
        address = (row.get('address') or '').strip()
        denom = (row.get('denomination') or default_denom or '').strip()
        email = (row.get('email') or '').strip()
        pastor = (row.get('pastor') or row.get('clergy') or '').strip()
        
        if not name:
            skipped += 1
            continue
        
        # Try to match by name + city + state
        name_clean = clean_name(name)
        candidates = []
        
        if city and state:
            q = "SELECT id, name, city, state FROM churches WHERE state=? AND city LIKE ?"
            for r in db.execute(q, (state, f'%{city}%')).fetchall():
                score = jw(name_clean, clean_name(r[1]))
                if score > 0.7:
                    candidates.append((score, r[0]))
        else:
            # Name-only match (less precise)
            q = "SELECT id, name FROM churches WHERE name LIKE ?"
            for r in db.execute(q, (f'%{name_clean[:20]}%',)).fetchall():
                score = jw(name_clean, clean_name(r[1]))
                if score > 0.8:
                    candidates.append((score, r[0]))
        
        if candidates:
            # Best match
            candidates.sort(key=lambda x: -x[0])
            cid = candidates[0][1]
            
            # Update existing record
            parts = [f"classification_source='{source_label}'",
                     f"denomination={json.dumps(denom)}",
                     f"denomination_affiliation={json.dumps(denom)}",
                     "last_updated=datetime('now')"]
            if website and website != 'https://www.google.com/maps/place/':
                parts.append(f"website={json.dumps(website)}")
                parts.append("website_source='denom_directory'")
                parts.append("website_confidence=0.80")
            if phone:
                parts.append(f"phone={json.dumps(phone)}")
                parts.append("phone_source='denom_directory'")
            if email:
                parts.append(f"email={json.dumps(email)}")
                parts.append("email_source='denom_directory'")
            if address:
                parts.append(f"address={json.dumps(address)}")
                parts.append("address_source='denom_directory'")
            
            sql = f"UPDATE churches SET {', '.join(parts)} WHERE id=?"
            db.execute(sql, (cid,))
            matched += 1
            
            # Add staff if pastor found
            if pastor:
                existing = db.execute("SELECT COUNT(*) FROM church_staff WHERE church_id=? AND name LIKE ?", 
                                       (cid, f'%{pastor[:20]}%')).fetchone()[0]
                if existing == 0:
                    db.execute("""INSERT INTO church_staff (church_id, name, role, source, confidence)
                                  VALUES (?, ?, 'Pastor', ?, 80)""",
                               (cid, pastor, source_label))
        else:
            skipped += 1
    
    db.commit()
    print(f"  Matched (updated): {matched:,}")
    print(f"  No match (skipped): {skipped:,}")
    db.close()

for fname, label, denom in files:
    fpath = os.path.join(DENOM_DIR, fname)
    if os.path.exists(fpath):
        import_csv(fpath, f'denom_{label}', denom)
    else:
        print(f"File not found: {fpath}")

print("\nDone!")
