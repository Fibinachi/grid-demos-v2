import os as _os
_os.environ['RESUME_JSON'] = '{"checked_at": "2026-10-11T08:53:00", "providers": {"kilo": {"models_seen": 11, "candidates": 11}, "openrouter": {"models_seen": 15, "candidates": 15}, "gemini": {"models_seen": 41, "candidates": 40}}, "working": [{"provider": "openrouter", "model": "nvidia/nemotron-3-super-120b-a12b:free", "toy": "pass", "full": "pass"}, {"provider": "openrouter", "model": "nvidia/nemotron-3-ultra-550b-a55b:free", "toy": "pass", "full": "pass"}, {"provider": "gemini", "model": "gemini-3.1-flash-lite", "toy": "pass", "full": "pass"}, {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview", "toy": "pass", "full": "pass"}, {"provider": "gemini", "model": "gemini-3.5-flash-lite", "toy": "pass", "full": "pass"}, {"provider": "gemini", "model": "gemini-flash-lite-latest", "toy": "pass", "full": "pass"}, {"provider": "gemini", "model": "gemini-robotics-er-2-preview", "toy": "pass", "full": "pass"}], "broken": [{"provider": "kilo", "model": "cohere/north-mini-code:free", "toy": "pass", "full": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "kilo", "model": "dots-studio/dots-3-note-preview:free", "toy": "pass", "full": "fail", "note": "Expecting \',\' delimiter: line 1 column 256 (char 255)"}, {"provider": "kilo", "model": "liquid/lfm-2.5-2.6b:free", "toy": "pass", "full": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "kilo", "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reason", "toy": "fail", "note": "\'choices\'"}, {"provider": "kilo", "model": "nvidia/nemotron-3-super-120b-a12b:free", "toy": "pass", "full": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "kilo", "model": "nvidia/nemotron-3-ultra-550b-a55b:free", "toy": "fail", "note": "Expecting \',\' delimiter: line 1 column 21 (char 20)"}, {"provider": "kilo", "model": "nvidia/nemotron-3.5-content-safety:free", "toy": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "kilo", "model": "nvidia/nemotron-3.5-lightning:free", "toy": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "openrouter", "model": "apodex/apodex-1.1-mini:free", "toy": "pass", "full": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "openrouter", "model": "cohere/north-mini-code:free", "toy": "pass", "full": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "openrouter", "model": "dots-studio/dots-3-note-preview:free", "toy": "pass", "full": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "openrouter", "model": "liquid/lfm-2.5-2.6b:free", "toy": "pass", "full": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "openrouter", "model": "nvidia/nemotron-3-nano-omni-30b-a3b-reason", "toy": "fail", "note": "\'choices\'"}, {"provider": "openrouter", "model": "nvidia/nemotron-3.5-content-safety:free", "toy": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "openrouter", "model": "nvidia/nemotron-3.5-lightning:free", "toy": "pass", "full": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "openrouter", "model": "thinkingmachines/inkling-small:free", "toy": "fail", "note": "HTTP 403"}, {"provider": "openrouter", "model": "thinkingmachines/inkling:free", "toy": "fail", "note": "HTTP 403"}, {"provider": "gemini", "model": "antigravity-preview-05-2026", "toy": "fail", "note": "HTTP 400"}, {"provider": "gemini", "model": "antigravity-preview-09-2026", "toy": "fail", "note": "HTTP 400"}, {"provider": "gemini", "model": "antigravity-preview-latest", "toy": "fail", "note": "HTTP 400"}, {"provider": "gemini", "model": "aqa", "toy": "fail", "note": "HTTP 404"}, {"provider": "gemini", "model": "gemini-2.5-flash", "toy": "fail", "note": "HTTP 404"}, {"provider": "gemini", "model": "gemini-2.5-flash-lite", "toy": "fail", "note": "HTTP 404"}, {"provider": "gemini", "model": "gemini-2.5-pro", "toy": "fail", "note": "HTTP 404"}, {"provider": "gemini", "model": "gemini-3-flash-preview", "toy": "pass", "full": "fail", "note": "Expecting value: line 19 column 19 (char 331)"}, {"provider": "gemini", "model": "gemini-3.5-flash", "toy": "pass", "full": "fail", "note": "HTTP 503"}, {"provider": "gemini", "model": "gemini-3.5-transcribe", "toy": "fail", "note": "HTTP 400"}, {"provider": "gemini", "model": "gemini-3.6-flash", "toy": "pass", "full": "fail", "note": "HTTP 503"}, {"provider": "gemini", "model": "gemini-3.7-flash", "toy": "fail", "note": "HTTP 503"}, {"provider": "gemini", "model": "gemini-3.8-flash", "toy": "fail", "note": "HTTP 503"}, {"provider": "gemini", "model": "gemini-flash-latest", "toy": "fail", "note": "HTTP 503"}, {"provider": "gemini", "model": "gemma-4-26b-a4b-it", "toy": "fail", "note": "Expecting value: line 1 column 1 (char 0)"}, {"provider": "gemini", "model": "gemma-4-31b-it", "toy": "fail", "note": "HTTP 500"}], "rate_limited": [{"provider": "kilo", "model": "poolside/laguna-s-2.1:free", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "kilo", "model": "poolside/laguna-xs-2.1:free", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "kilo", "model": "thinkingmachines/inkling-small:free", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "openrouter", "model": "google/gemma-4-26b-a4b-it:free", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "openrouter", "model": "google/gemma-4-31b-it:free", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "openrouter", "model": "poolside/laguna-s-2.1:free", "toy": "pass", "full": "rate_limited", "note": "HTTP 429"}, {"provider": "openrouter", "model": "poolside/laguna-xs-2.1:free", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "deep-research-max-preview-04-2026", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "deep-research-preview-04-2026", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "deep-research-pro-preview-12-2025", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-2.5-computer-use-preview-10-2025", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-2.5-flash-image", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-3-pro-image", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-3-pro-image-preview", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-3.1-flash-image", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-3.1-flash-image-preview", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-3.1-flash-lite-image", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-3.1-pro-preview", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-3.1-pro-preview-customtools", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-nano-banana-2.1", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-omni-1.1-flash", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-omni-flash-preview", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "gemini-pro-latest", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "lyria-3-clip-preview", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "lyria-3-pro-preview", "toy": "rate_limited", "note": "HTTP 429"}, {"provider": "gemini", "model": "lyria-3.5", "toy": "rate_limited", "note": "HTTP 429"}], "no_key": []}'
_os.environ['SKIP_PROVIDERS'] = 'kilo,openrouter,gemini'
"""
Free-model usability probe — all providers (runs on garage).

For each configured provider, lists candidate free models and runs a
two-stage usability test:
  Stage 1 (toy): tiny structured-output prompt. Must return 200 +
      non-empty, parseable JSON.
  Stage 2 (full): real cascade prompt — full CFLTM pick lists from the DB
      (~600 options) + 3 churches. Must return 200 + parseable JSON with
      one result per church and zero hallucinated ids (unknowns allowed).

Writes the master list to E:\\grid\\outputs\\free-models-working.json and
prints it between MASTER_JSON_BEGIN / MASTER_JSON_END (the cron worker
saves a local copy too).

Providers without a key on garage are recorded under "no_key" so Charles
knows what to promote to machine scope.

Run:  E:\\grid\\.venv\\Scripts\\python.exe - < free-model-probe.py
"""

