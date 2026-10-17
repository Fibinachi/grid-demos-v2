"""
Kilo cascade classifier — TRIAL RUN, 300 churches (2026-10-08).

Charles: "Can you do a trial run on the kilo classifier say 300 churches?"

150 unclassified + 150 labeled (taxonomy set). READ-ONLY vs production DB:
results go to a JSONL checkpoint; nothing is written to churches.db.

Core constrained cascade only (gate -> culture -> faith -> legacy ->
tradition -> movement, fused batched calls). Backtracking, tier-two web
search, and regional priors are spec'd in cascade-pipeline-design.md but
NOT in this trial; this validates pipeline mechanics + baseline accuracy.

Audit: for the labeled half, per-rank agreement of model picks vs the
church's existing CFLTM column values. NOTE: this measures consistency
with existing labels, not ground truth (old labels may be wrong).
Absolute accuracy needs human audit of a sample.

Run on garage (Kilo key at machine scope):
    powershell: $env:KILO_BASE_URL="https://api.kilo.ai/api/gateway"; `
      $env:KILO_MODEL="anthropic/claude-sonnet-5.5"; `
      E:\grid\.venv\Scripts\python.exe cascade-trial-300.py
"""

import argparse, json, os, sqlite3, sys, time, urllib.request

DB = r"E:\grid\churches.db"
BASE_URL = os.environ.get("GATEWAY_URL",
                          "https://api.kilo.ai/api/gateway").strip().rstrip("/")
API_KEY = (os.environ.get("GATEWAY_KEY") or os.environ.get("KILO_API_KEY") or "").strip()
MODEL = os.environ.get("KILO_MODEL",
                       "google/gemma-4-31b-it:free").strip()
CALLS_PER_MIN = float(os.environ.get("CALLS_PER_MIN", "15"))
CALL_INTERVAL = 60.0 / CALLS_PER_MIN
BATCH_GROUPS = 10
IS_OPENROUTER = "openrouter" in BASE_URL

RANKS = ["culture", "faith", "legacy", "tradition", "movement"]
COL = {"culture": "culture_id", "faith": "faith_id", "legacy": "legacy_id",
       "tradition": "tradition_id", "movement": "movement_id"}
PARENT_COL = {"faith": "culture_id", "legacy": "faith_id",
              "tradition": "legacy_id", "movement": "tradition_id"}


def die(msg):
    print("FATAL:", msg, file=sys.stderr); sys.exit(1)


def load_chains(db):
    chains = {}
    for rank in RANKS:
        pcol = PARENT_COL.get(rank)
        cols = "id, name" + (", %s" % pcol if pcol else "")
        chains[rank] = {r[0]: (r[1], r[2] if pcol else None)
                        for r in db.execute("SELECT %s FROM %s" % (cols, rank))}
    return chains


def pick_lists(chains):
    out = []
    for rank in RANKS:
        lines = ["%s:" % rank.upper()]
        for rid in sorted(chains[rank]):
            name, pid = chains[rank][rid]
            lines.append("  [%d] %s (parent %s)" % (rid, name, pid))
        out.append("\n".join(lines))
    return "\n\n".join(out)


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


def classify_batch(groups, lists_text):
    user = lists_text + "\n\nCHURCHES:\n"
    for g in groups:
        c = g["rep"]
        user += ("- id=%s name=%r lat=%s lon=%s source=%r "
                 "existing=%s\n" % (
                     c["id"], c["name"], c["latitude"],
                     c["longitude"], c["source"],
                     {k: c[k] for k in COL.values() if c[k]}))
    headers = {"Authorization": "Bearer " + API_KEY,
               "Content-Type": "application/json"}
    if IS_OPENROUTER:
        headers["HTTP-Referer"] = "https://gridataset.com"
        headers["X-Title"] = "GRID cascade trial"
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps({
            "model": MODEL,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": user}],
            "temperature": 0,
            "max_tokens": 4000,   # reasoning models need headroom or content=null
            "response_format": {"type": "json_object"},
        }).encode(),
        headers=headers)
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                body = json.load(r)
            txt = body["choices"][0]["message"]["content"] or ""
            # tolerate markdown-fenced JSON from free-router models
            t = txt.strip()
            if t.startswith("```"):
                t = t.split("\n", 1)[1] if "\n" in t else t[3:]
                t = t.rsplit("```", 1)[0]
            return json.loads(t), body.get("usage")
        except urllib.error.HTTPError as e:  # noqa: BLE001
            last = e
            # free-tier 429s need a real cooldown, not a short retry
            time.sleep(60 * (attempt + 1) if e.code == 429 else 2 ** attempt)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** attempt)
    die("batch failed after retries: %r" % (last,))


