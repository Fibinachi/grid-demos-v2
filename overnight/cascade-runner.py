"""
GRID cascade runner — persistent background classifier (staging only).

Runs 24/7 on garage. Pulls unclassified churches from churches.db in id
order, groups by lower(trim(name)), classifies each group with the
single-shot constrained cascade prompt, validates every emitted id, and
writes results to E:\\grid\\cascade_staging.db (NOT churches.db — production
application is a separate, explicitly approved step).

Resilience:
- Model priority comes from E:\\grid\\outputs\\free-models-working.json
  (the weekly probe's master list); falls back to a built-in list.
- Per-provider throttling + 429 backoff; on repeated failure, fails over
  to the next provider/model.
- Checkpoint = max church id processed; staging has PRIMARY KEY on
  group_key so reprocessed groups are harmless (INSERT OR IGNORE).
- Safe to kill and restart at any time.

Supervised by Windows Task Scheduler (see register task below).
Logs to E:\\grid\\outputs\\cascade-runner.log.
"""

import io, json, os, sqlite3, sys, time, traceback, urllib.request, urllib.error

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"E:\grid\churches.db"
STAGING = r"E:\grid\cascade_staging.db"
MASTER = r"E:\grid\outputs\free-models-working.json"
LOG = r"E:\grid\outputs\cascade-runner.log"

BATCH_CHURCHES = 2000   # read this many ids per work unit
BATCH_GROUPS = 10       # groups per model call

RANKS = ["culture", "faith", "legacy", "tradition", "movement"]
COL = {"culture": "culture_id", "faith": "faith_id", "legacy": "legacy_id",
       "tradition": "tradition_id", "movement": "movement_id"}
PCOL = {"faith": "culture_id", "legacy": "faith_id",
        "tradition": "legacy_id", "movement": "tradition_id"}

# provider -> chat url, key env, kind, calls/min on free tier
PROVIDERS = {
    "gemini":     ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                   "GEMINI_API_KEY", "openai", 12, {}),
    "gemini-native": ("https://generativelanguage.googleapis.com/v1beta",
                      "GEMINI_API_KEY", "gemini", 12, {}),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions",
                   "OPENROUTER_API_KEY", "openai", 12,
                   {"HTTP-Referer": "https://gridataset.com",
                    "X-Title": "GRID cascade runner"}),
    "kilo":       ("https://api.kilo.ai/api/gateway/chat/completions",
                   "KILO_API_KEY", "openai", 40, {}),
    "groq":       ("https://api.groq.com/openai/v1/chat/completions",
                   "GROQ_API_KEY", "openai", 20, {}),
    "cerebras":   ("https://api.cerebras.ai/v1/chat/completions",
                   "CEREBRAS_API_KEY", "openai", 20, {}),
}

FALLBACK_MODELS = [("gemini-native", "gemini-3-flash-preview"),
                   ("openrouter", "google/gemma-4-31b-it:free")]

SYSTEM = """You are a classifier for a database of religious sites. You are
given pick lists: every legal id for each rank
(culture -> faith -> legacy -> tradition -> movement), each with its parent.

For each church, walk the cascade:
- Gate first: is this a religious site (church, chapel, cathedral,
  ministry building)? If no, "gate": false and stop for that church.
- Pick exactly one id per rank, each constrained to the CHILDREN of the
  previous pick. Parent ids are shown in the lists.
- At ANY pass you may answer "unknown" instead of forcing a pick.
  Unknown stops the descent; deeper ranks stay null. An honest unknown
  beats a wrong guess.
- Novelty: if "unknown" at tradition/movement but a REAL formation is
  present that the lists lack, include "novelty": {"suggested_parent":
  <taxonomy id from the lists>, "rationale": "<one line>"}.
- Confidence 0..1 per rank. Location and source are signals: a
  denominational directory source is a strong prior.

HARD RULES:
- Every id you emit MUST appear verbatim in the pick lists above.
  Never invent, round, or guess an id.
- "unknown" is always legal at any rank.

Return exactly one JSON object with this shape, no prose, no fences:
{"results": [{"id": 123, "gate": true, "culture": 1, "faith": 2,
"legacy": 5, "tradition": 217, "movement": "unknown",
"confidence": {"culture": 0.9, "faith": 0.8, "legacy": 0.7,
"tradition": 0.6, "movement": 0.0}, "novelty": null}]}
One entry per church, in the same order as the CHURCHES list.
If gate is false, only "id" and "gate" are needed."""


