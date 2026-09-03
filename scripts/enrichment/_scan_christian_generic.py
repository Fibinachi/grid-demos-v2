"""DeepSeek scan of unclassified Christian entries + 1,000 random sample.

Four-phase pipeline:
  Phase 1a: SQL-fix 2,706 misclassified (non-Christian traditions under Christian)
  Phase 1b: SQL-fix LDS/JW entries hiding in generic Christian by name pattern
  Phase 2: DeepSeek-classify no-tradition Christian entries (~7K, excludes LDS/JW names)
  Phase 3: DeepSeek-classify 1,000 random sample (excludes LDS/JW names)
  Phase 4: Generate summary report

LDS/Mormon and JW entries are explicitly excluded from scanning — caught by name
patterns in Phase 1b and filtered from queries in Phases 2-3. Prompts also instruct
DeepSeek to flag LDS/JW as non-standard Christian traditions."""
import sqlite3, os, json, requests, sys, re
from datetime import datetime, timezone

conn = sqlite3.connect(r"E:\grid\churches.db", timeout=30)
conn.execute("PRAGMA busy_timeout = 30000")  # 30 second busy timeout
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

SCRIPT_NAME = "scan_christian_generic"
STARTED_AT = datetime.now(timezone.utc).isoformat()
source_name = 'deepseek_christian_generic'

# ── Ensure columns exist ──
existing = {r[1] for r in c.execute('PRAGMA table_info(churches)').fetchall()}
for col, dtype in [
    ('christian_affiliation', 'TEXT'),
    ('christian_confidence', 'REAL'),
    ('christian_classification_source', 'TEXT'),
    ('christian_updated', 'TEXT'),
]:
    if col not in existing:
        c.execute(f'ALTER TABLE churches ADD COLUMN {col} {dtype}')
        print(f'  Added column: {col}')
conn.commit()

# ── Provenance helpers ──
def log_enrichment(church_id, field, old_val, new_val):
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, ?, ?, ?, ?)",
              (church_id, field, str(old_val) if old_val is not None else None,
               str(new_val) if new_val is not None else None, source_name))

def update_with_provenance(church_id, field, old_val, new_val):
    if old_val is None:
        c.execute(f"SELECT {field} FROM churches WHERE id=?", (church_id,))
        row = c.fetchone()
        old_val = row[0] if row else None
    if str(old_val) != str(new_val):
        for attempt in range(3):
            try:
                c.execute(f"UPDATE churches SET {field}=? WHERE id=?", (new_val, church_id))
                log_enrichment(church_id, field, old_val, new_val)
                break
            except sqlite3.OperationalError as e:
                if 'locked' in str(e) and attempt < 2:
                    import time; time.sleep(1)
                    continue
                raise

# ── Phase 1: SQL-fix misclassified ──
print("=" * 72)
print("PHASE 1: Fix misclassified non-Christian traditions under Christian faith")
print("=" * 72)

MISCLASSIFIED_MAP = {
    'Vaishnavism': ('Hindu', 'Vaishnavism', 'temple'),
    'Shrine Shinto': ('Shinto', 'Shrine Shinto', 'shrine'),
    'Rabbinic': ('Judaism', 'Rabbinic', 'synagogue'),
    'Mahayana': ('Buddhist', 'Mahayana', 'temple'),
    'Muslim': ('Islam', 'Sunni', 'mosque'),
    'Chinese Buddhism': ('Buddhist', 'Chinese Buddhism', 'temple'),
    'Theravada': ('Buddhist', 'Theravada', 'temple'),
    'Zen': ('Buddhist', 'Zen', 'temple'),
    'ISKCON': ('Hindu', 'Vaishnavism', 'temple'),
    'Pagan': ('Other', 'Pagan', 'shrine'),
    'Neo-Hindu': ('Hindu', 'Other', 'temple'),
    'Shaivism': ('Hindu', 'Shaivism', 'temple'),
    'jewish': ('Judaism', 'Rabbinic', 'synagogue'),
    'Baha\'i': ('Other', 'Baha\'i', 'center'),
    'Sikh': ('Sikh', 'Sikh', 'gurdwara'),
    'Buddhist': ('Buddhist', 'Other', 'temple'),
    'Hindu': ('Hindu', 'Other', 'temple'),
    'Shinto': ('Shinto', 'Shrine Shinto', 'shrine'),
    'Taoist': ('Taoist', 'Taoist', 'temple'),
    'Jain': ('Jain', 'Other', 'temple'),
    'Confucian': ('Taoist', 'Confucian', 'temple'),
    'Animist': ('Other', 'Animist', 'shrine'),
    'Orthodox (Yeshiva)': ('Judaism', 'Orthodox (Yeshiva)', 'synagogue'),
    'Orthodox (Chabad)': ('Judaism', 'Orthodox (Chabad)', 'synagogue'),
    'Orthodox (Hasidic)': ('Judaism', 'Orthodox (Hasidic)', 'synagogue'),
}

