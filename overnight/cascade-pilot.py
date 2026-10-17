"""
Kilo cascade classifier — PILOT (draft, 2026-10-07/08).

Runs Charles's multi-pass cascade (gate -> culture -> faith -> legacy ->
tradition -> movement, fused into one batched call per group batch) over
1,000 pilot churches. READ-ONLY against the production DB: results go to
a JSONL checkpoint file; nothing is written to churches.db.

Run on the desktop (holds the Kilo key in env):
    set KILO_API_KEY=...
    set KILO_BASE_URL=https://<kilo openai-compatible endpoint>
    set KILO_MODEL=<model id>
    E:\grid\.venv\Scripts\python.exe cascade-pilot.py --n 1000

Throttle: 55 calls/min (headroom under the 60/min free-tier limit).
"""

import argparse, json, os, sqlite3, sys, time, urllib.request

DB = r"E:\grid\churches.db"
API_KEY = os.environ.get("KILO_API_KEY")
BASE_URL = os.environ.get("KILO_BASE_URL")   # e.g. Kilo's OpenAI-compatible endpoint
MODEL = os.environ.get("KILO_MODEL")         # e.g. a free-tier model id
CALL_INTERVAL = 60.0 / 55                    # 55 calls/min
BATCH_GROUPS = 10

RANKS = ["culture", "faith", "legacy", "tradition", "movement"]
PARENT = {"faith": "culture_id", "legacy": "faith_id",
          "tradition": "legacy_id", "movement": "tradition_id"}


def die(msg):
    print("FATAL:", msg, file=sys.stderr); sys.exit(1)


def load_chains(db):
    """Return {rank: {id: (name, parent_id)}} for pick-list construction."""
    chains = {}
    for rank in RANKS:
        pcol = {"culture": None, "faith": "culture_id", "legacy": "faith_id",
                "tradition": "legacy_id", "movement": "tradition_id"}[rank]
        cols = "id, name" + (", %s" % pcol if pcol else "")
        chains[rank] = {r[0]: (r[1], r[2] if pcol else None)
                        for r in db.execute("SELECT %s FROM %s" % (cols, rank))}
    return chains


def pick_lists(chains):
    """Render the full rank chains as compact text for the prompt."""
    out = []
    for rank in RANKS:
        lines = ["%s:" % rank.upper()]
        for rid in sorted(chains[rank]):
            name, pid = chains[rank][rid]
            lines.append("  [%d] %s (parent %s)" % (rid, name, pid))
        out.append("\n".join(lines))
    return "\n\n".join(out)


SYSTEM = """You are a classifier for a database of religious sites. For each
church below, walk the cascade and return one JSON object per church.
Rules:
- Gate first: is this a religious site? If no, set "gate": false and stop.
- Then pick exactly one id per rank, each constrained to the CHILDREN of
  the previous pick (culture -> faith -> legacy -> tradition -> movement).
- At ANY pass you may answer "unknown" instead of forcing a pick. Unknown
  stops the descent; deeper ranks stay null. An honest unknown beats a
  wrong guess.
- If "unknown" at tradition/movement but you believe a REAL formation is
  present that the lists lack, set "novelty" with suggested_parent (a
  taxonomy id from the lists) and a one-line rationale.
- Confidence 0..1 per level. Use the location and source as signals:
  a denominational directory source is a strong prior.
Return ONLY a JSON array, no prose."""


