#!/usr/bin/env python3
"""
Import ALL 1865 dioceses via DeepSeek.
Stores results in memory, writes to DB after all API calls complete.
"""
import os, re, json, requests, time, sys, sqlite3
from pathlib import Path

DB_PATH = Path("E:/grid/data/catholic_directory.db")
DIR_YEAR = 1865
key = os.environ["DEEPSEEK_API_KEY"]
CHUNK_SIZE = 500

prompt = "Extract ALL parish and institution entries from this 1865 Catholic directory section. Return JSON array with keys: church_name, entity_type, city, state, clergy (array of {name, title}). Classify entity_type as: parish, cathedral, mission, chapel, school, cemetery, hospital, convent, seminary, or other. Return ONLY valid JSON array, no markdown fences."

# ── Load & split text ──
print("Loading text...")
text = open("E:/grid/data/directories/catholic_dir_1865.txt", errors="ignore").read()
print(f"  {len(text):,} chars")

pattern = r'(?:ARCHDIOCESE|DIOCESE)\s+OF\s+([A-Z][A-Z\s\-\']+?)(?:\.|\s*\n)'
ams = []
for m in re.finditer(pattern, text):
    n = m.group(1).strip().rstrip('.'); p = m.start()
    if len(n) < 3: continue
    if any(w in n.lower() for w in ['street','avenue','road','lane','square','liberty','broadway','wall','park','place']): continue
    ams.append((n, p))

can = {}
for n, p in ams:
    kn = n.upper().strip()
    if kn == 'PHILADELPHTA': kn = 'PHILADELPHIA'
    if kn == 'SANTA FR': kn = 'SANTA FE'
    if kn == 'SAUT-SAINTE-MARIE': kn = 'SAULT STE. MARIE'
    if kn == 'NEW-YORK': kn = 'NEW YORK'
    if kn == 'NEW-ORLEANS': kn = 'NEW ORLEANS'
    if kn == 'ERI': kn = 'ERIE'
    if kn == 'KINGSTON' and p > 700000: kn = 'KINGSTON (CA)'
    if kn == 'THREE RIVERS': kn = 'TROIS-RIVIERES'
    if kn == 'HARBOR GRACE': kn = 'HARBOUR GRACE'
    if kn not in can: can[kn] = p

sd = sorted(can.items(), key=lambda x: x[1])
sections = []
for i, (name, start) in enumerate(sd):
    end = sd[i+1][1] if i+1 < len(sd) else min(start + 60000, len(text))
    sections.append({"name": name, "text": text[start:end]})

print(f"  {len(sections)} diocese sections")

# ── Process all dioceses, store results in memory ──
all_entries = []  # list of tuples for DB insert
entry_idx = 0
type_counts = {}

print(f"\nProcessing {len(sections)} dioceses via DeepSeek...")
for i, sec in enumerate(sections):
    name = sec["name"]
    clean = re.sub(r'\s+', ' ', sec["text"]).strip()[:8000]
    
    if len(clean) < 200:
        print(f"  [{i+1}/{len(sections)}] {name:30s} SKIP ({len(clean)} chars)")
        continue
    
    print(f"  [{i+1}/{len(sections)}] {name:30s} ({len(clean):,} chars) ...", flush=True)
    
    t0 = time.time()
    try:
        r = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={
                'model': 'deepseek-chat',
                'messages': [
                    {'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': clean}
                ],
                'temperature': 0.05,
                'max_tokens': 8000
            },
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            timeout=60
        )
        elapsed = time.time() - t0
        
        if r.status_code != 200:
            print(f"HTTP {r.status_code} ({elapsed:.1f}s)")
            continue
        
        content = r.json()['choices'][0]['message']['content']
        c2 = content.strip()
        c2 = re.sub(r'^```(?:json)?\s*\n?', '', c2)
        c2 = re.sub(r'\n?```\s*$', '', c2)
        
        s = c2.find('[')
        if s < 0:
            print(f"No JSON found ({elapsed:.1f}s)")
            continue
        
        depth = 0
        parsed = None
        for j in range(s, len(c2)):
            if c2[j] == '[': depth += 1
            elif c2[j] == ']':
                depth -= 1
                if depth == 0:
                    parsed = json.loads(c2[s:j+1])
                    break
        
        if not parsed:
            print(f"Incomplete JSON ({elapsed:.1f}s)")
            continue
        
        n_entries = len(parsed)
        print(f"OK {n_entries} entries ({elapsed:.1f}s)")
        
        for entry in parsed:
            ename = (entry.get("church_name") or "").strip()
            if not ename: continue
            etype = entry.get("entity_type", "parish")
            city = (entry.get("city") or "").strip()
            state = (entry.get("state") or "").strip()
            address = (entry.get("address") or "").strip()
            notes_val = (entry.get("notes") or "").strip()
            clergy_list = entry.get("clergy", [])
            yf = entry.get("year_founded")
            
            type_counts[etype] = type_counts.get(etype, 0) + 1
            
            all_entries.append((
                DIR_YEAR, f"{name}_{entry_idx}", ename,
                city or None, state or None, name, etype,
                address or None, None, None, None, None,
                yf, None, None,
                notes_val + " [1865 Sadlier's]",
                json.dumps(entry, ensure_ascii=False),
                json.dumps(clergy_list, ensure_ascii=False),  # store clergy as JSON
            ))
            entry_idx += 1
        
    except Exception as e:
        elapsed = time.time() - t0
        print(f"Err: {e} ({elapsed:.1f}s)")
    
    time.sleep(0.3)

print(f"\nTotal entries collected: {len(all_entries):,}")

