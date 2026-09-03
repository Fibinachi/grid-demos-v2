"""DeepSeek LLM scan for Taoist, Sikh, and Confucian entries.
Phase A: Fix wrong landmark_types, misclassified faiths, missing traditions.
"""
import sqlite3, os, json, requests, sys, re
from datetime import datetime

conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
if not API_KEY:
    print("ERROR: DEEPSEEK_API_KEY not set!")
    sys.exit(1)

SOURCE = 'deepseek_three_faiths_scan'
CHUNK_SIZE = 25
total_moved = 0
total_retraditioned = 0
total_retyped = 0
all_changed_ids = set()

# ── Provenance helpers ──
def log_enrichment(church_id, field, old_val, new_val):
    c.execute(
        "INSERT INTO enrichment_change_log (church_id, field_name, old_value, new_value, change_source) VALUES (?, ?, ?, ?, ?)",
        (church_id, field, str(old_val) if old_val is not None else None,
         str(new_val) if new_val is not None else None, SOURCE)
    )

def update_with_provenance(church_id, field, old_val, new_val):
    if old_val is None:
        c.execute(f"SELECT {field} FROM churches WHERE id=?", (church_id,))
        row = c.fetchone()
        old_val = row[0] if row else None
    if str(old_val) != str(new_val):
        c.execute(f"UPDATE churches SET {field}=? WHERE id=?", (new_val, church_id))
        log_enrichment(church_id, field, old_val, new_val)

