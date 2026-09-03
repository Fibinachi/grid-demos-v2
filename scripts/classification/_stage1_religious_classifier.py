"""
Stage 1 Classifier: Is this a religious organization?

Pipeline step 1 of 4. Pure AI classification — no heuristics, no shortcuts.
For every entry with insufficient classification, asks DeepSeek:
  1. Is this a religious organization?
  2. If yes: what civilizational_family + faith?
  3. If no: mark as Non-Religious and exit the pipeline.

Batches of 100. Resumable via enrichment_change_log.
"""
import sqlite3, os, json, requests, sys, re, time
from datetime import datetime, timezone
from unidecode import unidecode

DB_PATH = r"E:\grid\churches.db"
SOURCE_NAME = "stage1_religious_classifier"
BATCH_SIZE = 50

# ── Faith → taxonomy_id mapping (level 1 nodes) ──
FAITH_TO_TAXONOMY = {
    'Christian': 2,     'Islam': 4,        'Hindu': 3,
    'Buddhist': 1,      'Judaism': 5,      'Sikh': 55,
    'Jain': 46,         'Shinto': 7,       'Taoist': 59,
    'Confucian': 45,    'Bahai': 695,      'Zoroastrian': 61,
    'Pagan': 53,        'Animist': 39,     'Other': 52,
    'Non-Religious': 51,
}

# ── Faith → civilizational_family mapping ──
FAITH_TO_CIV = {
    'Christian': 'ABRAHAMIC',   'Islam': 'ABRAHAMIC',
    'Judaism': 'ABRAHAMIC',     'Bahai': 'ABRAHAMIC',
    'Other Abrahamic': 'ABRAHAMIC',
    'Hindu': 'DHARMIC',         'Buddhist': 'DHARMIC',
    'Sikh': 'DHARMIC',          'Jain': 'DHARMIC',
    'Shinto': 'TAOIC',          'Taoist': 'TAOIC',
    'Confucian': 'TAOIC',
    'Pagan': 'OTHER',           'Animist': 'OTHER',
    'Zoroastrian': 'OTHER',     'Other': 'OTHER',
    'Non-Religious': None,
}

# ── Generic tradition values that mean "unclassified" ──
# Note: NULL is handled separately via "tradition IS NULL" in the query
GENERIC_TRADITIONS = [
    'Christian', 'Muslim', 'Jewish', 'Hindu', 'Buddhist',
    'Sikh', 'Jain', 'Taoist', 'Shinto', 'Bahai', 'Other',
    '', 'NULL'
]

