"""DeepSeek scan of US Christian churches needing deeper classification.
Targets ~202K faith-only entries with no legacy/tradition/movement assigned
(after 91K already reviewed in prior run).
Includes misclassification detection (non-Christians, LDS, JW).
Resume-safe via enrichment_change_log.
Processes states smallest-to-largest with per-state summaries.
BATCH_SIZE=50."""
import sqlite3, os, json, requests, sys, re, time
from collections import OrderedDict
from datetime import datetime, timezone

DB = r"E:\grid\churches.db"
BATCH_SIZE = 40
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

conn = sqlite3.connect(DB, timeout=60)
conn.execute("PRAGMA busy_timeout = 60000")
c = conn.cursor()

SCRIPT_NAME = "scan_us_christians"
STARTED_AT = datetime.now(timezone.utc).isoformat()
SOURCE = 'deepseek_us_christians'

def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%H:%M:%S')}] {msg}", flush=True)

# ── Resume support ──
log("Checking already-reviewed entries...")
reviewed_count = c.execute(
    "SELECT COUNT(DISTINCT church_id) FROM enrichment_change_log WHERE change_source=?", (SOURCE,)
).fetchone()[0]
log(f"  Already reviewed: {reviewed_count:,}")

# ── Query faith-only US Christians ──
log("Querying faith-only US Christians...")
c.execute("""
    SELECT id, name, city, state, country, landmark_type, tradition
    FROM churches
    WHERE faith='Christian' AND country='US'
    AND faith_id IS NOT NULL AND legacy_id IS NULL
    AND name IS NOT NULL AND name != ''
    AND id NOT IN (SELECT DISTINCT church_id FROM enrichment_change_log WHERE change_source=?)
    ORDER BY state, name
""", (SOURCE,))
entries = c.fetchall()
log(f"  Remaining to scan: {len(entries):,}")

if not entries:
    log("Nothing to scan!")
    conn.close()
    sys.exit(0)

# ═══════════════════════════════════════════════════════════════════
# PHASE 0: SQL pre-classify by name patterns + source
# ═══════════════════════════════════════════════════════════════════
PRECLASS_SOURCE = 'preclass_us_christians'
log("")
log("=" * 60)
log("PHASE 0: Pre-classify by name pattern & source (no DeepSeek)")
log("=" * 60)

# Lookup helpers
def _get_id(table, name):
    r = c.execute(f"SELECT id FROM {table} WHERE name=?", (name,)).fetchone()
    return r[0] if r else None