fix_count = 0

for trad, (new_faith, new_trad, new_type) in MISCLASSIFIED_MAP.items():
    cnt = c.execute("SELECT COUNT(*) FROM churches WHERE tradition=? AND faith='Christian'", (trad,)).fetchone()[0]
    if not cnt:
        continue
    
    # Single UPDATE with WHERE condition — far faster than individual ID lists
    c.execute("""
        UPDATE churches SET faith=?, tradition=?, landmark_type=? 
        WHERE tradition=? AND faith='Christian'
    """, (new_faith, new_trad, new_type, trad))
    conn.commit()
    
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, ?, ?, ?, ?)",
              (0, '_batch', f'Phase1a:{trad}', f'{new_faith}/{new_trad}', source_name))
    conn.commit()
    
    print(f"  {trad:30s} -> {new_faith:10s}/{new_trad:30s}  ({cnt:,} entries)")
    fix_count += cnt
print(f"\n  Phase 1a complete: {fix_count:,} entries reclassified (tradition-based)")

# ── Phase 1b: SQL-fix LDS/JW by name pattern ──
print(f"\n  Phase 1b: Fix LDS/JW entries hiding in generic Christian by name pattern")

LDS_PATTERNS = [
    ('%Church of Jesus Christ of Latter%', 'Christian', "Church of Jesus Christ of Latter-day Saints", 'Other LDS'),
    ('%Latter%Day%', 'Christian', "Church of Jesus Christ of Latter-day Saints", 'Other LDS'),
    ('%Latter-day%', 'Christian', "Church of Jesus Christ of Latter-day Saints", 'Other LDS'),
    ('%Mormon%', 'Christian', "Church of Jesus Christ of Latter-day Saints", 'Other LDS'),
    ('%Deseret%', 'Christian', "Church of Jesus Christ of Latter-day Saints", 'Other LDS'),
    ('%Stake %', 'Christian', "Church of Jesus Christ of Latter-day Saints", 'Other LDS'),
    ('% Stake%', 'Christian', "Church of Jesus Christ of Latter-day Saints", 'Other LDS'),
    ('% Ward%', 'Christian', "Church of Jesus Christ of Latter-day Saints", 'Other LDS'),
    ('%Jehovah%', 'Christian', "Jehovah's Witnesses", 'Other'),
    ('%Witnesses%', 'Christian', "Jehovah's Witnesses", 'Other'),
    ('%Watchtower%', 'Christian', "Jehovah's Witnesses", 'Other'),
    ('%Kingdom Hall%', 'Christian', "Jehovah's Witnesses", 'Other'),
    ('%kingdom hall%', 'Christian', "Jehovah's Witnesses", 'Other'),
]

lds_jw_fix_count = 0