# ── DB setup ──
conn = sqlite3.connect(DB_PATH, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=5000")
conn.execute("PRAGMA foreign_keys=ON")
c = conn.cursor()

# ── API provider selection ──
GEMINI_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY")

if GEMINI_KEY:
    PROVIDER = "gemini"
    print(f"Using Gemini API (faster, cheaper)")
elif DEEPSEEK_KEY:
    PROVIDER = "deepseek"
    print(f"Using DeepSeek API")
else:
    print("ERROR: Set GEMINI_API_KEY or DEEPSEEK_API_KEY")
    sys.exit(1)

print("Resuming from classification_history...", end=" ", flush=True)
# Entries already classified by Stage 1
c.execute("SELECT DISTINCT church_id FROM classification_history WHERE stage='stage1' AND action='classified'")
already_done = {r[0] for r in c.fetchall()}

# Kickbacks from Stage 2 (entries Stage 2 thinks need re-evaluation)
c.execute("""
    SELECT DISTINCT church_id, kickback_reason 
    FROM classification_history 
    WHERE stage='stage2' AND action='kickback' AND kickback_target='stage1'
      AND church_id NOT IN (SELECT church_id FROM classification_history WHERE stage='stage1' AND action='resolved')
""")
kickbacks = {r[0]: r[1] for r in c.fetchall()}
print(f"{len(already_done):,} already classified, {len(kickbacks):,} kickbacks from Stage 2")

# ── Query candidates: all entries with generic/NULL tradition ──
# Split into two fast queries instead of one slow OR query
print("Querying NULL tradition entries...", end=" ", flush=True)
c.execute("""
    SELECT id, name, city, state, country, landmark_type, faith, tradition, civilizational_family
    FROM churches WHERE tradition IS NULL
    AND NOT (name LIKE 'Q%' AND CAST(substr(name,2) AS INTEGER) > 0)
    ORDER BY country, name
""")
null_entries = c.fetchall()
print(f"{len(null_entries):,} found")

print("Querying generic tradition entries...", end=" ", flush=True)
placeholders = ','.join(['?' for _ in GENERIC_TRADITIONS])
c.execute(f"""
    SELECT id, name, city, state, country, landmark_type, faith, tradition, civilizational_family
    FROM churches WHERE tradition IN ({placeholders})
    AND NOT (name LIKE 'Q%' AND CAST(substr(name,2) AS INTEGER) > 0)
    ORDER BY country, name
""", GENERIC_TRADITIONS)
generic_entries = c.fetchall()
print(f"{len(generic_entries):,} found")

# Merge (no duplicates since NULL != any generic string)
all_entries = null_entries + generic_entries
entries = [e for e in all_entries if e[0] not in already_done]

# Add kickback entries (force re-evaluation even if already classified)
# Extend tuple with kickback_reason as extra field
kickback_entries = []
for e in all_entries:
    if e[0] in kickbacks:
        # Add kickback_reason as 9th element (after civilizational_family)
        kickback_entries.append(e + (kickbacks[e[0]],))
if kickback_entries:
    # Remove kickback IDs from regular entries if they were there
    kb_ids = {e[0] for e in kickback_entries}
    entries = [e for e in entries if e[0] not in kb_ids]
    entries = kickback_entries + entries  # Process kickbacks first

print(f"\nStage 1 candidates: {len(all_entries):,} total, {len(entries):,} remaining "
      f"({len(already_done):,} already classified, {len(kickbacks):,} kickbacks)")
print(f"Batches: ~{(len(entries) - 1) // BATCH_SIZE + 1 if entries else 0}")
if kickback_entries:
    print(f"  ⚠ {len(kickback_entries)} entries with kickback context from Stage 2")
print()
sys.stdout.flush()

# ── Prompt template ──
SYSTEM_PROMPT = """You are classifying entries from a global database of religious sites. Many entries may not be religious organizations at all.

Your task: For each entry, determine:
1. **religious**: Is this a religious organization, place of worship, or religious ministry? 
   - YES: churches, mosques, temples, synagogues, gurdwaras, shrines, monasteries, religious schools, religious charities, denominational offices, religious retreats, religious music organizations explicitly tied to worship
   - NO: secular businesses (LLCs, Inc that are clearly commercial), non-religious non-profits (healthcare, housing, generic charities), government buildings, purely cultural centers, professional associations (guild of organists, medical associations), political organizations, secular schools, preschools/daycares without religious affiliation
   - BORDERLINE (still YES): religious media/broadcasting ministries, religious bookstores, religious summer camps, faith-based counseling centers

2. **civilization** (if religious): ABRAHAMIC | DHARMIC | TAOIC | OTHER
   - ABRAHAMIC: Christian, Islam, Judaism, Bahai, Other Abrahamic
   - DHARMIC: Hindu, Buddhist, Sikh, Jain
   - TAOIC: Shinto, Taoist, Confucian
   - OTHER: Pagan, Animist, Zoroastrian, Indigenous/Traditional, New Age, Spiritualist, Chinese Folk, Caodaism, Tenrikyo, Satanism, etc.

3. **faith** (if religious): Christian | Islam | Hindu | Buddhist | Judaism | Sikh | Jain | Shinto | Taoist | Confucian | Bahai | Zoroastrian | Pagan | Animist | Other
   - **NAME WINS over metadata**: If the name contains "Church", "Cathedral", "Saint", "St.", "Parish", "Anglican", "Methodist", "Reformed", "Baptist", "Presbyterian", "NG Kerk", "Moederkerk", "Groote Kerk" → ALWAYS Christian, regardless of current_faith or type. These are definitive Christian keywords.
   - "mosque", "masjid", "masjed", "masged", "islamic" → ALWAYS Islam. Names containing these are definitive, override any metadata.
   - "synagogue", "shul", "beit", "beth" (with type synagogue) → ALWAYS Judaism. Names containing these are definitive.
   - "temple" in India/Nepal → Hindu; in Thailand/Cambodia/Japan → Buddhist; in China → Buddhist or Taoist
   - "gurdwara" → Sikh
   - "jinja", "jingu", "shrine" in Japan → Shinto

4. **confidence**: 0.0 to 1.0
   - 0.95+: very clear from name (e.g., "First Baptist Church" → Christian)
   - 0.85-0.94: good signal, minor ambiguity
   - 0.70-0.84: educated guess, name is ambiguous
   - <0.70: uncertain, needs human review

5. **reasoning**: Brief explanation (5-15 words)

Return ONLY a JSON array: [{"idx": N, "religious": true/false, "civilization": "ABRAHAMIC"|"DHARMIC"|"TAOIC"|"OTHER"|null, "faith": "...", "confidence": 0.0-1.0, "reasoning": "..."}]
"""


def build_items(chunk):
    """Build the items list for the API call. Handles both regular entries (9 fields)
    and kickback entries (10 fields with kickback_reason)."""
    items = []
    for e in chunk:
        item = {
            "idx": e[0],  # church id
            "name": str(e[1] or ''),
            "city": str(e[2] or ''),
            "state": str(e[3] or ''),
            "country": str(e[4] or ''),
            "type": str(e[5] or ''),
            "current_faith": str(e[6] or ''),
            "current_tradition": str(e[7] or ''),
            "current_civ": str(e[8] or ''),
        }
        # Kickback entries have a 10th field: kickback_reason
        if len(e) >= 10 and e[9]:
            item["kickback_context"] = str(e[9])
        items.append(item)
    return items


def build_user_prompt(batch_items):
    """Build the numbered list prompt from batch items."""
    lines = []
    for item in batch_items:
        line = (
            f'{item["idx"]}. name="{item["name"]}" | type={item["type"]} | '
            f'country={item["country"]} | city={item["city"]} | state={item["state"]} | '
            f'current_faith={item["current_faith"]} | current_trad={item["current_tradition"]} | '
            f'current_civ={item["current_civ"]}'
        )
        if item.get("kickback_context"):
            line += f' | KICKBACK: Stage 2 flagged this for re-evaluation. Reason: {item["kickback_context"]}'
        lines.append(line)
    return "\n".join(lines)


def extract_json(content):
    """Extract JSON array from LLM response text. Handles markdown fences,
    leading/trailing text, and nested array issues."""
    if not content:
        return None

    # Strip markdown code fences
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', content.strip())
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)

    # Try to find the outermost JSON array using balanced bracket matching
    # This is more robust than greedy .* which breaks on nested arrays
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
                try:
                    return json.loads(cleaned[start:i+1])
                except json.JSONDecodeError:
                    pass
    return None


