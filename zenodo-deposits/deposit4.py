#!/usr/bin/env python3
"""Deposit 4 staged packages to Zenodo, publish, mint DOIs. Sequential with retries."""
import json, os, sys, time, urllib.request, urllib.error

BASE = "https://zenodo.org/api/deposit/depositions"
STATE_FILE = os.path.expanduser("~/workspace/zenodo-deposits/deposit-state.json")
PKG_ROOT = os.path.expanduser("~/workspace/zenodo-deposits")
PACKAGES = ["drehem-ledger-v1.0", "linearb-ledger-v1.0", "khipu-v1.0", "chicago-benchmark-v1.0"]

def load_token():
    with open(os.path.expanduser("~/.secrets/zenodo_api_token")) as f:
        return f.read().strip()

TOKEN = load_token()

def req(method, url, data=None, headers=None, timeout=120):
    h = {"Authorization": f"Bearer {TOKEN}"}
    if headers:
        h.update(headers)
    body = json.dumps(data).encode() if data is not None else None
    if data is not None and "Content-Type" not in h:
        h["Content-Type"] = "application/json"
    r = urllib.request.Request(url, data=body, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            detail = e.read().decode()[:500]
        except Exception:
            detail = ""
        return e.code, {"_http_error": detail}

def req_retry(method, url, data=None, headers=None, tries=6, timeout=120, label=""):
    for i in range(tries):
        try:
            status, out = req(method, url, data, headers, timeout)
            if status in (200, 201):
                return status, out
            if status >= 500 or status == 429:
                print(f"  [{label}] HTTP {status}, retry {i+1}/{tries}", flush=True)
                time.sleep(5 * (i + 1))
                continue
            print(f"  [{label}] HTTP {status} FAIL: {out}", flush=True)
            return status, out
        except Exception as e:
            print(f"  [{label}] connection error ({e}), retry {i+1}/{tries}", flush=True)
            time.sleep(5 * (i + 1))
    return None, {"_error": "retries exhausted"}

def put_file(bucket_url, path, filename, timeout=600):
    url = f"{bucket_url}/{filename}"
    with open(path, "rb") as f:
        payload = f.read()
    if not payload:
        print(f"    upload {filename}: refusing to upload empty file", flush=True)
        return False
    for i in range(8):
        try:
            r = urllib.request.Request(
                url, data=payload, method="PUT",
                headers={"Authorization": f"Bearer {TOKEN}",
                         "Content-Type": "application/octet-stream"})
            with urllib.request.urlopen(r, timeout=timeout) as resp:
                if resp.status in (200, 201):
                    return True
                print(f"    upload {filename}: HTTP {resp.status}, retry {i+1}/8", flush=True)
        except Exception as e:
            print(f"    upload {filename} try {i+1} failed: {e}", flush=True)
        time.sleep(5 * (i + 1))
    return False

def load_state():
    try:
        return json.load(open(STATE_FILE))
    except Exception:
        return {}

def save_state(s):
    json.dump(s, open(STATE_FILE, "w"), indent=1)

def main():
    state = load_state()
    for pkg in PACKAGES:
        if state.get(pkg, {}).get("doi"):
            print(f"== {pkg}: already published ({state[pkg]['doi']}), skipping", flush=True)
            continue
        pdir = os.path.join(PKG_ROOT, pkg)
        meta_full = json.load(open(os.path.join(pdir, "zenodo-deposit-metadata.json")))
        files = meta_full["files"]
        metadata = {k: v for k, v in meta_full["metadata"].items()}

        dep_id = state.get(pkg, {}).get("deposition_id")
        bucket = state.get(pkg, {}).get("bucket_url")
        if not dep_id:
            print(f"== {pkg}: creating deposition", flush=True)
            status, out = req_retry("POST", BASE, {}, label=f"{pkg} create")
            if status not in (200, 201):
                print(f"FAILED to create deposition for {pkg}", flush=True)
                continue
            dep_id, bucket = out["id"], out["links"]["bucket"]
            state[pkg] = {"deposition_id": dep_id, "bucket_url": bucket}
            save_state(state)
            print(f"  deposition {dep_id}", flush=True)
        else:
            print(f"== {pkg}: resuming deposition {dep_id}", flush=True)

        status, out = req_retry("GET", f"{BASE}/{dep_id}/files", label=f"{pkg} list files")
        have = {f["filename"] for f in out} if status == 200 else set()
        print(f"  already uploaded: {sorted(have) or 'none'}", flush=True)

        ok = True
        for fn in files:
            if fn in have:
                print(f"  SKIP (already uploaded): {fn}", flush=True)
                continue
            print(f"  uploading {fn} ...", flush=True)
            if put_file(bucket, os.path.join(pdir, fn), fn):
                print(f"  UPLOADED {fn}", flush=True)
            else:
                print(f"  FAILED upload {fn}", flush=True)
                ok = False
                break
        if not ok:
            continue

        print(f"  setting metadata", flush=True)
        status, out = req_retry("PUT", f"{BASE}/{dep_id}", {"metadata": metadata}, label=f"{pkg} metadata")
        if status not in (200, 201):
            print(f"FAILED metadata for {pkg}", flush=True)
            continue
        print(f"  METADATA SET", flush=True)

        print(f"  publishing", flush=True)
        status, out = req_retry("POST", f"{BASE}/{dep_id}/actions/publish", {}, label=f"{pkg} publish", tries=4)
        if status not in (200, 202):
            print(f"FAILED publish for {pkg}: {out}", flush=True)
            state[pkg]["publish_failed"] = out
            save_state(state)
            continue
        doi = out.get("doi")
        print(f"  PUBLISHED DOI: {doi}", flush=True)
        state[pkg]["doi"] = doi
        save_state(state)

        cit = os.path.join(pdir, "CITATION.txt")
        txt = open(cit).read()
        if "doi.org" not in txt:
            txt = txt.replace("(DOI to be appended.)", f"https://doi.org/{doi}")
            txt = txt.replace("[DOI to be appended once minted via Zenodo.]",
                              f"https://doi.org/{doi}")
            open(cit, "w").write(txt)
            print(f"  CITATION.txt updated", flush=True)

    print("DONE", flush=True)

main()