NAME_PATTERNS = [
    # (pattern, legacy_name, tradition_name, movement_name)
    # Legacy must be one of: Anglican, Catholic, Orthodox, Protestant, Restorationist, Other

    ("%Catholic Church%", "Catholic", "Roman Catholic", None),
    ("%Roman Catholic%", "Catholic", "Roman Catholic", "Roman Catholic"),
    ("%Coptic%", "Orthodox", "Coptic Orthodox", "Coptic Orthodox"),
    ("%Episcopal Church%", "Anglican", "Episcopal", "Episcopal"),
    ("%Orthodox Church%", "Orthodox", "Eastern Orthodox", None),
    ("%Greek Orthodox%", "Orthodox", "Greek Orthodox", "Greek Orthodox"),
    ("%Russian Orthodox%", "Orthodox", "Russian Orthodox", "Russian Orthodox"),
    ("%Serbian Orthodox%", "Orthodox", "Serbian Orthodox", "Serbian Orthodox"),
    ("%Antiochian Orthodox%", "Orthodox", "Antiochian Orthodox", "Antiochian Orthodox"),
    
    ("%Church of the Nazarene%", "Protestant", "Church of the Nazarene", "Church of the Nazarene"),
    ("%Nazarene Church%", "Protestant", "Church of the Nazarene", "Church of the Nazarene"),
    ("%Unitarian Universalist%", "Unitarian Universalist", "Unitarian Universalist", None),
    ("%Unitarian Church%", "Unitarian Universalist", "Unitarian Universalist", None),
    ("%Universalist Church%", "Unitarian Universalist", "Unitarian Universalist", None),
    ("%Unitarian%", "Unitarian Universalist", "Unitarian Universalist", None),
    ("%Universalist%", "Unitarian Universalist", "Unitarian Universalist", None),
    ("%Seventh-day Adventist%", "Protestant", "Seventh-day Adventist", "Seventh-day Adventist"),
    ("%COGIC%", "Protestant", "COGIC", "COGIC"),
    ("%Church of God in Christ%", "Protestant", "COGIC", "COGIC"),
    ("%Assemblies of God%", "Protestant", "Assemblies of God", "Assemblies of God"),
    ("%Southern Baptist Convention%", "Protestant", "Southern Baptist Convention", "Southern Baptist Convention"),
    ("%United Methodist%", "Protestant", "United Methodist Church", "United Methodist Church"),
    ("%AME Church%", "Protestant", "Methodist", "African Methodist Episcopal Church"),
    ("%AME Zion%", "Protestant", "Methodist", "African Methodist Episcopal Zion Church"),
    ("%African Methodist Episcopal Zion%", "Protestant", "Methodist", "African Methodist Episcopal Zion Church"),
    ("%African Methodist Episcopal%", "Protestant", "Methodist", "African Methodist Episcopal Church"),
    ("%Evangelical Lutheran%", "Protestant", "Evangelical Lutheran Church in America", "ELCA"),
    ("%Lutheran Church - Missouri%", "Protestant", "Lutheran Church - Missouri Synod", "LCMS"),
    ("%LCMS%", "Protestant", "Lutheran Church - Missouri Synod", "LCMS"),
    ("%WELS%", "Protestant", "Wisconsin Evangelical Lutheran Synod", "WELS"),
    ("%Presbyterian Church (USA)%", "Protestant", "Presbyterian Church (U.S.A.)", "PCUSA"),
    ("%Presbyterian Church in America%", "Protestant", "Presbyterian Church in America", "PCA"),
    ("%Presbyterian Church USA%", "Protestant", "Presbyterian Church (U.S.A.)", "PCUSA"),
    ("%United Church of Christ%", "Protestant", "United Church of Christ", "United Church of Christ"),
    ("%Disciples of Christ%", "Protestant", "Christian Church (Disciples of Christ)", "Christian Church (Disciples of Christ)"),
    ("%Salvation Army%", "Protestant", "Salvation Army", "Salvation Army"),
    ("%Latter-day Saint%", "Restorationist", "Church of Jesus Christ of Latter-day Saints", "Church of Jesus Christ of Latter-day Saints"),
    ("%Mormon%", "Restorationist", "Church of Jesus Christ of Latter-day Saints", "Church of Jesus Christ of Latter-day Saints"),
    ("%Jehovah%Witness%", "Restorationist", "Jehovah's Witnesses", "Jehovah's Witnesses"),
    ("%Christian Science%", "Protestant", "Christian Science", "Christian Science"),
    ("%First Baptist%", "Protestant", "Baptist", None),
    
    # ── New safe patterns from analysis ──
    ("%Baptist Church%", "Protestant", "Baptist", None),
    ("%Presbyterian%", "Protestant", "Presbyterian", None),
    ("%Methodist%", "Protestant", "Methodist", None),
    ("%Lutheran%", "Protestant", "Lutheran (Other)", None),
    ("%Pentecostal%", "Protestant", "Pentecostal", None),
    ("%Holiness%", "Protestant", "Holiness", None),
    ("%Congregational%", "Protestant", "Congregational", None),
    ("%Mennonite%", "Protestant", "Mennonite (unspecified)", None),
    ("%Brethren%", "Protestant", "Brethren", None),
    ("%Moravian%", "Protestant", "Moravian", None),
    ("%Quaker%", "Protestant", "Quaker", None),
    ("%Friends Church%", "Protestant", "Quaker", None),
    ("%Friends Meeting%", "Protestant", "Quaker", None),
    ("%Calvary Chapel%", "Protestant", "Calvary Chapel", "Calvary Chapel"),
    ("%Bible Church%", "Protestant", "Evangelical", None),
    ("%Community Church%", "Protestant", "Non-Denominational", None),
    ("%Full Gospel%", "Protestant", "Full Gospel", None),
    ("%Foursquare%", "Protestant", "Foursquare Church", "Foursquare Church"),
    ("%Church of the Brethren%", "Protestant", "Church of the Brethren", "Church of the Brethren"),
    ("%Free Methodist%", "Protestant", "Free Methodist", "Free Methodist"),
    ("%Wesleyan%", "Protestant", "Wesleyan", "Wesleyan Church"),
    ("%Evangelical Free%", "Protestant", "Evangelical Free Church of America", "Evangelical Free Church of America"),
    ("%Evangelical Covenant%", "Protestant", "Evangelical Covenant", "Evangelical Covenant Church"),
    ("%Christian & Missionary Alliance%", "Protestant", "Christian and Missionary Alliance", "Christian and Missionary Alliance"),
    ("%Community of Christ%", "Restorationist", "Community of Christ", "Community of Christ"),
    ("%Adventist%", "Protestant", "Adventist", None),
    ("%Church of Christ %", "Restorationist", "Churches of Christ", "Churches of Christ"),
    ("%Church of Christ,%", "Restorationist", "Churches of Christ", "Churches of Christ"),
    ("%Church of God%", "Protestant", "Church of God (Cleveland, TN)", "Church of God (Cleveland, TN)"),
    ("%Metropolitan Community Church%", "Protestant", "Metropolitan Community Churches", "Metropolitan Community Churches"),
    
    # ── Religious infrastructure (non-congregational, skip DeepSeek) ──
    ("%Council of Churches%", "Other", "Interdenominational", None),
    ("%Conference of Churches%", "Other", "Interdenominational", None),
    ("%Interfaith%", "Other", "Interdenominational", None),
    ("%Inter-Faith%", "Other", "Interdenominational", None),
    ("%Ecumenical%", "Other", "Interdenominational", None),
    ("%Interchurch%", "Other", "Interdenominational", None),
    ("%Inter-Church%", "Other", "Interdenominational", None),
    ("%Diocese of%", "Catholic", "Roman Catholic", None),
    ("%Archdiocese of%", "Catholic", "Roman Catholic", None),
    ("%Diocesan%", "Catholic", "Roman Catholic", None),
    ("%Synod%", "Protestant", "Lutheran (Other)", None),
    ("%Presbytery%", "Protestant", "Presbyterian", None),
]