def call_gemini(batch_items):
    """Call Gemini API. Returns parsed JSON or None."""
    user_prompt = build_user_prompt(batch_items)
    full_prompt = SYSTEM_PROMPT + "\n\nEntries:\n" + user_prompt

    try:
        resp = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
            json={"contents": [{"parts": [{"text": full_prompt}]}]},
            timeout=60
        )
        if resp.status_code == 200:
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return extract_json(text)
        if resp.status_code == 429:
            print(f"\n  Gemini rate limit (429)")
            return None
        print(f"\n  Gemini HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        print(f"\n  Gemini error: {e}")
        return None


def call_deepseek(batch_items, attempt=1):
    """Call DeepSeek API. Returns parsed JSON or None."""
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
                "max_tokens": 8192
            },
            headers={
                "Authorization": f"Bearer {DEEPSEEK_KEY}",
                "Content-Type": "application/json"
            },
            timeout=120
        )
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            result = extract_json(content)
            if result is not None:
                return result
            print(f"\n  JSON PARSE (attempt {attempt})")
            print(f"  First 150 chars: {content[:150]}")
            print(f"  Last 150 chars: {content[-150:]}")
            return None
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < 4:
            return None
        print(f"\n  DeepSeek HTTP {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as e:
        if attempt < 4:
            print(f"\n  DeepSeek error (attempt {attempt}): {e}")
            return None
        return None


def call_llm(batch_items):
    """Dispatch to the active LLM provider."""
    if PROVIDER == "gemini":
        return call_gemini(batch_items)
    else:
        return call_with_retry(batch_items)


def call_with_retry(batch_items, max_attempts=4):
    """Call DeepSeek with retries + exponential backoff."""
    for attempt in range(1, max_attempts + 1):
        result = call_deepseek(batch_items, attempt=attempt)
        if result is not None:
            return result
        if attempt < max_attempts:
            wait = min(2 ** attempt * 2, 30)
            print(f"  Retrying in {wait}s...")
            time.sleep(wait)
    return None


def log_classification(church_id, action, field_name=None, old_val=None, new_val=None,
                      confidence=None, reasoning=None, kickback_target=None, kickback_reason=None,
                      batch_id=None):
    """Log a pipeline action to classification_history."""
    c.execute(
        "INSERT INTO classification_history "
        "(church_id, stage, action, field_name, old_value, new_value, confidence, "
        "reasoning, kickback_target, kickback_reason, batch_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (church_id, 'stage1', action, field_name,
         str(old_val) if old_val is not None else None,
         str(new_val) if new_val is not None else None,
         confidence, reasoning, kickback_target, kickback_reason, batch_id))


