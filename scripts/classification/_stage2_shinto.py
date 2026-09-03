"""
Stage 2 Classifier — Shinto: What kind of Shinto?

Classifies Shinto entries into:
  - Shrine Shinto → general / Ise / Yoshida
  - Sect Shinto → general / Tenrikyo / Konkokyo / etc.
  - Folk Shinto

Phase 1: Fix obviously wrong traditions (Mahayana, Methodist, etc. on Shinto entries)
Phase 2: Classify generic 'shinto' entries using name patterns + DeepSeek
Phase 3 (optional): Refine Shrine Shinto entries using Japanese name patterns
"""
import sqlite3, os, json, requests, sys, re, time
from datetime import datetime, timezone
from unidecode import unidecode

DB_PATH = r"E:\grid\churches.db"
SOURCE_NAME = "stage2_shinto_classifier"
BATCH_SIZE = 40  # Smaller batches for more detailed classification

# ── Shinto tradition → taxonomy_id mapping ──
SHINTO_TAXONOMY = {
    # Shrine Shinto
    'shrine_shinto': 534,           # Shrine Shinto (general)
    'shrine_shinto_general': 534,
    'ise_shinto': 535,              # Ise Shinto
    'yoshida_shinto': 536,          # Yoshida Shinto
    # Sect Shinto
    'sect_shinto': 537,             # Sect Shinto (general)
    'sect_shinto_general': 537,
    'tenrikyo': 537,                # Tenrikyo (under Sect Shinto)
    'konkokyo': 537,                # Konkokyo (under Sect Shinto)
    'konko': 537,
    'tensho_kotai': 537,            # Tensho Kotai Jingu Kyo
    # Folk Shinto
    'folk_shinto': 538,             # Folk Shinto (general)
    'folk_shinto_general': 538,
}

# ── Known non-Shinto traditions to fix ──
NON_SHINTO_TRADITIONS = [
    'Mahayana', 'Theravada', 'Vajrayana', 'Zen', 'Pure Land',
    'Vaishnavism', 'Shaivism', 'Shaktism', 'Smarta', 'Hindu',
    'African Methodist Episcopal', 'Protestant', 'Catholic', 'Orthodox',
    'Reform', 'Conservative', 'Seventh-day Adventist',
    'Jacobite Syrian Christian Church', 'Methodist', 'Baptist',
    'Lutheran', 'Presbyterian', 'Anglican', 'Pentecostal',
    'Sunni', 'Shia', 'Sufi', 'Ibadi',
    'Sikh', 'Jain', 'Taoist', 'Confucian', 'Bahai',
]

# ── Name patterns for deterministic classification ──
SHINTO_NAME_PATTERNS = [
    # (pattern, tradition, confidence)
    (r'神宮|jingu|JINGU', 'ise_shinto', 0.95),
    (r'伊勢|ise\s', 'ise_shinto', 0.95),
    (r'大社|taisha|TAISHA', 'shrine_shinto', 0.95),
    (r'神社|jinja|JINJA', 'shrine_shinto', 0.90),
    (r'神宮寺|jinguji', 'shrine_shinto', 0.90),
    (r'天理教|tenrikyo|TENRIKYO', 'tenrikyo', 0.98),
    (r'金光教|konkokyo|KONKOKYO|konko\b', 'konkokyo', 0.98),
    (r'天照皇大神宮教|tensho.kotai', 'tensho_kotai', 0.98),
    (r'宮\b|gu\b|miya\b', 'shrine_shinto', 0.85),
    (r'八幡|hachiman|HACHIMAN', 'shrine_shinto', 0.90),
    (r'稲荷|inari|INARI', 'shrine_shinto', 0.90),
    (r'天満|tenman|TENMAN', 'shrine_shinto', 0.90),
    (r'天神|tenjin|TENJIN', 'shrine_shinto', 0.90),
    (r'東照|toshogu|TOSHOGU', 'shrine_shinto', 0.90),
    # Folk patterns
    (r'道祖神|dosojin|道祖', 'folk_shinto', 0.90),
    (r'地蔵|jizo|地藏', 'folk_shinto', 0.90),
    (r'庚申|koshin', 'folk_shinto', 0.90),
]