def validate_results(results, batch, chains):
    """Coerce hallucinated ids to "unknown"; return (cleaned, violations)."""
    violations = 0
    by_id = {g["rep"]["id"]: g for g in batch}
    cleaned = []
    for r in results:
        cid = r.get("id")
        if cid not in by_id:
            violations += 1
            continue
        prev = None
        for rank in RANKS:
            pick = r.get(rank)
            if pick == "unknown" or pick is None:
                prev = None
                r[rank] = "unknown"
                continue
            try:
                pid = int(pick)
            except (TypeError, ValueError):
                pid = None
            ok = (pid in chains[rank] and
                  (rank == "culture" or chains[rank][pid][1] == prev))
            if not ok:
                violations += 1
                r[rank] = "unknown"
                prev = None
            else:
                r[rank] = pid
                prev = pid
        cleaned.append(r)
    return cleaned, violations


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--batch-groups", type=int, default=BATCH_GROUPS)
    ap.add_argument("--checkpoint",
                    default=r"E:\grid\outputs\cascade-trial-300-checkpoint.jsonl")
    args = ap.parse_args()
    if not API_KEY: die("set KILO_API_KEY")

    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    db.row_factory = sqlite3.Row
    chains = load_chains(db)
    lists_text = pick_lists(chains)

    half = args.n // 2
    cols = ("id, name, latitude, longitude, source, culture_id, faith_id,"
            " legacy_id, tradition_id, movement_id, taxonomy_id")
    unlabeled = [dict(r) for r in db.execute(
        "SELECT %s FROM churches WHERE taxonomy_id IS NULL "
        "ORDER BY RANDOM() LIMIT ?" % cols, (half,))]
    labeled = [dict(r) for r in db.execute(
        "SELECT %s FROM churches WHERE taxonomy_id IS NOT NULL "
        "ORDER BY RANDOM() LIMIT ?" % cols, (args.n - half,))]
    # stash existing values for the audit join before closing
    for r in labeled:
        r["_labeled"] = True
    for r in unlabeled:
        r["_labeled"] = False
    rows = unlabeled + labeled
    db.close()

    groups, seen = [], {}
    for r in rows:
        key = (r["name"] or "").strip().lower() or ("id:%s" % r["id"])
        if key not in seen:
            seen[key] = {"key": key, "rep": r, "ids": [],
                         "labeled": r["_labeled"]}
            groups.append(seen[key])
        seen[key]["ids"].append(r["id"])
    print("%d churches -> %d groups (%d labeled groups)" %
          (len(rows), len(groups), sum(1 for g in groups if g["labeled"])),
          flush=True)

    done = set()
    if os.path.exists(args.checkpoint):
        with open(args.checkpoint, encoding="utf-8") as f:
            for line in f:
                try: done.add(json.loads(line)["key"])
                except Exception: pass
    print("resuming: %d groups already done" % len(done), flush=True)

    out = open(args.checkpoint, "a", encoding="utf-8")
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    total_violations = 0
    try:
        nb = (len(groups) + args.batch_groups - 1) // args.batch_groups
        for i in range(0, len(groups), args.batch_groups):
            batch = [g for g in groups[i:i + args.batch_groups]
                     if g["key"] not in done]
            if not batch:
                continue
            t0 = time.time()
            res, usage = classify_batch(batch, lists_text)
            if usage:
                for k in total_usage:
                    total_usage[k] += usage.get(k, 0)
            results = res.get("results", res) if isinstance(res, dict) else res
            if len(results) != len(batch):
                die("batch size mismatch: %d results for %d groups"
                    % (len(results), len(batch)))
            results, violations = validate_results(results, batch, chains)
            total_violations += violations
            for g, r in zip(batch, results):
                r["key"] = g["key"]; r["group_ids"] = g["ids"]
                r["labeled"] = g["labeled"]
                r["existing"] = {k: g["rep"][k] for k in COL.values()}
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
                done.add(g["key"])
            elapsed = time.time() - t0
            if elapsed < CALL_INTERVAL:
                time.sleep(CALL_INTERVAL - elapsed)
            print("batch %d/%d done (%d groups), usage=%s" %
                  (i // args.batch_groups + 1, nb, len(done), total_usage),
                  flush=True)
    finally:
        out.close()

    # ---- audit join: agreement on the labeled half ----
    agree = {r: [0, 0] for r in RANKS}   # [agree, comparable]
    unknowns = {r: 0 for r in RANKS}
    gate_fail = 0
    novelties = []
    n_labeled = 0
    with open(args.checkpoint, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if not r.get("gate", True):
                gate_fail += 1
                continue
            for rank in RANKS:
                pick = r.get(rank)
                if pick == "unknown" or pick is None:
                    unknowns[rank] += 1
                    continue
                if r.get("labeled"):
                    exist = (r.get("existing") or {}).get(COL[rank])
                    if exist is not None:
                        agree[rank][1] += 1
                        try:
                            if int(pick) == int(exist):
                                agree[rank][0] += 1
                        except (TypeError, ValueError):
                            pass
            if r.get("labeled"):
                n_labeled += 1
            if r.get("novelty"):
                novelties.append((r["group_ids"][0], r["novelty"]))
    print("labeled groups classified:", n_labeled)
    print("gate=false:", gate_fail)
    for rank in RANKS:
        a, c = agree[rank]
        print("  %s: agreement %d/%d (%.1f%%), unknowns %d" %
              (rank, a, c, 100.0 * a / c if c else 0, unknowns[rank]))
    print("novelty proposals:", len(novelties))
    for cid, nov in novelties[:20]:
        print("  church", cid, str(nov)[:120])
    print("total usage:", total_usage)
    print("hallucinated ids coerced to unknown:", total_violations)


if __name__ == "__main__":
    main()