def log_enrichment(church_id, field, old_val, new_val):
    """Log a data field change to enrichment_change_log."""
    c.execute(
        "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) "
        "VALUES (?, ?, ?, ?, ?)",
        (church_id, field,
         str(old_val) if old_val is not None else None,
         str(new_val) if new_val is not None else None,
         SOURCE_NAME))


def update_field(church_id, field, new_val):
    """Update a field with provenance tracking. Only writes if value changed."""
    c.execute(f"SELECT {field} FROM churches WHERE id=?", (church_id,))
    row = c.fetchone()
    if not row:
        return False
    old_val = row[0]
    # Normalize for comparison
    if str(old_val) != str(new_val):
        c.execute(f"UPDATE churches SET {field}=? WHERE id=?", (new_val, church_id))
        log_enrichment(church_id, field, old_val, new_val)
        return True
    return False


def normalize_display_name(name, name_en=None, name_tl=None):
    """Normalize a church name for live display. Prefers English/transliterated
    variants, title-cases ALL CAPS, expands abbreviations, transliterates non-Latin
    scripts via unidecode. Does NOT modify the DB."""
    # Prefer English name, then transliterated, then raw
    n = (name_en or name_tl or name or '').strip()
    if not n:
        return ""
    # Fix unicode apostrophes → straight
    for smart in '\u2019\u2018\u201a\u201b\u00c6\u00e6':
        n = n.replace(smart, "'")
    n = n.replace('Æ', "'").replace('æ', "'")
    # Transliterate any remaining non-Latin characters (Chinese, Arabic, Cyrillic, etc.)
    if not all(ord(c) < 128 for c in n):
        n = unidecode(n)
    # ALL CAPS → Title Case (but preserve mixed-case already)
    if n == n.upper() and len(n) > 4:
        n = n.title()
    # Expand St./Mt./Ft. → Saint/Mount/Fort when followed by name
    n = re.sub(r'\bSt\.(?=\s+[A-Z][a-z])', 'Saint', n)
    n = re.sub(r'\bMt\.(?=\s+[A-Z][a-z])', 'Mount', n)
    n = re.sub(r'\bFt\.(?=\s+[A-Z][a-z])', 'Fort', n)
    # Collapse multiple spaces
    n = re.sub(r'\s+', ' ', n).strip()
    return n