def classify_batch(groups, lists_text):
    user = lists_text + "\n\nCHURCHES:\n"
    for g in groups:
        c = g["rep"]
        user += ("- id=%s name=%r orig=%r lat=%s lon=%s source=%r "
                 "existing=%s\n" % (
                     c["id"], c["name"], c["name_original"], c["latitude"],
                     c["longitude"], c["source"],
                     {k: c[k] for k in
                      ("culture_id", "faith_id", "legacy_id",
                       "tradition_id", "movement_id") if c[k]}))
    req = urllib.request.Request(
        BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps({
            "model": MODEL,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": user}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }).encode(),
        headers={"Authorization": "Bearer " + API_KEY,
                 "Content-Type": "application/json"})
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                body = json.load(r)
            txt = body["choices"][0]["message"]["content"]
            return json.loads(txt)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 ** attempt)
    die("batch failed after retries: %r" % (last,))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--batch-groups", type=int, default=BATCH_GROUPS)
    ap.add_argument("--checkpoint", default="cascade-pilot-checkpoint.jsonl")
    args = ap.parse_args()
    if not API_KEY: die("set KILO_API_KEY")
    if not BASE_URL: die("set KILO_BASE_URL (Kilo OpenAI-compatible endpoint)")
    if not MODEL: die("set KILO_MODEL")

    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    db.row_factory = sqlite3.Row
    chains = load_chains(db)
    lists_text = pick_lists(chains)

    half = args.n // 2
    rows = [dict(r) for r in db.execute(
        """SELECT id, name, name_original, normalized_name, latitude,
                  longitude, source, culture_id, faith_id, legacy_id,
                  tradition_id, movement_id, taxonomy_id
           FROM churches WHERE taxonomy_id IS NULL
           ORDER BY RANDOM() LIMIT ?""", (half,))]
    rows += [dict(r) for r in db.execute(
        """SELECT id, name, name_original, normalized_name, latitude,
                  longitude, source, culture_id, faith_id, legacy_id,
                  tradition_id, movement_id, taxonomy_id
           FROM churches WHERE taxonomy_id IS NOT NULL
           ORDER BY RANDOM() LIMIT ?""", (args.n - half,))]
    db.close()

    # Group by normalized_name; representative = first row.
    groups, seen = [], {}
    for r in rows:
        key = r["normalized_name"] or ("id:%s" % r["id"])
        if key not in seen:
            seen[key] = {"key": key, "rep": r, "ids": []}
            groups.append(seen[key])
        seen[key]["ids"].append(r["id"])
    print("%d churches -> %d groups" % (len(rows), len(groups)))

    done = set()
    if os.path.exists(args.checkpoint):
        with open(args.checkpoint, encoding="utf-8") as f:
            for line in f:
                try: done.add(json.loads(line)["key"])
                except Exception: pass
    print("resuming: %d groups already done" % len(done))

    out = open(args.checkpoint, "a", encoding="utf-8")
    try:
        for i in range(0, len(groups), args.batch_groups):
            batch = [g for g in groups[i:i + args.batch_groups]
                     if g["key"] not in done]
            if not batch:
                continue
            t0 = time.time()
            res = classify_batch(batch, lists_text)
            # res: {"results": [ {church_id, gate, culture, ..., confidences, novelty}, ... ]}
            results = res.get("results", res) if isinstance(res, dict) else res
            for g, r in zip(batch, results):
                r["key"] = g["key"]; r["group_ids"] = g["ids"]
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
                done.add(g["key"])
            elapsed = time.time() - t0
            if elapsed < CALL_INTERVAL:
                time.sleep(CALL_INTERVAL - elapsed)
            print("batch %d/%d done (%d groups)" %
                  (i // args.batch_groups + 1,
                   (len(groups) + args.batch_groups - 1) // args.batch_groups,
                   len(done)))
    finally:
        out.close()

    # Audit-mode summary: agreement on the labeled half, novelty proposals.
    agree = {r: [0, 0] for r in RANKS}
    novelties = []
    with open(args.checkpoint, encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            rep_id = r["group_ids"][0]
            # (full audit join omitted in pilot draft; counts unknowns)
            for rank in RANKS:
                if r.get(rank) == "unknown":
                    agree[rank][1] += 1
            if r.get("novelty"):
                novelties.append((rep_id, r["novelty"]))
    print("unknown counts per rank:", {k: v[1] for k, v in agree.items()})
    print("novelty proposals:", len(novelties))
    for cid, nov in novelties[:20]:
        print("  church", cid, nov)


if __name__ == "__main__":
    main()