SOURCE_PATTERNS = [
    ("churchunion_scraper", "Protestant", None),
]

pre_total = 0
legacy_cache = {}
movement_cache = {}

# Name-based
for pattern, legacy_name, tradition_name, movement_name in NAME_PATTERNS:
    cnt = c.execute("""
        SELECT COUNT(id) FROM churches
        WHERE faith='Christian' AND country='US'
        AND legacy_id IS NULL AND name LIKE ?
    """, (pattern,)).fetchone()[0]
    
    if not cnt:
        continue
    
    # Cache IDs
    if legacy_name not in legacy_cache:
        legacy_cache[legacy_name] = _get_id('legacy', legacy_name)
    if tradition_name and tradition_name not in movement_cache:
        movement_cache[tradition_name] = _get_id('tradition', tradition_name)
    if movement_name and movement_name not in movement_cache:
        movement_cache[movement_name] = _get_id('movement', movement_name)
    
    lid = legacy_cache.get(legacy_name)
    tid = movement_cache.get(tradition_name) if tradition_name else None
    mid = movement_cache.get(movement_name) if movement_name else None
    
    if not lid:
        log(f"  SKIP {pattern}: legacy '{legacy_name}' not found in table")
        continue
    
    # Build update
    if mid:
        c.execute("""
            UPDATE churches SET legacy_id=?, tradition_id=?, movement_id=?
            WHERE faith='Christian' AND country='US'
            AND legacy_id IS NULL AND name LIKE ?
        """, (lid, tid or lid, mid, pattern))
    elif tid:
        c.execute("""
            UPDATE churches SET legacy_id=?, tradition_id=?
            WHERE faith='Christian' AND country='US'
            AND legacy_id IS NULL AND name LIKE ?
        """, (lid, tid, pattern))
    else:
        c.execute("""
            UPDATE churches SET legacy_id=?
            WHERE faith='Christian' AND country='US'
            AND legacy_id IS NULL AND name LIKE ?
        """, (lid, pattern))
    
    rows = c.rowcount
    if rows:
        c.execute("""
            INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source)
            SELECT id, 'legacy_id', NULL, ?, ? FROM churches
            WHERE faith='Christian' AND country='US'
            AND legacy_id=? AND id IN (
                SELECT id FROM churches WHERE faith='Christian' AND country='US'
                AND legacy_id IS NULL AND name LIKE ?
            )
        """, (legacy_name, PRECLASS_SOURCE, lid, pattern))
        conn.commit()
        pre_total += rows
        log(f"  {pattern:45s} -> {legacy_name:15s}/{tradition_name:30s} {movement_name or '':25s} {rows:>8,}")