def process_results(results, batch_id, kickback_ids):
    """Apply Stage 1 results to the database. Logs to both classification_history
    and enrichment_change_log."""
    global total_processed, total_religious, total_nonreligious, low_confidence

    if not results:
        return

    for r in results:
        idx = r.get("idx")
        is_religious = r.get("religious", False)
        civilization = r.get("civilization")
        faith = r.get("faith", "")
        confidence = r.get("confidence", 0.0)
        reasoning = r.get("reasoning", "")
        is_kickback = idx in kickback_ids

        if not idx:
            continue

        try:
            # Verify the ID exists
            c.execute("SELECT id, name, city, country, name_english, name_transliterated FROM churches WHERE id=?", (idx,))
            row = c.fetchone()
            if not row:
                continue
            church_name = normalize_display_name(row[1], row[4], row[5])[:60]
            church_loc = f"{row[2]}, {row[3]}" if row[2] else str(row[3] or '')

            # ── Log classification action ──
            log_classification(
                idx, 'classified',
                confidence=confidence, reasoning=reasoning, batch_id=batch_id)

            # ── Log kickback resolution if this was a kickback entry ──
            if is_kickback:
                log_classification(
                    idx, 'resolved',
                    reasoning=f'Re-evaluated by Stage 1: {reasoning}',
                    kickback_target='stage1', batch_id=batch_id)

            if confidence < 0.70:
                low_confidence += 1
                # Still apply, but flagged in classification_history

            if not is_religious:
                # Non-religious: faith=Non-Religious, civilization=NULL
                c.execute("SELECT faith, tradition, civilizational_family FROM churches WHERE id=?", (idx,))
                old_row = c.fetchone()

                update_field(idx, 'faith', 'Non-Religious')
                update_field(idx, 'tradition', 'non_religious')
                update_field(idx, 'civilizational_family', None)
                update_field(idx, 'taxonomy_id', 51)

                log_classification(idx, 'classified',
                    field_name='faith', old_val=old_row[0], new_val='Non-Religious',
                    confidence=confidence, reasoning='Non-religious: ' + reasoning,
                    batch_id=batch_id)
                total_nonreligious += 1

                print(f"  ❌ {idx:>8} | {church_name:<60} | {church_loc:<30} | Non-Religious ({confidence:.2f})")

            else:
                # Religious: set faith + civilization
                c.execute("SELECT faith, tradition FROM churches WHERE id=?", (idx,))
                old_faith, old_trad = c.fetchone()
                faith_changed = (old_faith != faith) if (faith and old_faith) else False

                if faith and faith in FAITH_TO_TAXONOMY:
                    if update_field(idx, 'faith', faith):
                        log_classification(idx, 'classified',
                            field_name='faith', old_val=old_faith, new_val=faith,
                            confidence=confidence, reasoning=reasoning, batch_id=batch_id)
                    if update_field(idx, 'taxonomy_id', FAITH_TO_TAXONOMY[faith]):
                        pass  # taxonomy change logged via enrichment_change_log

                if civilization:
                    if update_field(idx, 'civilizational_family', civilization):
                        log_classification(idx, 'classified',
                            field_name='civilizational_family', new_val=civilization,
                            confidence=confidence, reasoning=reasoning, batch_id=batch_id)
                elif faith in FAITH_TO_CIV:
                    civ = FAITH_TO_CIV[faith]
                    if civ and update_field(idx, 'civilizational_family', civ):
                        log_classification(idx, 'classified',
                            field_name='civilizational_family', new_val=civ,
                            confidence=confidence, reasoning=reasoning, batch_id=batch_id)

                # Set tradition to faith.lower() if NULL or generic
                if old_trad is None or (old_trad and str(old_trad) in GENERIC_TRADITIONS):
                    new_trad = faith.lower() if faith else 'unknown'
                    if old_trad != new_trad:
                        update_field(idx, 'tradition', new_trad)
                elif faith_changed and old_trad and str(old_trad) not in GENERIC_TRADITIONS:
                    # Faith changed but tradition was specific — clear it (unlikely case)
                    update_field(idx, 'tradition', None)

                total_religious += 1

                icon = "⚠" if confidence < 0.70 else ("🔄" if is_kickback else "✅")
                print(f"  {icon} {idx:>8} | {church_name:<60} | {church_loc:<30} | {faith} ({confidence:.2f})  {reasoning}")

            total_processed += 1

        except sqlite3.OperationalError as e:
            print(f"\n  DB error for id={idx}: {e}")
            conn.rollback()
            time.sleep(0.5)
            continue