# ── Country heuristic ──
def guess_shinto_by_country(country, landmark_type):
    """Country-based heuristic for Shinto classification."""
    lt = (landmark_type or '').lower()
    if country == 'JP':
        if lt == 'shrine':
            return 'shrine_shinto', 0.80
        return 'shrine_shinto', 0.70
    # Non-Japanese Shinto entries: likely Sect Shinto offshoots or Folk
    if country in ('US', 'BR', 'KR', 'TW'):
        return 'sect_shinto', 0.70
    return 'folk_shinto', 0.60


def classify_by_name(name, landmark_type, country):
    """Try deterministic name-based classification. Returns (tradition, confidence) or None."""
    if not name:
        return None
    for pattern, tradition, confidence in SHINTO_NAME_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return tradition, confidence
    return None


conn = sqlite3.connect(DB_PATH, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")
c = conn.cursor()

# ── Phase 1: Fix obviously wrong traditions ──
print("=" * 60)
print("PHASE 1: Fixing wrong traditions on Shinto entries")
print("=" * 60)

ph = ','.join(['?' for _ in NON_SHINTO_TRADITIONS])
wrong_rows = c.execute(f"""
    SELECT id, name, tradition, landmark_type, country
    FROM churches WHERE faith='Shinto' AND tradition IN ({ph})
    ORDER BY country, name
""", NON_SHINTO_TRADITIONS).fetchall()

print(f"Wrong traditions to fix: {len(wrong_rows):,}")
for r in c.execute(f"""
    SELECT tradition, COUNT(1) FROM churches WHERE faith='Shinto' AND tradition IN ({ph})
    GROUP BY tradition ORDER BY COUNT(1) DESC
""", NON_SHINTO_TRADITIONS):
    print(f"  {r[0]:30s}: {r[1]:,}")

if wrong_rows:
    print("\nFixing...")
    for i, (cid, name, old_trad, ltype, country) in enumerate(wrong_rows):
        # Try name-based first
        result = classify_by_name(name, ltype, country)
        if result:
            new_trad, conf = result
        else:
            new_trad, conf = guess_shinto_by_country(country, ltype)

        tax_id = SHINTO_TAXONOMY.get(new_trad, 534)
        c.execute("""UPDATE churches SET tradition=?, taxonomy_id=?, shinto_confidence=?, 
                      shinto_classification_source=?, shinto_updated=datetime('now')
                      WHERE id=?""",
                   (new_trad, tax_id, conf, 'stage2_phase1_fix', cid))
        c.execute("""INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source)
                      VALUES (?,?,?,?,?)""",
                   (cid, 'tradition', old_trad, new_trad, SOURCE_NAME))
        c.execute("""INSERT INTO classification_history (church_id, stage, action, field_name, old_value, new_value, confidence, reasoning, batch_id)
                      VALUES (?,'stage2','classified','tradition',?,?,?,'Fixed wrong tradition on Shinto entry','stage2_shinto_phase1')""",
                   (cid, old_trad, new_trad, conf))
    conn.commit()
    print(f"  Fixed {len(wrong_rows):,} entries")

# ── Phase 2: Classify unclassified Shinto entries ──
print("\n" + "=" * 60)
print("PHASE 2: Classifying generic 'shinto' entries")
print("=" * 60)

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not DEEPSEEK_KEY:
    print("No DeepSeek API key — skipping AI phase")
    conn.close()
    sys.exit(0)

# Get unclassified Shinto entries
candidates = c.execute("""
    SELECT id, name, city, state, country, landmark_type, faith, tradition
    FROM churches WHERE faith='Shinto' AND (tradition IS NULL OR tradition IN ('shinto',''))
    ORDER BY country, name
""").fetchall()

# Check already done
c.execute("SELECT DISTINCT church_id FROM classification_history WHERE stage='stage2_shinto' AND action='classified'")
already_done = {r[0] for r in c.fetchall()}

entries = [e for e in candidates if e[0] not in already_done]
print(f"Candidates: {len(candidates):,} total, {len(entries):,} remaining ({len(already_done):,} already done)")
print(f"Batches: ~{(len(entries) - 1) // BATCH_SIZE + 1 if entries else 0}")

if not entries:
    print("Nothing to do. Done!")
    conn.close()
    sys.exit(0)

# ── Shinto-specific prompt ──
SYSTEM_PROMPT = """You are classifying Shinto religious sites into specific traditions.

For each entry, determine the most specific Shinto tradition:

**Shrine Shinto** (神社神道): The mainstream tradition centered on jinja (shrines).
  - **Shrine Shinto (general)**: Standard jinja, hachimangu, tenmangu, inari shrines, etc.
  - **Ise Shinto**: Affiliated with Ise Jingu (伊勢神宮) — jingu (神宮) shrines, imperial shrines
  - **Yoshida Shinto**: Yoshida family tradition, historic Kyoto-based

**Sect Shinto** (教派神道): Organized religious movements derived from Shinto:
  - **Tenrikyo** (天理教): Major new religion founded by Nakayama Miki
  - **Konkokyo** (金光教): Founded by Kawate Bunjiro, focus on Konjin deity
  - **Tensho Kotai Jingu Kyo**: Founded by Kitamura Sayo ("Dancing Goddess")
  - **Sect Shinto (general)**: Other sectarian groups (Kurozumikyo, Fuso-kyo, Jikko-kyo, etc.)

**Folk Shinto** (民俗神道): Local/folk practices — dosojin (道祖神), koshin (庚申) stones, jizo (地蔵), village kami

Key name signals:
- 神宮/jingu → Ise Shinto
- 大社/taisha → major Shrine Shinto
- 神社/jinja → Shrine Shinto
- 天理教/Tenrikyo → Tenrikyo (Sect)
- 金光教/Konkokyo → Konkokyo (Sect)
- 道祖神/dosojin → Folk Shinto
- Country=JP, type=shrine → likely Shrine Shinto
- Country≠JP → likely Sect Shinto (missionary offshoot) or Folk

Return ONLY a JSON array: [{"idx": N, "tradition": "shrine_shinto|ise_shinto|yoshida_shinto|tenrikyo|konkokyo|tensho_kotai|sect_shinto|folk_shinto", "confidence": 0.0-1.0, "reasoning": "..."}]
"""


def build_items(chunk):
    items = []
    for e in chunk:
        items.append({
            "idx": e[0],
            "name": str(e[1] or ''),
            "city": str(e[2] or ''),
            "state": str(e[3] or ''),
            "country": str(e[4] or ''),
            "type": str(e[5] or ''),
            "current_faith": str(e[6] or ''),
            "current_tradition": str(e[7] or ''),
        })
    return items


def build_user_prompt(batch_items):
    lines = []
    for item in batch_items:
        line = (f'{item["idx"]}. name="{item["name"]}" | type={item["type"]} | '
                f'country={item["country"]} | city={item["city"]}')
        lines.append(line)
    return "\n".join(lines)


def call_deepseek(batch_items):
    user_prompt = build_user_prompt(batch_items)
    try:
        resp = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.05,
                "max_tokens": 4000
            },
            headers={"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"},
            timeout=120
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            cleaned = re.sub(r'^```(?:json)?\s*\n?', '', content.strip())
            cleaned = re.sub(r'\n?```\s*$', '', cleaned)
            start = cleaned.find('[')
            if start == -1:
                return None
            depth = 0
            for i in range(start, len(cleaned)):
                if cleaned[i] == '[':
                    depth += 1
                elif cleaned[i] == ']':
                    depth -= 1
                    if depth == 0:
                        return json.loads(cleaned[start:i+1])
        elif resp.status_code in (429, 500, 502, 503, 504):
            return None
        return None
    except Exception:
        return None