# Source-based
for src, legacy_name, movement_name in SOURCE_PATTERNS:
    cnt = c.execute("""
        SELECT COUNT(id) FROM churches
        WHERE faith='Christian' AND country='US'
        AND legacy_id IS NULL AND source=?
    """, (src,)).fetchone()[0]
    if not cnt:
        continue
    
    lid = legacy_cache.get(legacy_name) or _get_id('legacy', legacy_name)
    if not lid:
        log(f"  SKIP {src}: legacy '{legacy_name}' not found")
        continue
    
    mid = _get_id('movement', movement_name) if movement_name else None
    
    if mid:
        c.execute("""
            UPDATE churches SET legacy_id=?, movement_id=?
            WHERE faith='Christian' AND country='US'
            AND legacy_id IS NULL AND source=?
        """, (lid, mid, src))
    else:
        c.execute("""
            UPDATE churches SET legacy_id=?
            WHERE faith='Christian' AND country='US'
            AND legacy_id IS NULL AND source=?
        """, (lid, src))
    
    rows = c.rowcount
    if rows:
        c.execute("""
            INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source)
            SELECT id, 'legacy_id', NULL, 'preclass', ? FROM churches
            WHERE faith='Christian' AND country='US'
            AND legacy_id=? AND source=?
        """, (PRECLASS_SOURCE, lid, src))
        conn.commit()
        pre_total += rows
        log(f"  source={src:40s} -> {legacy_name:25s}                         {rows:>8,}")

log(f"\n  PHASE 0 complete: {pre_total:,} entries pre-classified")

# PHASE 0b: Set landmark_type for infrastructure orgs
log("\n  Setting landmark_type='organization' for councils/dioceses...")
c.execute("""
    UPDATE churches SET landmark_type='organization'
    WHERE faith='Christian' AND country='US' AND legacy_id IS NOT NULL
    AND landmark_type IS NULL
    AND (name LIKE '%Council of Churches%' OR name LIKE '%Conference of Churches%'
         OR name LIKE '%Interfaith%' OR name LIKE '%Ecumenical%'
         OR name LIKE '%Interchurch%' OR name LIKE '%Inter-Church%'
         OR name LIKE '%Inter-Faith%'
         OR name LIKE '%Diocese of%' OR name LIKE '%Archdiocese of%'
         OR name LIKE '%Diocesan%' OR name LIKE '%Synod%')
""")
log(f"  Landmark types updated: {c.rowcount:,}")
conn.commit()

# Re-query remaining
log("\nRe-querying after pre-classification...")
c.execute("""
    SELECT id, name, city, state, country, landmark_type, tradition
    FROM churches
    WHERE faith='Christian' AND country='US'
    AND faith_id IS NOT NULL AND legacy_id IS NULL
    AND name IS NOT NULL AND name != ''
    AND id NOT IN (SELECT DISTINCT church_id FROM enrichment_change_log WHERE change_source=?)
""", (SOURCE,))
entries = c.fetchall()
log(f"  Remaining to scan: {len(entries):,}")