# ── Main scan loop ──
total_processed = 0
total_religious = 0
total_nonreligious = 0
low_confidence = 0
total_failed = 0
total_batches = (len(entries) - 1) // BATCH_SIZE + 1 if entries else 0
start_time = time.time()
kickback_ids = set(kickbacks.keys()) if kickbacks else set()

for batch_num in range(0, len(entries), BATCH_SIZE):
    chunk = entries[batch_num:batch_num + BATCH_SIZE]
    batch_items = build_items(chunk)
    bn = batch_num // BATCH_SIZE + 1
    batch_id = f"stage1_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{bn}"

    results = call_llm(batch_items)

    if results:
        process_results(results, batch_id, kickback_ids)
        conn.commit()
    else:
        total_failed += len(chunk)
        print(f"\n  BATCH {bn}/{total_batches} FAILED after retries, skipping {len(chunk)} items")

    # Progress
    done = min(batch_num + BATCH_SIZE, len(entries))
    pct = done / len(entries) * 100 if entries else 0
    elapsed = time.time() - start_time
    rate = done / elapsed if elapsed > 0 else 0
    eta = (len(entries) - done) / rate if rate > 0 else 0

    print(f"\r  Batch {bn}/{total_batches} | {done:,}/{len(entries):,} ({pct:.1f}%) | "
          f"religious: {total_religious:,} | non-religious: {total_nonreligious:,} | "
          f"low-conf: {low_confidence:,} | failed: {total_failed:,} | "
          f"{rate:.0f}/s | ETA {eta/60:.0f}m",
          end="")
    sys.stdout.flush()

    time.sleep(0.5)  # Rate limit courtesy

print()
elapsed = time.time() - start_time
print(f"\n=== Stage 1 Complete ===")
print(f"  Runtime: {elapsed/60:.1f} minutes")
print(f"  Processed: {total_processed:,}")
print(f"  Religious: {total_religious:,}")
print(f"  Non-Religious: {total_nonreligious:,}")
print(f"  Low confidence (still applied): {low_confidence:,}")
print(f"  Failed batches: {total_failed:,}")

# ── Summary ──
print("\n=== Classification History Summary ===")
for row in c.execute("""
    SELECT action, COUNT(*) FROM classification_history
    WHERE stage='stage1' 
    GROUP BY action ORDER BY COUNT(*) DESC
"""):
    print(f"  {row[0]:25s} {row[1]:>8,}")

print("\n=== Post-Stage 1 Faith Distribution ===")
for row in c.execute("""
    SELECT c.faith, COUNT(*) FROM churches c
    WHERE c.id IN (SELECT DISTINCT church_id FROM classification_history WHERE stage='stage1' AND action='classified')
    GROUP BY c.faith ORDER BY COUNT(*) DESC
"""):
    print(f"  {row[0]:25s} {row[1]:>8,}")

remaining = c.execute("""
    SELECT COUNT(*) FROM churches
    WHERE tradition IS NULL
       OR tradition IN ('Christian','Muslim','Jewish','Hindu','Buddhist','Sikh','Jain','Taoist','Shinto','Other','Bahai')
""").fetchone()[0]
print(f"\n  Remaining unclassified: {remaining:,}")

conn.close()
print("Done.")
