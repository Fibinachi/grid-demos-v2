#!/usr/bin/env python3
"""Parallel 1926 record puller: takes --ids file and --out, polite 1.5s delay, keep-alive."""
import argparse, json, os, sys, time
import requests
sys.path.insert(0, "/home/hatch/workspace/grid/chicago-benchmark")
from importlib.machinery import SourceFileLoader
mod = SourceFileLoader("scraper", "/home/hatch/workspace/grid/chicago-benchmark/1926-cook-scraper.py").load_module()

ap = argparse.ArgumentParser()
ap.add_argument("--ids", required=True)
ap.add_argument("--out", required=True)
args = ap.parse_args()

want = [l.strip() for l in open(args.ids) if l.strip()]
done = set()
if os.path.exists(args.out):
    with open(args.out) as f:
        for line in f:
            try:
                done.add(str(json.loads(line)["record_id"]))
            except Exception:
                pass
todo = [i for i in want if i not in done]
print(f"worker: {len(todo)} to pull", flush=True)
os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
with open(args.out, "a") as f:
    for n, rid in enumerate(todo, 1):
        try:
            f.write(json.dumps(mod.parse_record(rid, mod.fetch(f"{mod.BASE}/census/record/{rid}/"))) + "\n")
            f.flush()
        except Exception as e:
            print(f"FAILED {rid}: {e}", file=sys.stderr, flush=True)
        if n % 100 == 0:
            print(f"{n}/{len(todo)}", flush=True)
        time.sleep(mod.DELAY)
print("worker done", flush=True)