# LDS batch — single combined query for all LDS patterns
lds_patterns_sql = """
    (name LIKE '%Church of Jesus Christ of Latter%')
    OR (name LIKE '%Latter%Day Saint%')
    OR (name LIKE '%Latter-day Saint%')
    OR (name LIKE '%Mormon%')
    OR (name LIKE '%Deseret%')
"""
cnt_lds = c.execute(f"SELECT COUNT(*) FROM churches WHERE taxonomy_id=2 AND faith='Christian' AND ({lds_patterns_sql})").fetchone()[0]
if cnt_lds:
    c.execute(f"""
        UPDATE churches SET tradition='Church of Jesus Christ of Latter-day Saints', 
                            landmark_type='meetinghouse', taxonomy_id=166
        WHERE taxonomy_id=2 AND faith='Christian' AND ({lds_patterns_sql})
    """)
    conn.commit()
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, ?, ?, ?, ?)",
              (0, '_batch', 'Phase1b:LDS', f'count={cnt_lds}', source_name))
    conn.commit()
    print(f"  LDS name patterns                                        ({cnt_lds:,} entries)")
    lds_jw_fix_count += cnt_lds

# JW batch — single combined query for all JW patterns
jw_patterns_sql = """
    (name LIKE '%Jehovah%')
    OR (name LIKE '%Witnesses%')
    OR (name LIKE '%Watchtower%')
    OR (name LIKE '%Kingdom Hall%')
    OR (name LIKE '%kingdom hall%')
"""
cnt_jw = c.execute(f"SELECT COUNT(*) FROM churches WHERE taxonomy_id=2 AND faith='Christian' AND ({jw_patterns_sql})").fetchone()[0]
if cnt_jw:
    c.execute(f"""
        UPDATE churches SET tradition="Jehovah's Witnesses",
                            landmark_type='kingdom_hall', taxonomy_id=165
        WHERE taxonomy_id=2 AND faith='Christian' AND ({jw_patterns_sql})
    """)
    conn.commit()
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, ?, ?, ?, ?)",
              (0, '_batch', 'Phase1b:JW', f'count={cnt_jw}', source_name))
    conn.commit()
    print(f"  JW name patterns                                         ({cnt_jw:,} entries)")
    lds_jw_fix_count += cnt_jw

print(f"\n  Phase 1b complete: {lds_jw_fix_count:,} LDS/JW entries reclassified by name")
fix_count += lds_jw_fix_count

# ── Phase 2: Find no-tradition Christian entries ──
print("\n" + "=" * 72)
print("PHASE 2: Scan 7,055 no-tradition Christian entries via DeepSeek")
print("=" * 72)

# Check what's already been reviewed
c.execute("""
    SELECT DISTINCT church_id FROM enrichment_change_log
    WHERE change_source = 'deepseek_christian_generic'
""")
reviewed_phase2 = {r[0] for r in c.fetchall()}
print(f"  Already reviewed: {len(reviewed_phase2):,} entries")

# Get no-tradition entries, excluding already-reviewed + LDS/JW name patterns
exclude_name_patterns = [
    '%Latter%', '%Mormon%', '%Deseret%', 
    '%Jehovah%', '%Witness%', '%Watchtower%', '%Kingdom Hall%', '%kingdom hall%',
    '%Stake%', '% Ward%', '% Stake%'
]

if reviewed_phase2:
    placeholders = ','.join('?' * len(reviewed_phase2))
    name_clause = ' AND '.join(['name NOT LIKE ?'] * len(exclude_name_patterns))
    c.execute(f"""
        SELECT id, name, city, state, country, landmark_type, tradition
        FROM churches WHERE taxonomy_id=2 
        AND (tradition IS NULL OR tradition = '')
        AND id NOT IN ({placeholders})
        AND {name_clause}
        ORDER BY country, name
    """, tuple(reviewed_phase2) + tuple(exclude_name_patterns))
else:
    name_clause = ' AND '.join(['name NOT LIKE ?'] * len(exclude_name_patterns))
    c.execute(f"""
        SELECT id, name, city, state, country, landmark_type, tradition
        FROM churches WHERE taxonomy_id=2 
        AND (tradition IS NULL OR tradition = '')
        AND {name_clause}
        ORDER BY country, name
    """, tuple(exclude_name_patterns))