# ── Name-based pre-filter ──
name_hits = 0
for e in entries:
    result = classify_by_name(e[1], e[5], e[4])
    if result:
        trad, conf = result
        tax_id = SHINTO_TAXONOMY.get(trad, 534)
        c.execute("""UPDATE churches SET tradition=?, taxonomy_id=?, shinto_confidence=?,
                      shinto_classification_source=?, shinto_updated=datetime('now')
                      WHERE id=?""",
                   (trad, tax_id, conf, 'stage2_name_pattern', e[0]))
        c.execute("""INSERT INTO classification_history (church_id, stage, action, field_name, new_value, confidence, reasoning, batch_id)
                      VALUES (?,'stage2_shinto','classified','tradition',?,?,'Name pattern match','stage2_shinto_pattern')""",
                   (e[0], trad, conf))
        name_hits += 1

conn.commit()
already_done.update({e[0] for e in entries if classify_by_name(e[1], e[5], e[4])})
entries = [e for e in entries if e[0] not in already_done]
print(f"\nName-pattern matches: {name_hits:,}")
print(f"Remaining for AI: {len(entries):,}")

# ── Country-based heuristic for remaining ──
if entries:
    print(f"Batches: ~{(len(entries) - 1) // BATCH_SIZE + 1}")

# ── AI classification loop ──
total_processed = 0
total_failed = 0
counts = {}
start_time = time.time()