# ── Group entries by state, sorted smallest→largest ──
by_state = OrderedDict()
for e in entries:
    st = str(e[3] or '??')
    by_state.setdefault(st, []).append(e)

# Sort by state count ascending
state_order = sorted(by_state.keys(), key=lambda s: len(by_state[s]))
log(f"  States to process: {len(state_order)} (smallest→largest)")
for st in state_order:
    log(f"    {st}: {len(by_state[st]):,}")

grand_total = len(entries)
total_batches = (grand_total - 1) // BATCH_SIZE + 1
log(f"  Total batches: {total_batches}")

# ── Provenance helpers ──
def log_enrichment(church_id, field, old_val, new_val):
    c.execute("INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, ?, ?, ?, ?)",
              (church_id, field, str(old_val) if old_val is not None else None,
               str(new_val) if new_val is not None else None, SOURCE))

def update_with_provenance(church_id, field, old_val, new_val):
    if old_val is None and church_id:
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
                    time.sleep(1)
                    continue
                raise

# ── Prompt ──
PROMPT = """Classify each religious site with its specific taxonomy levels.

IMPORTANT — Not everything named "church" is Christian. Watch for:
- LDS/Mormon: Latter-day Saints, Mormon, Deseret, Stake, Ward, YSA Ward → tradition="Latter-day Saints"
- Jehovah's Witnesses: Kingdom Hall, Jehovah, Witnesses → tradition="Jehovah's Witnesses"
- HINDU: mandir, temple (if Indian context), sai baba, shirdi, samsthan → faith="Hindu"
- BUDDHIST: wat, vihara, buddha → faith="Buddhist"
- MUSLIM: mosque, masjid, islamic centre → faith="Islam"

For each entry return:
- faith: Christian|Hindu|Buddhist|Islam|Judaism|Sikh|Jain|Other (only if NOT Christian)
- legacy: Protestant|Catholic|Orthodox|Anglican|Restorationist|Other (if Christian)
- tradition: Baptist|Methodist|Pentecostal|Presbyterian|Lutheran|Non-Denominational|Evangelical|Adventist|Reformed|Congregational|Holiness|Churches of Christ|Latter-day Saints|Jehovah's Witnesses|Roman Catholic|Eastern Orthodox|Oriental Orthodox|Other
- movement: if identifiable (ELCA, LCMS, SBC, Assemblies of God, United Methodist, AME, PCUSA, etc.) — otherwise null
- type: church|cathedral|temple|synagogue|mosque|mandir|gurdwara|meetinghouse|kingdom_hall|other

Return ONLY JSON array:
[{{"id": N, "faith": "...", "legacy": "...", "tradition": "...", "movement": "...", "type": "..."}}]

{items}"""

def call_deepseek(items, max_tokens=6000):
    prompt = PROMPT.format(items=json.dumps(items, indent=2))
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.05, "max_tokens": max_tokens
        }, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, timeout=120)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            jm = re.search(r'\[.*?\]', content, re.DOTALL)
            if jm:
                try:
                    return json.loads(jm.group())
                except json.JSONDecodeError:
                    log(f"  JSON PARSE ERROR")
                    return None
            log(f"  NO JSON found in response")
            return None
        log(f"  HTTP {resp.status_code}: {resp.text[:150]}")
        return None
    except Exception as e:
        log(f"  API error: {e}")
        return None

# ── Faith to culture map ──
FAITH_CULTURE = {
    'Christian': 555, 'Islam': 555, 'Judaism': 555,
    'Hindu': 556, 'Buddhist': 556, 'Sikh': 556, 'Jain': 556,
    'Shinto': 557, 'Taoist': 557, 'Confucian': 557,
}