no_trad_entries = c.fetchall()
print(f"  Remaining to scan: {len(no_trad_entries):,}")

# ── Phase 3: 1,000 random sample from generic Christian ──
print("\n" + "=" * 72)
print("PHASE 3: 1,000 random sample from generic Christian pool")
print("=" * 72)

# Get total generic Christian count (with tradition, after phase 1 fixes)
c.execute("""
    SELECT COUNT(*) FROM churches 
    WHERE taxonomy_id=2 AND faith='Christian' 
    AND tradition IS NOT NULL AND tradition != ''
""")
total_pool = c.fetchone()[0]
print(f"  Generic Christian pool available: {total_pool:,}")

# Check already-sampled from this run
c.execute("""
    SELECT DISTINCT church_id FROM enrichment_change_log
    WHERE change_source = 'deepseek_christian_sample'
""")
sampled_ids = {r[0] for r in c.fetchall()}
print(f"  Already sampled: {len(sampled_ids):,}")

# Pick random entries not already sampled, excluding LDS/JW name patterns
exclude_sample_patterns = [
    '%Latter%', '%Mormon%', '%Deseret%',
    '%Jehovah%', '%Witness%', '%Watchtower%', '%Kingdom Hall%', '%kingdom hall%',
    '%Stake%', '% Ward%', '% Stake%'
]
name_clause2 = ' AND '.join(['name NOT LIKE ?'] * len(exclude_sample_patterns))

if sampled_ids:
    placeholders2 = ','.join('?' * len(sampled_ids))
    c.execute(f"""
        SELECT id, name, city, state, country, landmark_type, tradition
        FROM churches WHERE taxonomy_id=2 AND faith='Christian'
        AND tradition IS NOT NULL AND tradition != ''
        AND id NOT IN ({placeholders2})
        AND {name_clause2}
        ORDER BY RANDOM()
        LIMIT 1000
    """, tuple(sampled_ids) + tuple(exclude_sample_patterns))
else:
    c.execute(f"""
        SELECT id, name, city, state, country, landmark_type, tradition
        FROM churches WHERE taxonomy_id=2 AND faith='Christian'
        AND tradition IS NOT NULL AND tradition != ''
        AND {name_clause2}
        ORDER BY RANDOM()
        LIMIT 1000
    """, tuple(exclude_sample_patterns))
sample_entries = c.fetchall()
print(f"  New random sample: {len(sample_entries):,} entries")
print(f"  Sample composition:")
trad_counts = {}
for e in sample_entries:
    t = e[6] or 'unknown'
    trad_counts[t] = trad_counts.get(t, 0) + 1
for t, cnt in sorted(trad_counts.items(), key=lambda x: -x[1]):
    print(f"    {t:30s} {cnt:>6,}")

# ── Combined DeepSeek scan function ──