import io, json, os, sqlite3, sys, time, urllib.request, urllib.error

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DB = r"E:\grid\churches.db"

# kind: "openai" = OpenAI-compatible chat/completions + models endpoints.
#       "cohere" = Cohere native /v1/chat.
PROVIDERS = {
    "kilo":       {"kind": "openai",
                   "models": "https://api.kilo.ai/api/gateway/models",
                   "chat": "https://api.kilo.ai/api/gateway/chat/completions",
                   "key_env": "KILO_API_KEY", "headers": {},
                   "free": lambda i: i.endswith(":free")},
    "openrouter": {"kind": "openai",
                   "models": "https://openrouter.ai/api/v1/models",
                   "chat": "https://openrouter.ai/api/v1/chat/completions",
                   "key_env": "OPENROUTER_API_KEY",
                   "headers": {"HTTP-Referer": "https://gridataset.com",
                               "X-Title": "GRID free-model probe"},
                   "free": lambda i: i.endswith(":free")},
    "gemini":     {"kind": "openai",
                   "models": "https://generativelanguage.googleapis.com/v1beta/models",
                   "chat": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                   "key_env": "GEMINI_API_KEY", "headers": {},
                   "key_header": "x-goog-api-key",
                   "name_prefix": "models/",
                   "free": lambda i: ("embed" not in i and "imagen" not in i
                                      and "veo" not in i and "tts" not in i)},
    "groq":       {"kind": "openai",
                   "models": "https://api.groq.com/openai/v1/models",
                   "chat": "https://api.groq.com/openai/v1/chat/completions",
                   "key_env": "GROQ_API_KEY", "headers": {},
                   "free": lambda i: True},
    "cerebras":   {"kind": "openai",
                   "models": "https://api.cerebras.ai/v1/models",
                   "chat": "https://api.cerebras.ai/v1/chat/completions",
                   "key_env": "CEREBRAS_API_KEY", "headers": {},
                   "free": lambda i: True},
    "mistral":    {"kind": "openai",
                   "models": "https://api.mistral.ai/v1/models",
                   "chat": "https://api.mistral.ai/v1/chat/completions",
                   "key_env": "MISTRAL_API_KEY", "headers": {},
                   "free": lambda i: True},
    "aimlapi":    {"kind": "openai",
                   "models": "https://api.aimlapi.com/v1/models",
                   "chat": "https://api.aimlapi.com/v1/chat/completions",
                   "key_env": "AIMLAPI_API_KEY", "headers": {},
                   "free": lambda i: True},
    "fireworks":  {"kind": "openai",
                   "models": "https://api.fireworks.ai/inference/v1/models",
                   "chat": "https://api.fireworks.ai/inference/v1/chat/completions",
                   "key_env": "FIREWORKS_API_KEY", "headers": {},
                   "free": lambda i: True},
    "cohere":     {"kind": "cohere",
                   "models": "https://api.cohere.ai/v1/models",
                   "chat": "https://api.cohere.ai/v1/chat",
                   "key_env": "COHERE_API_KEY", "headers": {},
                   "free": lambda i: True},
}