def call_deepseek(items, prompt_template, max_tokens=3000):
    prompt = prompt_template.format(items=json.dumps(items, indent=2, ensure_ascii=False))
    try:
        resp = requests.post("https://api.deepseek.com/v1/chat/completions", json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.05,
            "max_tokens": max_tokens
        }, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }, timeout=90)
        if resp.status_code == 200:
            content = resp.json()["choices"][0]["message"]["content"]
            jm = re.search(r'\[.*?\]', content, re.DOTALL)
            if jm:
                return json.loads(jm.group())
            print(f"  NO JSON in response")
            return None
        print(f"  HTTP {resp.status_code}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

# ═══════════════════════════════════════════════════════════════
#  TAOIST PROMPT
# ═══════════════════════════════════════════════════════════════
TAOIST_PROMPT = """Classify each religious site as TAOIST, CHINESE_FOLK, BUDDHIST, CONFUCIAN, or OTHER.

Context: These entries are currently labeled as Taoist/Buddhist from East/Southeast Asia.

Classification rules:
- Chinese temples with 庙 (temple/miao), 宫 (gong/palace), 祠 (ci/shrine), 观 (guan/observatory), 庵 (an/nunnery), 堂 (tang/hall) → TAOIST or CHINESE_FOLK
- Confucian temples: 孔庙 (Confucian temple), 文庙 (wen miao), 学宫 (xue gong/school palace), 大成殿 (dacheng dian) → CONFUCIAN
- Buddhist temples: 寺 (si), 禅寺 (zen temple), 佛寺 (buddhist temple), wat, vihara → BUDDHIST
- Names with "church", "cathedral", "synagogue" → determine actual faith from name
- Ancestral halls (宗祠, 氏宗祠) → CHINESE_FOLK

Traditions for TAOIST: Zhengyi, Quanzhen, Folk Taoist, Way of the Celestial Masters, Shangqing, Lingbao
Traditions for CHINESE_FOLK: Chinese Folk Religion, Ancestor Worship, Mazu Worship, Wang Ye Worship
Traditions for BUDDHIST: Mahayana, Theravada, Vajrayana, Pure Land, Chan/Zen
Traditions for CONFUCIAN: Confucianism, Neo-Confucianism

Landmark types: temple, shrine, pagoda, monastery, nunnery, sanctuary

Return ONLY valid JSON array (no markdown):
[{{"id": N, "faith": "TAOIST|CHINESE_FOLK|BUDDHIST|CONFUCIAN|OTHER", "tradition": "...", "type": "temple|shrine|pagoda|..."}}]

{items}"""

# ═══════════════════════════════════════════════════════════════
#  SIKH PROMPT
# ═══════════════════════════════════════════════════════════════
SIKH_PROMPT = """Classify each religious site as SIKH, CHRISTIAN, HINDU, or OTHER.

Context: These entries are currently labeled as Sikh but some may be misclassified.

Rules for SIKH:
- Gurdwara, Sikh temple, Khalsa, Guru Granth, Singh Sabha, Gurudwara, Guru Nanak → SIKH
- Traditions: Khalsa, Namdhari, Nirankari, Sikh (general), Seva Panthi
- Type: gurdwara, temple, shrine

Rules for CHRISTIAN (move out of Sikh):
- Church, chapel, cathedral, christ, jesus, saint, st., gospel, mission, pastor, trinity → CHRISTIAN
- For CHRISTIAN, specify tradition (Catholic, Protestant, Anglican, Baptist, etc.) and type (church, chapel, cathedral)

Rules for HINDU (move out of Sikh):
- Mandir, temple with Hindu deity names (Shiva, Vishnu, Krishna, Lakshmi, Durga, Hanuman, Rama) → HINDU
- For HINDU, tradition (Vaishnavism, Shaivism, Shaktism, etc.) and type (temple, shrine)

Return ONLY valid JSON array:
[{{"id": N, "faith": "SIKH|CHRISTIAN|HINDU|OTHER", "tradition": "...", "type": "gurdwara|temple|church|..."}}]

{items}"""

# ═══════════════════════════════════════════════════════════════
#  CONFUCIAN PROMPT
# ═══════════════════════════════════════════════════════════════
CONFUCIAN_PROMPT = """Classify each Chinese religious/temple entry.

Determine the correct faith: CONFUCIAN, TAOIST, CHINESE_FOLK, or BUDDHIST.

- Confucian: 孔庙 (Confucian temple), 文庙 (wen miao/culture temple), 学宫 (xue gong/school), 大成殿 (Dacheng Hall), 孔子 (Confucius), 儒 (ru/Confucian) → CONFUCIAN
  Tradition: Confucianism, Neo-Confucianism
- Taoist: 宫 (gong), 观 (guan), 道士 (daoshi), 老君 (Laojun) → TAOIST
  Tradition: Zhengyi, Quanzhen, Folk Taoist
- Chinese Folk: 祠 (ci/ancestral shrine), 宗祠 (ancestral hall), 庙 (miao/temple, generic), 妈祖 (Mazu) → CHINESE_FOLK
  Tradition: Chinese Folk Religion, Ancestor Worship, Mazu Worship
- Buddhist: 寺 (si), 禅 (chan/zen), 佛 (buddha) → BUDDHIST
  Tradition: Mahayana, Pure Land, Chan/Zen

Landmark type: temple (default), shrine, pagoda

Return ONLY valid JSON:
[{{"id": N, "faith": "CONFUCIAN|TAOIST|CHINESE_FOLK|BUDDHIST", "tradition": "...", "type": "temple"}}]

{items}"""

# ═══════════════════════════════════════════════════════════════
#  SCAN FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def scan_faith(label, entries, prompt, faith_map):
    """Scan entries for a faith. faith_map maps DeepSeek faith outputs → DB values."""
    global total_moved, total_retraditioned, total_retyped
    
    if not entries:
        print(f"\n{label}: 0 entries, skipping")
        return
    
    print(f"\n{'='*60}")
    print(f"=== {label}: {len(entries)} entries ===")
    print(f"{'='*60}")
    
    for cs in range(0, len(entries), CHUNK_SIZE):
        chunk = entries[cs:cs+CHUNK_SIZE]
        items = [{"id": e[0], "name": str(e[1] or ''), "city": str(e[2] or ''),
                  "state": str(e[3] or ''), "country": str(e[4] or '')} for e in chunk]
        batch_num = cs // CHUNK_SIZE + 1
        total_batches = (len(entries) - 1) // CHUNK_SIZE + 1
        print(f"  Batch {batch_num}/{total_batches} ({len(items)} entries)...", end=" ")
        sys.stdout.flush()
        
        results = call_deepseek(items, prompt)
        if not results:
            print("FAILED")
            continue
        
        moved_batch = 0
        for r in results:
            id_ = r.get("id")
            faith = r.get("faith", "").upper()
            trad = r.get("tradition", "")
            ftype = (r.get("type") or "").lower()
            
            # Map faith to DB value
            mapped_faith = faith_map.get(faith, faith.title() if faith else None)
            
            if mapped_faith and mapped_faith not in (label, 'Sikh', 'Taoist'):
                # Moved OUT of this faith
                mapped_type = ftype if ftype in ('temple','shrine','church','mosque','cathedral','chapel','monastery','nunnery','pagoda','gurdwara','sanctuary','organization') else 'temple'
                update_with_provenance(id_, 'faith', None, mapped_faith)
                update_with_provenance(id_, 'tradition', None, trad or 'Other')
                update_with_provenance(id_, 'landmark_type', None, mapped_type)
                total_moved += 1
                moved_batch += 1
            else:
                # Still same faith - refine tradition and landmark_type
                # Update tradition if provided and different
                if trad:
                    c.execute("SELECT tradition FROM churches WHERE id=?", (id_,))
                    old_trad = c.fetchone()
                    if old_trad and old_trad[0] != trad and old_trad[0] not in ('', None):
                        update_with_provenance(id_, 'tradition', old_trad[0], trad)
                        total_retraditioned += 1
                    elif old_trad and (old_trad[0] is None or old_trad[0] == ''):
                        update_with_provenance(id_, 'tradition', '', trad)
                        total_retraditioned += 1
                
                # Update landmark_type if provided and different from standard
                if ftype:
                    c.execute("SELECT landmark_type FROM churches WHERE id=?", (id_,))
                    old_type = c.fetchone()
                    if old_type and old_type[0] != ftype:
                        # Only update if new type is more specific or old type was wrong
                        wrong_types = ['church','synagogue','cathedral','chapel','mosque']
                        if old_type[0] in wrong_types or (old_type[0] == 'temple' and ftype == 'gurdwara'):
                            update_with_provenance(id_, 'landmark_type', old_type[0], ftype)
                            total_retyped += 1
        
        conn.commit()
        status = []
        if moved_batch: status.append(f"{moved_batch} moved")
        print(f"OK{' (' + ', '.join(status) + ')' if status else ''}")
        all_changed_ids.update(r.get("id") for r in results)

# ═══════════════════════════════════════════════════════════════
#  PHASE A: Problematic entries only
# ═══════════════════════════════════════════════════════════════

# ── Taoist: wrong landmark_types + no tradition ──
print("="*60)
print("PHASE A: TAOIST — wrong landmark_types + missing traditions")
print("="*60)

c.execute("""SELECT id, name, city, state, country, landmark_type, tradition
    FROM churches WHERE faith='Taoist'
    AND (landmark_type IN ('synagogue','church','cathedral','chapel','mosque')
         OR tradition IS NULL OR tradition = '')
    ORDER BY country, name""")
taoist_problematic = c.fetchall()
print(f"Problematic Taoist entries: {len(taoist_problematic)}")

scan_faith('Taoist', taoist_problematic, TAOIST_PROMPT,
           {'TAOIST': 'Taoist', 'CHINESE_FOLK': 'Other', 'BUDDHIST': 'Buddhist',
            'CONFUCIAN': 'Confucian', 'OTHER': 'Other'})

# ── Sikh: wrong landmark_types + wrong traditions ──
print("\n" + "="*60)
print("PHASE A: SIKH — wrong landmark_types + wrong traditions")
print("="*60)

c.execute("""SELECT id, name, city, state, country, landmark_type, tradition
    FROM churches WHERE faith='Sikh'
    AND (landmark_type IN ('church','synagogue','cathedral','chapel','mosque')
         OR tradition IN ('Protestant','Vaishnavism','Reform','Catholic','Orthodox (Hasidic)')
         OR tradition IS NULL OR tradition = '')
    ORDER BY country, name""")
sikh_problematic = c.fetchall()
print(f"Problematic Sikh entries: {len(sikh_problematic)}")

scan_faith('Sikh', sikh_problematic, SIKH_PROMPT,
           {'SIKH': 'Sikh', 'CHRISTIAN': 'Christian', 'HINDU': 'Hindu', 'OTHER': 'Other'})

# ── Confucian: all entries need tradition ──
print("\n" + "="*60)
print("PHASE A: CONFUCIAN — all 86 entries")
print("="*60)

c.execute("""SELECT id, name, city, state, country, landmark_type, tradition
    FROM churches WHERE faith='Confucian'
    ORDER BY country, name""")
confucian_all = c.fetchall()
print(f"Confucian entries: {len(confucian_all)}")

scan_faith('Confucian', confucian_all, CONFUCIAN_PROMPT,
           {'CONFUCIAN': 'Confucian', 'TAOIST': 'Taoist', 
            'CHINESE_FOLK': 'Other', 'BUDDHIST': 'Buddhist', 'OTHER': 'Other'})

# ═══════════════════════════════════════════════════════════════
#  POST-SCAN: Normalize common issues
# ═══════════════════════════════════════════════════════════════

print("\n" + "="*60)
print("POST-SCAN: Normalization fixes")
print("="*60)

# Fix landmark_type: 'gurdwara' → keep (correct for Sikh)
# Fix any lingering 'chabad' type in non-Jewish faiths
c.execute("UPDATE churches SET landmark_type='temple' WHERE faith='Taoist' AND landmark_type='synagogue'")
n = c.rowcount
if n: print(f"  Taoist synagogue→temple: {n}")

c.execute("UPDATE churches SET landmark_type='gurdwara' WHERE faith='Sikh' AND landmark_type='synagogue'")
n = c.rowcount
if n: print(f"  Sikh synagogue→gurdwara: {n}")

c.execute("UPDATE churches SET landmark_type='gurdwara' WHERE faith='Sikh' AND landmark_type='church'")
n = c.rowcount
if n: print(f"  Sikh church→gurdwara: {n}")

conn.commit()

# ── Summary ──
print(f"\n{'='*60}")
print(f"SCAN COMPLETE")
print(f"{'='*60}")
print(f"  Entries moved to different faith: {total_moved}")
print(f"  Traditions refined: {total_retraditioned}")
print(f"  Landmark types corrected: {total_retyped}")
print(f"  Total unique churches modified: {len(all_changed_ids)}")
conn.close()
print("Done!")
