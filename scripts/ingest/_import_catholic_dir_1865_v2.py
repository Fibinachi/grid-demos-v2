#!/usr/bin/env python3
"""
Import 1865 Catholic Directory — streamlined version built from working test.
Processes each diocese via DeepSeek and writes to catholic_directory.db.
"""
import os, re, json, requests, time, sys, sqlite3
from pathlib import Path

DB_PATH = Path("E:/grid/data/catholic_directory.db")
DIR_TEXT = Path("E:/grid/data/directories/catholic_dir_1865.txt")
DIR_YEAR = 1865
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
CHUNK_SIZE = 500

PARISH_PROMPT = "Extract ALL parish and institution entries from this 1865 Catholic directory section. Return JSON array with keys: church_name, entity_type, city, state, clergy (array of {name, title}). Return ONLY valid JSON array, no markdown fences."

HIERARCHY_PROMPT = """Extract ALL bishops, archbishops, and cardinals from this 1865 US Catholic hierarchy listing.
Return JSON array: [{"name":"...","title":"Bishop of X","diocese":"...","bishop_type":"BISHOP|ARCHBISHOP|CARDINAL","consecrated":18..,"birth_year":18..,"notes":"..."}]
Extract EVERY bishop. Return ONLY valid JSON array, no markdown fences."""


def call_api(prompt, text_chunk):
    """Call DeepSeek and return parsed JSON."""
    try:
        r = requests.post(
            'https://api.deepseek.com/v1/chat/completions',
            json={
                'model': 'deepseek-chat',
                'messages': [
                    {'role': 'system', 'content': prompt},
                    {'role': 'user', 'content': text_chunk}
                ],
                'temperature': 0.05,
                'max_tokens': 8000
            },
            headers={'Authorization': f'Bearer {DEEPSEEK_KEY}', 'Content-Type': 'application/json'},
            timeout=60
        )
        if r.status_code != 200:
            print(f"HTTP {r.status_code}")
            return None

        content = r.json()['choices'][0]['message']['content']
        cleaned = content.strip()
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
        cleaned = re.sub(r'\n?```\s*$', '', cleaned)

        for sc, ec in [('[', ']'), ('{', '}')]:
            s = cleaned.find(sc)
            if s >= 0:
                depth = 0
                for j in range(s, len(cleaned)):
                    if cleaned[j] == sc: depth += 1
                    elif cleaned[j] == ec:
                        depth -= 1
                        if depth == 0:
                            return json.loads(cleaned[s:j+1])
        return None
    except json.JSONDecodeError:
        return None
    except Exception as e:
        print(f"Err:{e}")
        return None


def find_diocese_sections(text):
    """Split text into per-diocese sections."""
    pattern = r'(?:ARCHDIOCESE|DIOCESE)\s+OF\s+([A-Z][A-Z\s\-\']+?)(?:\.|\s*\n)'
    all_matches = []
    for m in re.finditer(pattern, text):
        name = m.group(1).strip().rstrip('.')
        pos = m.start()
        if len(name) < 3: continue
        if any(w in name.lower() for w in ['street','avenue','road','lane','square','liberty','broadway','wall','park','place']): continue
        if pos > 0 and text[pos-1:pos].strip() and text[pos-1].islower(): continue
        all_matches.append((name, pos))

    # Canonicalize: first occurrence only
    canonical = {}
    for name, pos in all_matches:
        kn = name.upper().strip()
        if kn == 'PHILADELPHTA': kn = 'PHILADELPHIA'
        if kn == 'SANTA FR': kn = 'SANTA FE'
        if kn == 'SAUT-SAINTE-MARIE': kn = 'SAULT STE. MARIE'
        if kn == 'NEW-YORK': kn = 'NEW YORK'
        if kn == 'NEW-ORLEANS': kn = 'NEW ORLEANS'
        if kn == 'ERI': kn = 'ERIE'
        if kn == 'KINGSTON' and pos > 700000: kn = 'KINGSTON (CA)'
        if kn == 'THREE RIVERS': kn = 'TROIS-RIVIERES'
        if kn == 'HARBOR GRACE': kn = 'HARBOUR GRACE'
        if kn == 'NATICHITOCHES' or kn == 'NATCHITOCHES': kn = 'NATCHITOCHES'
        if kn not in canonical: canonical[kn] = pos

    sd = sorted(canonical.items(), key=lambda x: x[1])
    sections = []
    for i, (name, start) in enumerate(sd):
        end = sd[i+1][1] if i+1 < len(sd) else min(start + 60000, len(text))
        sections.append({"name": name, "text": text[start:end]})
    return sections