def process_results(results, st_counters):
    for r in results:
        id_ = r.get("id")
        if not id_:
            continue
        
        faith = (r.get("faith") or "").strip()
        legacy = (r.get("legacy") or "").strip()
        tradition = (r.get("tradition") or "").strip()
        movement = (r.get("movement") or "").strip() or None
        ftype = (r.get("type") or "").strip().lower().replace(' ', '_')
        
        # Handle faith change (non-Christian)
        if faith and faith.lower() != "christian":
            new_faith = faith.capitalize()
            old_faith = c.execute("SELECT faith FROM churches WHERE id=?", (id_,)).fetchone()
            if old_faith and old_faith[0] != new_faith:
                update_with_provenance(id_, 'faith', old_faith[0], new_faith)
                cult = FAITH_CULTURE.get(new_faith, 6)
                c.execute("UPDATE churches SET culture_id=? WHERE id=?", (cult, id_))
                st_counters['faith'] += 1
                continue  # skip legacy/tradition assignment for non-Christians
        
        # Set legacy
        if legacy:
            old = c.execute("SELECT legacy_id FROM churches WHERE id=?", (id_,)).fetchone()
            leg_id = c.execute("SELECT id FROM legacy WHERE name=? AND faith_id=2", (legacy,)).fetchone()
            if leg_id:
                update_with_provenance(id_, 'legacy_id', old[0] if old else None, leg_id[0])
                st_counters['legacy'] += 1
        
        # Set tradition
        if tradition:
            old = c.execute("SELECT tradition_id FROM churches WHERE id=?", (id_,)).fetchone()
            trad_id = c.execute("SELECT id FROM tradition WHERE name=?", (tradition,)).fetchone()
            if trad_id:
                update_with_provenance(id_, 'tradition_id', old[0] if old else None, trad_id[0])
                st_counters['tradition'] += 1
        
        # Set movement
        if movement:
            old = c.execute("SELECT movement_id FROM churches WHERE id=?", (id_,)).fetchone()
            mov_id = c.execute("SELECT id FROM movement WHERE name=?", (movement,)).fetchone()
            if mov_id:
                update_with_provenance(id_, 'movement_id', old[0] if old else None, mov_id[0])
                st_counters['movement'] += 1
        
        # Set landmark_type
        if ftype:
            old = c.execute("SELECT landmark_type FROM churches WHERE id=?", (id_,)).fetchone()
            old_val = old[0] if old else None
            if old_val != ftype:
                update_with_provenance(id_, 'landmark_type', old_val, ftype)
                st_counters['type'] += 1

# ── Scan: per-state, smallest→largest ──
grand_faith = 0
grand_legacy = 0
grand_tradition = 0
grand_movement = 0
grand_type = 0
grand_fail = 0
grand_batch = 0
states_done = 0

log(f"\n{'='*60}")
log(f"Starting scan — {len(state_order)} states, {grand_total:,} entries")
log(f"{'='*60}")