def log(msg):
    line = "%s %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_chains(db):
    chains = {}
    for rank in RANKS:
        pcol = PCOL.get(rank)
        cols = "id, name" + (", %s" % pcol if pcol else "")
        chains[rank] = {r[0]: (r[1], r[2] if pcol else None)
                        for r in db.execute("SELECT %s FROM %s" % (cols, rank))}
    return chains


def pick_lists_text(chains):
    out = []
    for rank in RANKS:
        lines = ["%s:" % rank.upper()]
        for rid in sorted(chains[rank]):
            name, pid = chains[rank][rid]
            lines.append("  [%d] %s (parent %s)" % (rid, name, pid))
        out.append("\n".join(lines))
    return "\n\n".join(out)


def model_priority():
    """[(provider, model), ...] from the probe master list, else fallback."""
    try:
        m = json.load(open(MASTER, encoding="utf-8"))
        pri = [(e["provider"], e["model"]) for e in m.get("working", [])]
        # gemini entries need the native endpoint for reliability
        pri = [("gemini-native" if p == "gemini" else p, mod)
               for p, mod in pri]
        if pri:
            return pri
    except Exception:
        pass
    return FALLBACK_MODELS


def call_model(provider, model, key, messages):
    url, _, kind, _, extra = PROVIDERS[provider]
    if kind == "gemini":
        gurl = "%s/models/%s:generateContent" % (url, model)
        data = {"system_instruction": {"parts": [{"text": messages[0]["content"]}]},
                "contents": [{"parts": [{"text": messages[1]["content"]}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 4000,
                                     "responseMimeType": "application/json"}}
        req = urllib.request.Request(
            gurl, data=json.dumps(data).encode(),
            headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=240) as r:
            body = json.load(r)
        return body["candidates"][0]["content"]["parts"][0]["text"]
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    headers.update(extra)
    req = urllib.request.Request(
        url, data=json.dumps({"model": model, "messages": messages,
                              "temperature": 0, "max_tokens": 4000,
                              "response_format": {"type": "json_object"}}).encode(),
        headers=headers)
    with urllib.request.urlopen(req, timeout=240) as r:
        body = json.load(r)
    return body["choices"][0]["message"]["content"]


def classify_batch(provider, model, key, groups, lists_text):
    user = lists_text + "\n\nCHURCHES:\n"
    for g in groups:
        c = g["rep"]
        user += ("- id=%s name=%r lat=%s lon=%s source=%r\n"
                 % (c["id"], c["name"], c["latitude"],
                    c["longitude"], c["source"]))
    messages = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": user}]
    last = None
    for attempt in range(4):
        try:
            txt = (call_model(provider, model, key, messages) or "").strip()
            if txt.startswith("```"):
                txt = txt.split("\n", 1)[1] if "\n" in txt else txt[3:]
                txt = txt.rsplit("```", 1)[0]
            d = json.loads(txt)
            res = d.get("results", d) if isinstance(d, dict) else d
            if isinstance(res, dict):
                res = [res]
            if len(res) != len(groups):
                raise ValueError("size mismatch %d != %d"
                                 % (len(res), len(groups)))
            return res
        except urllib.error.HTTPError as e:
            last = e
            time.sleep(90 * (attempt + 1) if e.code == 429 else 5 * (attempt + 1))
        except Exception as e:
            last = e
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("batch failed: %r" % (last,))


def validate(results, groups, chains):
    clean, violations = [], 0
    by_id = {g["rep"]["id"]: g for g in groups}
    for r in results:
        if r.get("id") not in by_id:
            violations += 1
            continue
        prev = None
        for rank in RANKS:
            pick = r.get(rank)
            if pick == "unknown" or pick is None:
                r[rank] = "unknown"
                prev = None
                continue
            try:
                pid = int(pick)
            except (TypeError, ValueError):
                pid = None
            ok = (pid in chains[rank]
                  and (rank == "culture" or chains[rank][pid][1] == prev))
            if not ok:
                violations += 1
                r[rank] = "unknown"
                prev = None
            else:
                r[rank] = pid
                prev = pid
        clean.append(r)
    return clean, violations


def ensure_staging():
    sdb = sqlite3.connect(STAGING)
    sdb.execute("""CREATE TABLE IF NOT EXISTS classifications (
        group_key TEXT PRIMARY KEY,
        church_ids TEXT NOT NULL,
        provider TEXT NOT NULL, model TEXT NOT NULL,
        result_json TEXT NOT NULL, created_at TEXT NOT NULL)""")
    sdb.execute("""CREATE TABLE IF NOT EXISTS runner_state (
        k TEXT PRIMARY KEY, v TEXT NOT NULL)""")
    sdb.commit()
    return sdb


def get_state(sdb, k, default="0"):
    r = sdb.execute("SELECT v FROM runner_state WHERE k=?", (k,)).fetchone()
    return r[0] if r else default


def set_state(sdb, k, v):
    sdb.execute("INSERT OR REPLACE INTO runner_state(k, v) VALUES (?, ?)", (k, v))
    sdb.commit()


def main():
    sdb = ensure_staging()
    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    db.row_factory = sqlite3.Row
    chains = load_chains(db)
    lists_text = pick_lists_text(chains)

    max_id = db.execute("SELECT MAX(id) FROM churches").fetchone()[0]
    cursor = int(get_state(sdb, "cursor", "0"))
    log("runner start: cursor=%d max_id=%d" % (cursor, max_id))

    while True:
        priority = model_priority()
        if cursor >= max_id:
            log("done: cursor reached max_id; sleeping 6h for new ingests")
            time.sleep(6 * 3600)
            max_id = db.execute("SELECT MAX(id) FROM churches").fetchone()[0]
            continue
        rows = [dict(r) for r in db.execute(
            """SELECT id, name, latitude, longitude, source
               FROM churches WHERE id > ? AND id <= ? AND taxonomy_id IS NULL
               ORDER BY id LIMIT ?""",
            (cursor, cursor + BATCH_CHURCHES, BATCH_CHURCHES))]
        if not rows:
            cursor += BATCH_CHURCHES
            set_state(sdb, "cursor", str(cursor))
            continue
        groups, seen = [], {}
        for r in rows:
            gk = (r["name"] or "").strip().lower() or ("id:%s" % r["id"])
            if gk not in seen:
                seen[gk] = {"key": gk, "rep": r, "ids": []}
                groups.append(seen[gk])
            seen[gk]["ids"].append(r["id"])
        cursor = rows[-1]["id"]
        set_state(sdb, "cursor", str(cursor))

        done = True
        for provider, model in priority:
            url, key_env, kind, cpm, _ = PROVIDERS[provider]
            key = (os.environ.get(key_env) or "").strip()
            if not key:
                continue
            interval = 60.0 / cpm
            ok, failed = 0, 0
            for i in range(0, len(groups), BATCH_GROUPS):
                batch = groups[i:i + BATCH_GROUPS]
                t0 = time.time()
                try:
                    res = classify_batch(provider, model, key, batch, lists_text)
                except Exception as e:
                    failed += 1
                    log("provider %s model %s batch failed (%d fails): %s"
                        % (provider, model, failed, str(e)[:100]))
                    if failed >= 3:
                        break
                    continue
                clean, _ = validate(res, batch, chains)
                now = time.strftime("%Y-%m-%dT%H:%M:%S")
                for g, r in zip(batch, clean):
                    sdb.execute(
                        "INSERT OR IGNORE INTO classifications VALUES (?,?,?,?,?,?)",
                        (g["key"], json.dumps(g["ids"]), provider, model,
                         json.dumps(r, ensure_ascii=False), now))
                sdb.commit()
                ok += 1
                el = time.time() - t0
                if el < interval:
                    time.sleep(interval - el)
            log("unit cursor=%d groups=%d provider=%s model=%s batches_ok=%d"
                % (cursor, len(groups), provider, model, ok))
            if ok > 0:
                done = True
                break
            done = False
        if not done:
            log("all providers failed this unit; backing off 15 min")
            time.sleep(15 * 60)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        log("RUNNER CRASH:\n" + traceback.format_exc())
        raise