def main():
    if not DEEPSEEK_KEY:
        print("DEEPSEEK_API_KEY not set!")
        return

    # Load text
    print("Loading 1865 directory text...")
    text = DIR_TEXT.read_text(encoding="utf-8", errors="ignore")
    print(f"  {len(text):,} chars")

    # Find sections
    sections = find_diocese_sections(text)
    print(f"  {len(sections)} diocese sections found")

    # Connect to DB
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("PRAGMA synchronous=OFF")

    # Clear old 1865 data
    print("Clearing existing 1865 data...")
    conn.execute("DELETE FROM dir_contacts WHERE entry_id IN (SELECT id FROM dir_entries WHERE directory_year=?)", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_clergy WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_bishops WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_entries WHERE directory_year=?", (DIR_YEAR,))
    conn.execute("DELETE FROM dir_provenance WHERE source LIKE 'catholic_dir_1865%'", ())
    conn.commit()

    # Process each diocese
    total_entries = 0
    total_clergy = 0
    type_counts = {}
    batch_entries = []
    batch_clergy = []
    entry_idx = 0

    print(f"\nProcessing {len(sections)} dioceses via DeepSeek...")
    for i, sec in enumerate(sections):
        name = sec["name"]
        sec_clean = re.sub(r'\s+', ' ', sec["text"]).strip()[:8000]

        if len(sec_clean) < 200:
            print(f"  [{i+1}/{len(sections)}] {name:30s} SKIP (too short: {len(sec_clean)} chars)")
            continue

        sys.stdout.write(f"  [{i+1}/{len(sections)}] {name:30s} ({len(sec_clean):,} chars) ... ")
        sys.stdout.flush()

        t0 = time.time()
        result = call_api(PARISH_PROMPT, sec_clean)
        elapsed = time.time() - t0

        if result and isinstance(result, list):
            n = len(result)
            print(f"OK {n} entries ({elapsed:.1f}s)")
            for entry in result:
                ename = (entry.get("church_name") or "").strip()
                if not ename: continue
                etype = entry.get("entity_type", "parish")
                city = (entry.get("city") or "").strip()
                state = (entry.get("state") or "").strip()
                address = (entry.get("address") or "").strip()
                notes_val = (entry.get("notes") or "").strip()
                clergy_list = entry.get("clergy", [])
                year_founded = entry.get("year_founded")

                type_counts[etype] = type_counts.get(etype, 0) + 1

                batch_entries.append((
                    DIR_YEAR, f"{name}_{entry_idx}", ename,
                    city or None, state or None, name, etype,
                    address or None, None, None, None, None,
                    year_founded, None, None,
                    notes_val + " [1865 Sadlier's]",
                    json.dumps(entry, ensure_ascii=False),
                ))

                for c in clergy_list:
                    cname = (c.get("name") or "").strip()
                    ctitle = (c.get("title") or "").strip()
                    if cname:
                        batch_clergy.append((entry_idx, DIR_YEAR, cname, ctitle))
                        total_clergy += 1

                entry_idx += 1
                total_entries += 1

            # Flush batch
            if len(batch_entries) >= CHUNK_SIZE:
                conn.executemany("""INSERT INTO dir_entries (directory_year, source_entry_id, name, city,
                    state, diocese, entity_type, address, zip, phone, website, email,
                    year_founded, landmark_type, grid_church_id, notes, source_raw)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", batch_entries)
                batch_entries.clear()
                conn.commit()

        elif result is None:
            print(f"FAIL ({elapsed:.1f}s)")
        else:
            print(f"Unexpected result type: {type(result).__name__}")

        time.sleep(0.5)  # rate limit

    # Final flush
    if batch_entries:
        conn.executemany("""INSERT INTO dir_entries (directory_year, source_entry_id, name, city,
            state, diocese, entity_type, address, zip, phone, website, email,
            year_founded, landmark_type, grid_church_id, notes, source_raw)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", batch_entries)
        conn.commit()

    # Link clergy via source_entry_id mapping
    print(f"\nLinking clergy...")
    entry_map = {}
    for row in conn.execute("SELECT source_entry_id, id FROM dir_entries WHERE directory_year=?", (DIR_YEAR,)):
        entry_map[row[0]] = row[1]

    linked = 0
    for row in conn.execute("SELECT id, entry_id FROM dir_clergy WHERE directory_year=?", (DIR_YEAR,)):
        source_key = str(row[1])
        real_eid = entry_map.get(source_key)
        if real_eid:
            conn.execute("UPDATE dir_clergy SET entry_id=? WHERE id=?", (real_eid, row[0]))
            linked += 1
    conn.execute("DELETE FROM dir_clergy WHERE entry_id < 0 OR entry_id >= 1000000")
    conn.commit()
    print(f"  Linked {linked} clergy")

    # Hierarchy section
    print("Looking for hierarchy section...")
    for pat in ["CARDINALS, ARCHBISHOPS, BISHOPS", "THE HIERARCHY", "HIERARCHY OF THE CATHOLIC CHURCH"]:
        idx = text.find(pat)
        if idx > 0 and idx < len(text) * 0.4:
            hier = re.sub(r'\s+', ' ', text[idx:idx+30000]).strip()[:12000]
            print(f"  Found '{pat}' at pos {idx:,}...")
            result = call_api(HIERARCHY_PROMPT, hier)
            if result and isinstance(result, list):
                for b in result:
                    conn.execute("""INSERT INTO dir_bishops (directory_year, name, title, diocese,
                        bishop_type, status, consecrated_year, birth_year, notes, source_raw)
                        VALUES (?,?,?,?,?,?,?,?,?,?)""", (
                        DIR_YEAR, b.get("name",""), b.get("title","") or None,
                        b.get("diocese","") or None, b.get("bishop_type","") or None,
                        "historical", b.get("consecrated"), b.get("birth_year"),
                        b.get("notes","") or None, json.dumps(b, ensure_ascii=False)))
                print(f"  Imported {len(result)} bishops")
            break

    # Provenance
    entry_count = conn.execute("SELECT COUNT(*) FROM dir_entries WHERE directory_year=?", (DIR_YEAR,)).fetchone()[0]
    clergy_count = conn.execute("SELECT COUNT(*) FROM dir_clergy WHERE directory_year=?", (DIR_YEAR,)).fetchone()[0]
    bishop_count = conn.execute("SELECT COUNT(*) FROM dir_bishops WHERE directory_year=?", (DIR_YEAR,)).fetchone()[0]
    conn.execute("""INSERT INTO dir_provenance (source, description, entry_count, clergy_count, bishop_count)
        VALUES (?,?,?,?,?)""", ("catholic_dir_1865", f"1865 Sadlier's Catholic Directory — {entry_count:,} entries", entry_count, clergy_count, bishop_count))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()

    # Summary
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


if __name__ == "__main__":
    main()