PROMPT_CLASSIFY = """For each entry, determine the specific faith, tradition, and facility type.

The entry currently has faith=Christian but may or may not actually be Christian.
If it IS Christian, classify as specifically as possible.
If it is NOT Christian, return the correct faith.

IMPORTANT — LDS/Mormon and Jehovah's Witnesses are NOT standard Christian:
- LDS/Mormon indicators: Latter-day Saints, Mormon, Deseret, Stake, Ward, Temple (SLC context), LDS
- Jehovah's Witnesses indicators: Jehovah's Witnesses, Witnesses, Watchtower, Kingdom Hall, JW
- Return faith="Christian" with tradition="Church of Jesus Christ of Latter-day Saints" for LDS
- Return faith="Christian" with tradition="Jehovah's Witnesses" for JW

Common CHRISTIAN traditions:
- PROTESTANT subgroups: Baptist, Methodist, Presbyterian, Lutheran (ELCA/LCMS/WELS), Anglican/Episcopal, Pentecostal (Assemblies of God, Foursquare, COGIC), Adventist (Seventh-day Adventist), Reformed, Congregational, United Church of Christ, Christian Church (Disciples of Christ), Non-Denominational, Evangelical Free, Nazarene, Wesleyan, Holiness, Mennonite, Quaker, Salvation Army, Calvary Chapel, Vineyard, Community Church, Church of God (Cleveland, Anderson), Brethren
- CATHOLIC: Roman Catholic (specify rite: Latin, Byzantine, Maronite, etc.), Old Catholic, Traditional Catholic
- ORTHODOX: Eastern Orthodox (Greek, Russian, Antiochian, Serbian, Romanian, Bulgarian, OCA), Oriental Orthodox (Coptic, Ethiopian, Armenian, Syriac, Malankara)
- OTHER STANDARD CHRISTIAN: Unitarian Universalist, Christian Science, Metropolitan Community Church

NON-CHRISTIAN faiths to watch for: Hindu (mandir, temple, ashram), Buddhist (wat, vihara, stupa), Muslim (mosque, masjid), Jewish (synagogue, shul), Shinto (jinja, shrine), Sikh (gurdwara), Other

Return ONLY JSON array:
[{{"id": N, "faith": "Christian|Hindu|Buddhist|Islam|Judaism|Shinto|Sikh|Other", "tradition": "...", "denomination": "...", "landmark_type": "church|cathedral|basilica|chapel|shrine|temple|synagogue|mosque|masjid|mandir|gurdwara|jinja|meetinghouse|kingdom_hall|auditorium|center|other"}}]

Use the most specific denomination possible based on the name and location.

{items}"""

PROMPT_SAMPLE = """For each entry, determine the most specific Christian denomination/tradition.

This is a religious site that IS Christian. Based on the name, city, state, and country, classify it.

IMPORTANT — LDS/Mormon and Jehovah's Witnesses are NOT standard Christian:
- LDS/Mormon indicators: Latter-day Saints, Mormon, Deseret, Stake, Ward, Temple (SLC), LDS
  → tradition="Church of Jesus Christ of Latter-day Saints"
- Jehovah's Witnesses indicators: Jehovah, Witnesses, Watchtower, Kingdom Hall, JW
  → tradition="Jehovah's Witnesses"
- These should be returned as distinct non-standard Christian traditions

Common Christian traditions (most specific level):
- Baptist: Southern Baptist Convention, American Baptist, Independent Baptist, National Baptist, Free Will Baptist, Primitive Baptist, Missionary Baptist
- Methodist: United Methodist Church, AME, AME Zion, CME, Free Methodist, Wesleyan
- Presbyterian: PC(USA), PCA, Cumberland, EPC, OPC, Associate Reformed
- Lutheran: ELCA, LCMS, WELS, LCMC, NALC, AFLC
- Anglican/Episcopal: Episcopal Church, ACNA, Anglican Church of Canada, Church of England
- Pentecostal: Assemblies of God, Foursquare, COGIC, Pentecostal Holiness, UPCI, Church of God (Cleveland)
- Catholic: Roman Catholic (Latin Rite, Byzantine, Maronite, Ukrainian, Syro-Malabar, etc.)
- Orthodox: Greek, Russian, Antiochian, OCA, Serbian, Romanian, Coptic, Ethiopian, Armenian
- Other: Non-Denominational, Evangelical, Adventist, Reformed, Congregational, UCC, Disciples of Christ, Nazarene, Holiness, Mennonite, Quaker, Salvation Army, Church of God, Calvary Chapel, Vineyard, Community Church, Christian & Missionary Alliance, Brethren, etc.

Return ONLY JSON array:
[{{"id": N, "tradition": "...", "denomination": "...", "landmark_type": "church|cathedral|basilica|chapel|meetinghouse|kingdom_hall|other"}}]

{items}"""