for st in state_order:
    state_entries = by_state[st]
    state_total = len(state_entries)
    st_batches = (state_total - 1) // BATCH_SIZE + 1
    
    # Per-state counters
    stc = {'faith': 0, 'legacy': 0, 'tradition': 0, 'movement': 0, 'type': 0}
    st_fail = 0
    st_start = datetime.now(timezone.utc)
    
    log(f"\n── {st} ({state_total:,} entries, {st_batches} batches) ──")
    
    for cs in range(0, state_total, BATCH_SIZE):
        chunk = state_entries[cs:cs + BATCH_SIZE]
        chunk_size = len(chunk)
        items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
                  "state": str(e[3] or ''), "country": str(e[4] or '')} for e in chunk]
        bn = cs // BATCH_SIZE + 1
        grand_batch += 1
        
        # Snapshot before this batch
        prev = stc.copy()
        prev_fail = st_fail
        
        results = call_deepseek(items)
        if not results:
            time.sleep(2)
            results = call_deepseek(items)  # retry once
        
        if results:
            process_results(results, stc)
            conn.commit()
        else:
            st_fail += 1
        
        # Batch deltas
        b_faith = stc['faith'] - prev['faith']
        b_legacy = stc['legacy'] - prev['legacy']
        b_trad = stc['tradition'] - prev['tradition']
        b_mov = stc['movement'] - prev['movement']
        b_type = stc['type'] - prev['type']
        b_fail = st_fail - prev_fail
        
        # Progress within state every 10 batches or last batch
        if bn % 10 == 0 or bn == st_batches:
            processed = cs + chunk_size
            pct_b = lambda n: f"{n/chunk_size*100:.0f}%" if chunk_size else "-"
            pct_s = lambda n: f"{n/processed*100:.0f}%" if processed else "-"
            elapsed = (datetime.now(timezone.utc) - st_start).total_seconds()
            rate = processed / elapsed if elapsed > 0 else 0
            log(f"  [{st}] batch {bn}/{st_batches} | "
                f"moved:{b_faith}({pct_b(b_faith)}) leg:{b_legacy}({pct_b(b_legacy)}) "
                f"trad:{b_trad}({pct_b(b_trad)}) mov:{b_mov}({pct_b(b_mov)}) "
                f"type:{b_type}({pct_b(b_type)}) fail:{b_fail} | "
                f"st: mov:{stc['faith']}({pct_s(stc['faith'])}) "
                f"leg:{stc['legacy']}({pct_s(stc['legacy'])}) "
                f"trad:{stc['tradition']}({pct_s(stc['tradition'])}) | "
                f"{rate:.0f}/s")
    
    # State summary
    st_elapsed = (datetime.now(timezone.utc) - st_start).total_seconds()
    st_rate = state_total / st_elapsed if st_elapsed > 0 else 0
    pct = lambda n: f"{n/state_total*100:.1f}%"
    
    log(f"  ✅ {st} DONE — {state_total:,} in {st_elapsed:.0f}s ({st_rate:.0f}/s) | "
        f"faith:{stc['faith']}({pct(stc['faith'])}) leg:{stc['legacy']}({pct(stc['legacy'])}) "
        f"trad:{stc['tradition']}({pct(stc['tradition'])}) "
        f"mov:{stc['movement']}({pct(stc['movement'])}) type:{stc['type']}({pct(stc['type'])}) "
        f"fail:{st_fail}")
    
    grand_faith += stc['faith']
    grand_legacy += stc['legacy']
    grand_tradition += stc['tradition']
    grand_movement += stc['movement']
    grand_type += stc['type']
    grand_fail += st_fail
    states_done += 1
    
    # Grand progress
    scanned = sum(len(by_state[s]) for s in state_order[:states_done])
    gpct = lambda n: f"{n/scanned*100:.1f}%" if scanned else "-"
    log(f"  🏁 Overall: {states_done}/{len(state_order)} states, {scanned:,}/{grand_total:,} entries | "
        f"faith:{grand_faith}({gpct(grand_faith)}) leg:{grand_legacy}({gpct(grand_legacy)}) "
        f"trad:{grand_tradition}({gpct(grand_tradition)}) "
        f"mov:{grand_movement}({gpct(grand_movement)}) type:{grand_type}({gpct(grand_type)}) "
        f"fail:{grand_fail}")

# ── Final Summary ──
log(f"\n{'='*60}")
log(f"=== SCAN COMPLETE ===")
log(f"  States processed:     {states_done}")
log(f"  Entries scanned:      {grand_total:,}")
log(f"  Total batches:        {grand_batch}")
log(f"  Moved to other faith: {grand_faith:,}")
log(f"  Legacy assigned:      {grand_legacy:,}")
log(f"  Tradition assigned:   {grand_tradition:,}")
log(f"  Movement assigned:    {grand_movement:,}")
log(f"  Landmark types set:   {grand_type:,}")
log(f"  Failed batches:       {grand_fail}")
log(f"  Started:  {STARTED_AT}")
log(f"  Finished: {datetime.now(timezone.utc).isoformat()}")
log(f"{'='*60}")

conn.close()