# ── Write to DB ──
print("\nWriting to database...")
conn = sqlite3.connect(str(DB_PATH))
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA foreign_keys=OFF")
conn.execute("PRAGMA synchronous=OFF")

# Clear old
conn.execute("DELETE FROM dir_contacts WHERE entry_id IN (SELECT id FROM dir_entries WHERE directory_year=?)", (DIR_YEAR,))
conn.execute("DELETE FROM dir_clergy WHERE directory_year=?", (DIR_YEAR,))
conn.execute("DELETE FROM dir_bishops WHERE directory_year=?", (DIR_YEAR,))
conn.execute("DELETE FROM dir_entries WHERE directory_year=?", (DIR_YEAR,))
conn.execute("DELETE FROM dir_provenance WHERE source LIKE 'catholic_dir_1865%'", ())
conn.commit()

# Insert entries + clergy
total_clergy = 0
for chunk_start in range(0, len(all_entries), CHUNK_SIZE):
    chunk = all_entries[chunk_start:chunk_start + CHUNK_SIZE]
    # Insert entries
    entry_data = [e[:-1] for e in chunk]  # strip clergy JSON
    conn.executemany("""INSERT INTO dir_entries (directory_year, source_entry_id, name, city,
        state, diocese, entity_type, address, zip, phone, website, email,
        year_founded, landmark_type, grid_church_id, notes, source_raw)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", entry_data)
    
    # Get IDs and insert clergy
    for e in chunk:
        source_key = e[1]  # source_entry_id
        clergy_json = e[17]  # last element is clergy JSON
        if clergy_json:
            clergy_list = json.loads(clergy_json)
            real_eid = conn.execute(
                "SELECT id FROM dir_entries WHERE source_entry_id=? AND directory_year=?",
                (source_key, DIR_YEAR)
            ).fetchone()
            if real_eid:
                for c in clergy_list:
                    cname = (c.get("name") or "").strip()
                    ctitle = (c.get("title") or "").strip()
                    if cname:
                        conn.execute(
                            "INSERT INTO dir_clergy (entry_id, directory_year, name, role) VALUES (?,?,?,?)",
                            (real_eid[0], DIR_YEAR, cname, ctitle)
                        )
                        total_clergy += 1
    conn.commit()

# Hierarchy
print("Looking for hierarchy section...")
for pat in ["CARDINALS, ARCHBISHOPS, BISHOPS", "THE HIERARCHY", "HIERARCHY OF THE CATHOLIC CHURCH"]:
    idx = text.find(pat)
    if idx > 0 and idx < len(text) * 0.4:
        hier = re.sub(r'\s+', ' ', text[idx:idx+30000]).strip()[:12000]
        print(f"  Found '{pat}' at pos {idx:,}, parsing...")
        try:
            r = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                json={
                    'model': 'deepseek-chat',
                    'messages': [
                        {'role': 'system', 'content': "Extract ALL bishops from this 1865 hierarchy listing. Return JSON array with: name, title, diocese, bishop_type, consecrated, birth_year, notes. Return ONLY valid JSON array."},
                        {'role': 'user', 'content': hier}
                    ],
                    'temperature': 0.05, 'max_tokens': 8000
                },
                headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                timeout=60
            )
            if r.status_code == 200:
                c2 = r.json()['choices'][0]['message']['content'].strip()
                c2 = re.sub(r'^```(?:json)?\s*\n?', '', c2)
                c2 = re.sub(r'\n?```\s*$', '', c2)
                s = c2.find('[')
                if s >= 0:
                    depth = 0
                    for j in range(s, len(c2)):
                        if c2[j] == '[': depth += 1
                        elif c2[j] == ']':
                            depth -= 1
                            if depth == 0:
                                bishops = json.loads(c2[s:j+1])
                                for b in bishops:
                                    conn.execute("""INSERT INTO dir_bishops (directory_year, name, title, diocese,
                                        bishop_type, status, consecrated_year, birth_year, notes, source_raw)
                                        VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                                        DIR_YEAR, b.get("name",""), b.get("title","") or None,
                                        b.get("diocese","") or None, b.get("bishop_type","") or None,
                                        "historical", b.get("consecrated"), b.get("birth_year"),
                                        b.get("notes","") or None, json.dumps(b, ensure_ascii=False)))
                                print(f"  Imported {len(bishops)} bishops")
                                break
        except Exception as e:
            print(f"  Hierarchy error: {e}")
        break

# Provenance
entry_count = conn.execute("SELECT COUNT(*) FROM dir_entries WHERE directory_year=?", (DIR_YEAR,)).fetchone()[0]
clergy_count = conn.execute("SELECT COUNT(*) FROM dir_clergy WHERE directory_year=?", (DIR_YEAR,)).fetchone()[0]
bishop_count = conn.execute("SELECT COUNT(*) FROM dir_bishops WHERE directory_year=?", (DIR_YEAR,)).fetchone()[0]
conn.execute("""INSERT INTO dir_provenance (source, description, entry_count, clergy_count, bishop_count)
    VALUES (?,?,?,?,?)""", ("catholic_dir_1865", f"1865 Sadlier's Catholic Directory — {entry_count:,} entries", entry_count, clergy_count, bishop_count))
conn.execute("PRAGMA foreign_keys=ON")
conn.commit()

print(f"\n{'='*60}")
print(f"1865 Import Complete")
print(f"{'='*60}")
print(f"  Dioceses:  {len(sections)}")
print(f"  Entries:   {entry_count:,}")
print(f"  Clergy:    {clergy_count:,}")
print(f"  Bishops:   {bishop_count:,}")
print(f"\nEntity types:")
for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
    print(f"  {t:25s} {c:>8,}")

conn.close()
print("Done.")