for batch_num in range(0, len(entries), BATCH_SIZE):
    chunk = entries[batch_num:batch_num + BATCH_SIZE]
    batch_items = build_items(chunk)
    bn = batch_num // BATCH_SIZE + 1
    total_batches = (len(entries) - 1) // BATCH_SIZE + 1
    batch_id = f"stage2_shinto_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{bn}"

    results = call_deepseek(batch_items)

    if results:
        for r in results:
            idx = r.get("idx")
            tradition = r.get("tradition", "shrine_shinto")
            confidence = r.get("confidence", 0.7)
            reasoning = r.get("reasoning", "")

            c.execute("SELECT id, name, city, country, tradition FROM churches WHERE id=?", (idx,))
            row = c.fetchone()
            if not row:
                continue

            church_name = unidecode(str(row[1] or '')[:50])
            church_loc = f"{row[2]}, {row[3]}" if row[2] else str(row[3] or '')
            old_trad = row[4]

            tax_id = SHINTO_TAXONOMY.get(tradition, 534)

            c.execute("""UPDATE churches SET tradition=?, taxonomy_id=?, shinto_confidence=?,
                          shinto_classification_source=?, shinto_updated=datetime('now')
                          WHERE id=?""",
                       (tradition, tax_id, confidence, 'stage2_deepseek', idx))
            c.execute("""INSERT INTO classification_history (church_id, stage, action, field_name, old_value, new_value, confidence, reasoning, batch_id)
                          VALUES (?,'stage2_shinto','classified','tradition',?,?,?,?,?)""",
                       (idx, old_trad, tradition, confidence, reasoning, batch_id))

            counts[tradition] = counts.get(tradition, 0) + 1
            total_processed += 1

            icon = "⚠" if confidence < 0.70 else "✅"
            print(f"  {icon} {idx:>8} | {church_name:<50} | {church_loc:<25} | {tradition} ({confidence:.2f})  {reasoning}")

        conn.commit()
    else:
        total_failed += len(chunk)

    # Progress
    done = min(batch_num + BATCH_SIZE, len(entries))
    pct = done / len(entries) * 100 if entries else 0
    elapsed = time.time() - start_time
    rate = done / elapsed if elapsed > 0 else 0
    eta = (len(entries) - done) / rate if rate > 0 else 0
    print(f"\r  Batch {bn}/{total_batches} | {done:,}/{len(entries):,} ({pct:.1f}%) | "
          f"failed: {total_failed:,} | {rate:.0f}/s | ETA {eta/60:.0f}m")
    sys.stdout.flush()
    time.sleep(0.5)

print("\n")
elapsed = time.time() - start_time
print(f"=== Stage 2 Shinto Complete ===")
print(f"  Runtime: {elapsed/60:.1f} minutes")
print(f"  Processed: {total_processed:,}")
print(f"  Failed: {total_failed:,}")
print(f"  Phase 1 fixes: {len(wrong_rows):,}")
print(f"  Name-pattern: {name_hits:,}")
print(f"\nAI classification breakdown:")
for trad, cnt in sorted(counts.items(), key=lambda x: -x[1]):
    print(f"  {trad:25s}: {cnt:,}")

conn.close()