MAX_TOY_PER_PROVIDER = 40
MAX_FULL_PER_PROVIDER = 10
PAUSE = 4  # seconds between calls; free tiers are rate-limited

RANKS = ["culture", "faith", "legacy", "tradition", "movement"]
PCOL = {"faith": "culture_id", "legacy": "faith_id",
        "tradition": "legacy_id", "movement": "tradition_id"}

TOY_SYS = "Return ONLY JSON, no prose."
TOY_USER = 'Return {"ok": true}.'

FULL_SYS = (
    "You are a classifier for a database of religious sites. Given pick "
    "lists with legal ids per rank (culture -> faith -> legacy -> tradition "
    "-> movement), each with parent: gate first (religious site?), then pick "
    "exactly one id per rank constrained to CHILDREN of previous pick; "
    "'unknown' legal at any pass and stops descent; every emitted id MUST "
    "appear verbatim in the lists, never invent one. Return exactly "
    "{\"results\": [{\"id\": <church id>, \"gate\": true|false, "
    "\"culture\": <id|\"unknown\">, \"faith\": ..., \"legacy\": ..., "
    "\"tradition\": ..., \"movement\": ..., \"novelty\": null}]} - one entry "
    "per church in listed order, no prose, no fences.")


def _get(url, key, key_header=None):
    headers = {}
    if key_header:
        headers[key_header] = key
    else:
        headers["Authorization"] = "Bearer " + key
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def list_models(pname, p):
    key = (os.environ.get(p["key_env"]) or "").strip()
    if not key:
        return None, []
    body = _get(p["models"], key, p.get("key_header"))
    items = body.get("data") or body.get("models") or []
    ids = []
    for m in items:
        i = m.get("id") or m.get("name") or ""
        if p.get("name_prefix") and i.startswith(p["name_prefix"]):
            i = i[len(p["name_prefix"]):]
        if i and p["free"](i):
            ids.append(i)
    return key, sorted(set(ids))


def chat_openai(p, key, model, messages, max_tokens):
    headers = {"Authorization": "Bearer " + key,
               "Content-Type": "application/json"}
    headers.update(p["headers"])
    req = urllib.request.Request(
        p["chat"],
        data=json.dumps({"model": model, "messages": messages,
                         "temperature": 0, "max_tokens": max_tokens,
                         "response_format": {"type": "json_object"}}).encode(),
        headers=headers)
    with urllib.request.urlopen(req, timeout=240) as r:
        body = json.load(r)
    return (body["choices"][0]["message"].get("content") or "").strip()