def call_deepseek(items, prompt_template, max_tokens=4000):
    prompt = prompt_template.format(items=json.dumps(items, indent=2))
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.05, "max_tokens": max_tokens
        }, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, timeout=90)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            jm = re.search(r'\[.*?\]', content, re.DOTALL)
            if jm:
                try:
                    return json.loads(jm.group())
                except json.JSONDecodeError:
                    print(f"  JSON PARSE ERROR")
                    return None
            print(f"  NO JSON found in response")
            return None
        print(f"  HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"  API error: {e}")
        return None

def process_classification(results, is_sample=False):
    """Process DeepSeek results for no-tradition or sample entries."""
    cnt_faith = 0
    cnt_trad = 0
    cnt_type = 0
    for r in results:
        id_ = r.get("id")
        faith = r.get("faith", "Christian")
        trad = r.get("tradition", "")
        denom = r.get("denomination", "")
        ftype = (r.get("landmark_type") or "").lower().replace(' ', '_')

        if not id_:
            continue

        # Update faith if changed from Christian
        if faith and faith.upper() != "CHRISTIAN":
            old = c.execute("SELECT faith FROM churches WHERE id=?", (id_,)).fetchone()
            old_val = old[0] if old else None
            update_with_provenance(id_, 'faith', old_val, faith)
            cnt_faith += 1

        # Update tradition if provided
        if trad:
            old = c.execute("SELECT tradition FROM churches WHERE id=?", (id_,)).fetchone()
            old_val = old[0] if old else None
            update_with_provenance(id_, 'tradition', old_val, trad)
            cnt_trad += 1

        if denom and denom != trad:
            # Store denomination in christian_affiliation
            update_with_provenance(id_, 'christian_affiliation', None, f"{faith}::{denom}")

        # Update landmark_type if provided
        if ftype:
            old = c.execute("SELECT landmark_type FROM churches WHERE id=?", (id_,)).fetchone()
            old_val = old[0] if old else None
            if ftype != old_val:
                update_with_provenance(id_, 'landmark_type', old_val, ftype)
                cnt_type += 1

        # Set confidence + source
        c.execute("""
            UPDATE churches SET 
                christian_confidence=0.85,
                christian_classification_source=?,
                christian_updated=?
            WHERE id=?
        """, ('deepseek_christian_sample' if is_sample else source_name,
              datetime.now(timezone.utc).isoformat(), id_))

    return cnt_faith, cnt_trad, cnt_type


# ── Scan Phase 2: no-tradition entries ──
CHUNK_SIZE = 20

if no_trad_entries:
    print(f"\n  Scanning {len(no_trad_entries):,} no-tradition entries...")
    p2_faith = 0
    p2_trad = 0
    p2_type = 0
    
    for cs in range(0, len(no_trad_entries), CHUNK_SIZE):
        chunk = no_trad_entries[cs:cs+CHUNK_SIZE]
        items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
                  "state": str(e[3] or ''), "country": str(e[4] or ''),
                  "type": str(e[5] or ''), "tradition": str(e[6] or '')} for e in chunk]
        bn = cs//CHUNK_SIZE + 1
        tb = (len(no_trad_entries)-1)//CHUNK_SIZE + 1
        
        results = call_deepseek(items, PROMPT_CLASSIFY)
        if results:
            f, t, ty = process_classification(results)
            p2_faith += f
            p2_trad += t
            p2_type += ty
            conn.commit()
        else:
            results = call_deepseek(items, PROMPT_CLASSIFY)
            if results:
                f, t, ty = process_classification(results)
                p2_faith += f
                p2_trad += t
                p2_type += ty
                conn.commit()
        
        if (cs // CHUNK_SIZE) % 5 == 0:
            print(f"  Batch {bn}/{tb} | faith: {p2_faith} | trad: {p2_trad} | type: {p2_type}")
    
    print(f"\n  Phase 2 complete: {p2_faith} faith moved, {p2_trad} traditions set, {p2_type} types updated")
else:
    print("  Nothing to scan (all already done)")

# ── Scan Phase 3: 1,000 random sample ──
if sample_entries:
    print(f"\n  Scanning {len(sample_entries):,} sample entries...")
    s3_faith = 0
    s3_trad = 0
    s3_type = 0
    
    for cs in range(0, len(sample_entries), CHUNK_SIZE):
        chunk = sample_entries[cs:cs+CHUNK_SIZE]
        items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
                  "state": str(e[3] or ''), "country": str(e[4] or ''),
                  "type": str(e[5] or ''), "tradition": str(e[6] or '')} for e in chunk]
        bn = cs//CHUNK_SIZE + 1
        tb = (len(sample_entries)-1)//CHUNK_SIZE + 1
        
        results = call_deepseek(items, PROMPT_SAMPLE, max_tokens=5000)
        if results:
            f, t, ty = process_classification(results, is_sample=True)
            s3_faith += f
            s3_trad += t
            s3_type += ty
            conn.commit()
        else:
            results = call_deepseek(items, PROMPT_SAMPLE, max_tokens=5000)
            if results:
                f, t, ty = process_classification(results, is_sample=True)
                s3_faith += f
                s3_trad += t
                s3_type += ty
                conn.commit()
        
        if (cs // CHUNK_SIZE) % 5 == 0:
            print(f"  Batch {bn}/{tb} | faith: {s3_faith} | trad: {s3_trad} | type: {s3_type}")
    
    print(f"\n  Phase 3 complete: {s3_faith} faith moved, {s3_trad} traditions refined, {s3_type} types updated")
else:
    print("  No sample entries to scan")

# ── Phase 4: Summary Report ──
print("\n" + "=" * 72)
print("PHASE 4: SUMMARY REPORT")
print("=" * 72)

# Overall Christian state now
total_christian = c.execute("SELECT COUNT(*) FROM churches WHERE faith='Christian'").fetchone()[0]
c2 = c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=2").fetchone()[0]
wt = c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id=2 AND tradition IS NOT NULL AND tradition != ''").fetchone()[0]
wot = c2 - wt
sub = total_christian - c2

print(f"\n  Christian churches total:          {total_christian:>10,}")
print(f"  At specific taxonomy sub-nodes:   {sub:>10,}")
print(f"  At generic Christian (id=2):      {c2:>10,}")
print(f"    With tradition:                 {wt:>10,}")
print(f"    Without tradition (remaining):  {wot:>10,}")

# Check for remaining misclassifications
print(f"\n  Remaining misclassifications (non-Christian trad under Christian):")
mis_remaining = c.execute("""
    SELECT tradition, COUNT(*) FROM churches 
    WHERE taxonomy_id=2 AND faith='Christian'
    AND LOWER(tradition) IN ('vaishnavism', 'shrine shinto', 'rabbinic', 'muslim',
        'mahayana', 'chinese buddhism', 'theravada', 'zen', 'iskcon', 
        'pagan', 'neo-hindu', 'shaivism', 'jewish', 'baha''i', 'sikh',
        'buddhist', 'hindu', 'shinto', 'taoist', 'jain', 'confucian', 'animist')
    GROUP BY tradition ORDER BY COUNT(*) DESC
""").fetchall()
if mis_remaining:
    for r in mis_remaining:
        print(f"    {r[0]:30s} {r[1]:>8,}")
else:
    print("    NONE ✅")

# Sample composition
sample_ids = [e[0] for e in sample_entries] if sample_entries else []
if sample_ids:
    sample_trads = c.execute("""
        SELECT tradition, COUNT(*) FROM churches 
        WHERE id IN (""" + ','.join(str(x) for x in sample_ids) + """)
        AND christian_classification_source = 'deepseek_christian_sample'
        GROUP BY tradition ORDER BY COUNT(*) DESC
    """).fetchall()
    print(f"\n  Sample {len(sample_ids):,} entries composition:")
    if sample_trads:
        for r in sample_trads[:20]:
            print(f"    {r[0]:40s} {r[1]:>6,}")
        if len(sample_trads) > 20:
            print(f"    ... and {len(sample_trads)-20} more traditions")
    else:
        print("    (results pending)")

conn.close()
print(f"\n=== Pipeline complete ===")
print(f"  Started:  {STARTED_AT}")
print(f"  Finished: {datetime.now(timezone.utc).isoformat()}")