def chat_cohere(p, key, model, prompt, max_tokens):
    req = urllib.request.Request(
        p["chat"],
        data=json.dumps({"model": model, "message": prompt,
                         "temperature": 0,
                         "max_tokens": max_tokens}).encode(),
        headers={"Authorization": "Bearer " + key,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=240) as r:
        body = json.load(r)
    t = (body.get("text") or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        t = t.rsplit("```", 1)[0]
    return t.strip()


def classify_err(e):
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 429:
            return "rate_limited", "HTTP 429"
        return "fail", "HTTP %s" % e.code
    return "fail", str(e)[:80]


def toy_probe(pname, p, key, model):
    try:
        if p["kind"] == "cohere":
            t = chat_cohere(p, key, model,
                            TOY_SYS + " " + TOY_USER, 300)
        else:
            t = chat_openai(p, key, model,
                            [{"role": "system", "content": TOY_SYS},
                             {"role": "user", "content": TOY_USER}], 300)
        json.loads(t)
        return "pass", ""
    except Exception as e:
        return classify_err(e)


def full_probe(pname, p, key, model, chains, user):
    try:
        if p["kind"] == "cohere":
            t = chat_cohere(p, key, model, FULL_SYS + "\n\n" + user, 4000)
        else:
            t = chat_openai(p, key, model,
                            [{"role": "system", "content": FULL_SYS},
                             {"role": "user", "content": user}], 4000)
        d = json.loads(t)
        res = d.get("results", d) if isinstance(d, dict) else d
        if isinstance(res, dict):
            res = [res]
        if len(res) != 3:
            return "fail", "results=%d, want 3" % len(res)
        bad = sum(1 for e in res for rank in RANKS
                  for v in [e.get(rank)]
                  if v != "unknown" and v is not None
                  and int(v) not in chains[rank])
        if bad:
            return "fail", "%d hallucinated ids" % bad
        return "pass", ""
    except Exception as e:
        return classify_err(e)


def load_pick_lists():
    db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    db.row_factory = sqlite3.Row
    chains = {}
    for rank in RANKS:
        pcol = PCOL.get(rank)
        cols = "id, name" + (", %s" % pcol if pcol else "")
        chains[rank] = {r[0]: (r[1], r[2] if pcol else None)
                        for r in db.execute("SELECT %s FROM %s" % (cols, rank))}
    lists = []
    for rank in RANKS:
        lines = ["%s:" % rank.upper()]
        for rid in sorted(chains[rank]):
            name, pid = chains[rank][rid]
            lines.append("  [%d] %s (parent %s)" % (rid, name, pid))
        lists.append("\n".join(lines))
    rows = [dict(r) for r in db.execute(
        "SELECT id,name,latitude,longitude,source FROM churches "
        "WHERE taxonomy_id IS NULL ORDER BY RANDOM() LIMIT 3")]
    db.close()
    user = "\n\n".join(lists) + "\n\nCHURCHES:\n"
    for c in rows:
        user += ("- id=%s name=%r lat=%s lon=%s source=%r\n"
                 % (c["id"], c["name"], c["latitude"],
                    c["longitude"], c["source"]))
    return chains, user


def main():
    master = {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
              "providers": {}, "working": [], "broken": [],
              "rate_limited": [], "no_key": []}
    chains, full_user = load_pick_lists()
    resume = os.environ.get("RESUME_JSON")
    skip = set(os.environ.get("SKIP_PROVIDERS", "").split(",")) - {""}
    if resume:
        master.update(json.loads(resume))
    for pname, p in PROVIDERS.items():
        if pname in skip:
            continue
        try:
            key, models = list_models(pname, p)
        except Exception as e:
            master["providers"][pname] = {
                "error": "%s: %s" % (type(e).__name__, e)}
            print("skip %s: provider error %s" % (pname, e), flush=True)
            continue
        if key is None:
            master["no_key"].append(pname)
            print("skip %s: no key on garage" % pname, flush=True)
            continue
        cands = models[:MAX_TOY_PER_PROVIDER]
        master["providers"][pname] = {"models_seen": len(models),
                                      "candidates": len(cands)}
        print("%s: %d models, probing %d" % (pname, len(models), len(cands)),
              flush=True)
        full_done = 0
        for m in cands:
            toy, note = toy_probe(pname, p, key, m)
            entry = {"provider": pname, "model": m, "toy": toy}
            if toy == "pass" and full_done < MAX_FULL_PER_PROVIDER:
                full, fnote = full_probe(pname, p, key, m, chains, full_user)
                full_done += 1
                entry["full"] = full
                entry["note"] = fnote
                bucket = ("working" if full == "pass"
                          else "rate_limited" if full == "rate_limited"
                          else "broken")
            elif toy == "pass":
                entry["full"] = "skipped"
                entry["note"] = "full-probe cap reached"
                bucket = "broken"
            elif toy == "rate_limited":
                entry["note"] = note
                bucket = "rate_limited"
            else:
                entry["note"] = note
                bucket = "broken"
            master[bucket].append(entry)
            print("  %-10s %-42s toy=%s full=%s %s"
                  % (pname, m[:42], toy, entry.get("full", "-"),
                     entry.get("note", "")), flush=True)
            time.sleep(PAUSE)
    out = r"E:\grid\outputs\free-models-working.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(master, f, indent=1)
    print("wrote", out)
    print("MASTER_JSON_BEGIN")
    print(json.dumps(master))
    print("MASTER_JSON_END")


if __name__ == "__main__":
    main()
