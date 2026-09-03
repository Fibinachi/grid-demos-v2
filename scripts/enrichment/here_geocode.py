#!/usr/bin/env python3
"""
HERE.com Enrichment Pipeline — 30K/month Budget
===================================================
Uses HERE Geocoding & Search API v7 (30,000 req/month) to:

  --missing    Geocode 10,634 churches missing lat/lng entirely
  --upgrade    Re-geocode ZIP-centroid → street-level (high-value only)
  --places     Look up website/phone via HERE Places API

Budget allocation (30K total):
  ~10K  Phase 1: Missing lat/lng (fills the gap — highest priority)
  ~10K  Phase 2: Upgrade ZIP-centroid with street address (quality improvement)
  ~10K  Phase 3: Places lookup for websites/phones (contact enrichment)

Usage:
    # Phase 1: Geocode missing lat/lng
    python scripts/enrichment/here_geocode.py --missing

    # Phase 2: Upgrade high-value ZIP-centroid churches
    python scripts/enrichment/here_geocode.py --upgrade --limit 10000

    # Phase 3: Places lookup for contact info
    python scripts/enrichment/here_geocode.py --places --limit 5000

    # Dry-run any phase
    python scripts/enrichment/here_geocode.py --missing --dry-run --limit 100
    python scripts/enrichment/here_geocode.py --upgrade --dry-run --limit 100

Requires: HERE API key in data/here_api_key.json or env HERE_API_KEY
"""
import json, os, sys, time, sqlite3, urllib.request, urllib.parse
from datetime import datetime, date

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')
KEY_FILE = os.path.join(PROJECT_DIR, 'data', 'here_api_key.json')
QUOTA_FILE = os.path.join(PROJECT_DIR, 'data', 'here_quota.json')
CP_DIR = os.path.join(PROJECT_DIR, 'data')

HERE_GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"
HERE_DISCOVER_URL = "https://discover.search.hereapi.com/v1/discover"

MAX_MONTHLY = 30000
RATE_LIMIT = 0.15
BATCH_SIZE = 500

stats = {'called': 0, 'matched': 0, 'errors': 0, 'skipped': 0,
         'street': 0, 'website_found': 0, 'phone_found': 0}


def load_api_key():
    key = os.environ.get('HERE_API_KEY', '')
    if key:
        return key
    if os.path.exists(KEY_FILE):
        with open(KEY_FILE) as f:
            return json.load(f).get('here_api_key', '')
    return None


def this_month():
    """Return YYYY-MM string for current month."""
    return date.today().isoformat()[:7]


def load_quota():
    """Return calls used this month."""
    if not os.path.exists(QUOTA_FILE):
        return 0
    try:
        with open(QUOTA_FILE) as f:
            data = json.load(f)
        if data.get('month') == this_month():
            return data.get('used', 0)
    except Exception:
        pass
    return 0


def save_quota(used):
    os.makedirs(os.path.dirname(QUOTA_FILE), exist_ok=True)
    with open(QUOTA_FILE, 'w') as f:
        json.dump({'month': this_month(), 'used': used, 'max': MAX_MONTHLY}, f)


def quota_ok(needed=1):
    used = load_quota()
    remaining = MAX_MONTHLY - used
    if remaining < needed:
        print(f"\nMONTHLY QUOTA EXCEEDED: used {used}/{MAX_MONTHLY}")
        print(f"Resets {this_month()}-01 next month.")
        return 0
    return remaining


def track_calls(n=1):
    save_quota(load_quota() + n)


def cp_path(phase):
    return os.path.join(CP_DIR, f'here_{phase}_cp.json')


def load_cp(phase):
    p = cp_path(phase)
    if not os.path.exists(p):
        return set()
    try:
        with open(p) as f:
            return set(json.load(f).get('ids', []))
    except Exception:
        return set()


def save_cp(phase, ids):
    with open(cp_path(phase), 'w') as f:
        json.dump({'ids': list(ids), 'updated': datetime.now().isoformat()}, f)


# ─── API CALLS ───

def geocode(name, address, city, state, zipcode):
    """Forward-geocode via HERE. Returns (lat, lng, quality) or None."""
    q = f"{address}, {city}, {state} {zipcode or ''}".strip() if address and len(address) > 5 \
        else f"{name}, {city}, {state}".strip()
    if not q:
        return None
    params = urllib.parse.urlencode({'q': q, 'apiKey': HERE_API_KEY, 'limit': '1', 'lang': 'en-US'})
    url = f"{HERE_GEOCODE_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GrantWizard/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        items = data.get('items', [])
        if not items:
            return None
        item = items[0]
        pos = item.get('position', {})
        lat, lng = pos.get('lat'), pos.get('lng')
        if lat is None or lng is None:
            return None
        rt = item.get('resultType', '')
        quality = 'street' if rt in ('houseNumber', 'street', 'place') else \
                  'city' if rt == 'locality' else 'postal'
        return (lat, lng, quality)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("\nERROR: Invalid HERE API key!"); sys.exit(1)
        return None
    except Exception:
        return None


def discover(name, city, state):
    """Search HERE Places for website/phone. Returns dict."""
    q = f"{name} church {city} {state}".strip()
    params = urllib.parse.urlencode({'q': q, 'apiKey': HERE_API_KEY, 'limit': '3',
                                      'lang': 'en-US', 'categories': '100-1000-0000'})
    url = f"{HERE_DISCOVER_URL}?{params}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'GrantWizard/1.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        result = {'website': None, 'phone': None}
        for item in data.get('items', []):
            ws = item.get('website', '') or ''
            if ws and not result['website']:
                result['website'] = ws if ws.startswith('http') else f"https://{ws}"
            for c in item.get('contacts', []) if isinstance(item.get('contacts'), list) else []:
                if not isinstance(c, dict):
                    continue
                for w in c.get('www', []):
                    v = w.get('value', '') if isinstance(w, dict) else ''
                    if v and not result['website']:
                        result['website'] = v if v.startswith('http') else f"https://{v}"
                for p in c.get('phone', []):
                    v = p.get('value', '') if isinstance(p, dict) else ''
                    if v and not result['phone']:
                        result['phone'] = v
            if result['website'] and result['phone']:
                break
        return result
    except Exception:
        return {'website': None, 'phone': None}


# ─── DB ───

def ensure_cols(db):
    existing = {r[1] for r in db.execute("PRAGMA table_info(churches)")}
    for c, t in [('here_geocode_quality', 'TEXT'), ('here_last_geocoded', 'TEXT')]:
        if c not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {c} {t}")


def get_missing(db, limit=0):
    q = """SELECT id, name, address, city, state, zip FROM churches
           WHERE (latitude IS NULL OR latitude=0) AND city!='' AND state!='' ORDER BY id"""
    if limit:
        q += f" LIMIT {limit}"
    return db.execute(q).fetchall()


def get_zip_upgrades(db, limit=0):
    q = """SELECT id, name, address, city, state, zip FROM churches
           WHERE geocode_source='zip_centroid' AND address!='' AND LENGTH(address)>5
           ORDER BY CASE WHEN denomination!='' THEN 0 ELSE 1 END, id"""
    if limit:
        q += f" LIMIT {limit}"
    return db.execute(q).fetchall()


def get_places_candidates(db, limit=0):
    q = """SELECT id, name, city, state FROM churches
           WHERE (phone='' OR phone IS NULL OR email='' OR email IS NULL)
             AND city!='' AND state!=''
           ORDER BY CASE WHEN phone='' THEN 0 ELSE 1 END, id"""
    if limit:
        q += f" LIMIT {limit}"
    return db.execute(q).fetchall()


# ─── RUNNERS ───

def run_missing(db, limit, dry_run, resume):
    print("\nPHASE 1: Geocode Missing lat/lng")
    print("=" * 60)
    rows = get_missing(db, limit)
    print(f"Churches needing coords: {len(rows):,}")
    done = load_cp('missing') if resume else set()
    todo = [r for r in rows if r[0] not in done]
    remaining = quota_ok(len(todo))
    todo = todo[:remaining]
    print(f"To process: {len(todo):,}")
    if dry_run:
        for r in todo[:10]:
            print(f"  {r[0]:>8d} | {r[1][:40]:40s} | {r[4]:20s} {r[5]}")
        if len(todo) > 10:
            print(f"  ... {len(todo)-10:,} more")
        return
    updates = []
    for i, r in enumerate(todo):
        res = geocode(*r[1:])
        track_calls()
        stats['called'] += 1
        if res:
            lat, lng, quality = res
            updates.append((r[0], lat, lng, quality))
            stats['matched'] += 1
            if quality == 'street':
                stats['street'] += 1
        else:
            stats['errors'] += 1
        time.sleep(RATE_LIMIT)
        if len(updates) >= BATCH_SIZE:
            _flush_geo(db, updates)
        if (i + 1) % 2000 == 0:
            _prog(i+1, len(todo), 'missing')
    if updates:
        _flush_geo(db, updates)
    save_cp('missing', done | {r[0] for r in todo})
    _log(db, 'here_geocode_missing', stats['matched'], stats['called'])


def run_upgrade(db, limit, dry_run, resume):
    print("\nPHASE 2: Upgrade ZIP-Centroid to Street-Level")
    print("=" * 60)
    rows = get_zip_upgrades(db, limit)
    print(f"ZIP-centroid with street addresses: {len(rows):,}")
    done = load_cp('upgrade') if resume else set()
    todo = [r for r in rows if r[0] not in done]
    remaining = quota_ok(len(todo))
    todo = todo[:remaining]
    print(f"To process: {len(todo):,}")
    if dry_run:
        for r in todo[:10]:
            print(f"  {r[0]:>8d} | {r[1][:40]:40s} | {r[3][:30]:30s}")
        if len(todo) > 10:
            print(f"  ... {len(todo)-10:,} more")
        return
    updates = []
    for i, r in enumerate(todo):
        res = geocode(*r[1:])
        track_calls()
        stats['called'] += 1
        if res and res[2] == 'street':
            lat, lng = res[0], res[1]
            updates.append((r[0], lat, lng))
            stats['matched'] += 1
            stats['street'] += 1
        else:
            stats['skipped'] += 1  # not street-level, keep old ZIP centroid
        time.sleep(RATE_LIMIT)
        if len(updates) >= BATCH_SIZE:
            _flush_upg(db, updates)
        if (i + 1) % 2000 == 0:
            _prog(i+1, len(todo), 'upgrade')
    if updates:
        _flush_upg(db, updates)
    save_cp('upgrade', done | {r[0] for r in todo})
    _log(db, 'here_geocode_upgrade', stats['matched'], stats['called'])


def run_places(db, limit, dry_run, resume):
    print("\nPHASE 3: HERE Places — Websites & Phones")
    print("=" * 60)
    rows = get_places_candidates(db, limit)
    print(f"Churches needing contact enrichment: {len(rows):,}")
    done = load_cp('places') if resume else set()
    todo = [r for r in rows if r[0] not in done]
    remaining = quota_ok(len(todo))
    todo = todo[:remaining]
    print(f"To process: {len(todo):,}")
    if dry_run:
        for r in todo[:10]:
            print(f"  {r[0]:>8d} | {r[1][:45]:45s} | {r[2]:20s} {r[3]}")
        if len(todo) > 10:
            print(f"  ... {len(todo)-10:,} more")
        return
    updates = []
    for i, r in enumerate(todo):
        info = discover(r[1], r[2], r[3])
        track_calls()
        stats['called'] += 1
        if info['website'] or info['phone']:
            updates.append((r[0], info['website'], info['phone']))
            stats['matched'] += 1
            if info['website']:
                stats['website_found'] += 1
            if info['phone']:
                stats['phone_found'] += 1
        else:
            stats['errors'] += 1
        time.sleep(RATE_LIMIT)
        if len(updates) >= BATCH_SIZE:
            _flush_pl(db, updates)
        if (i + 1) % 1000 == 0:
            _prog(i+1, len(todo), 'places')
    if updates:
        _flush_pl(db, updates)
    save_cp('places', done | {r[0] for r in todo})
    _log(db, 'here_places', stats['matched'], stats['called'])


# ─── HELPERS ───

def _flush_geo(db, updates):
    for cid, lat, lng, quality in updates:
        conf = 0.90 if quality == 'street' else (0.70 if quality == 'city' else 0.50)
        db.execute("""UPDATE churches SET latitude=?, longitude=?,
            geocode_source='here', geocode_confidence=?,
            here_geocode_quality=?, here_last_geocoded=datetime('now'),
            last_updated=datetime('now') WHERE id=?""",
            (lat, lng, conf, quality, cid))
    db.commit()
    print(f"  Wrote {len(updates)} geocode updates"); updates.clear()


def _flush_upg(db, updates):
    for cid, lat, lng in updates:
        db.execute("""UPDATE churches SET latitude=?, longitude=?,
            geocode_source='here', geocode_confidence=0.90,
            here_geocode_quality='street', here_last_geocoded=datetime('now'),
            last_updated=datetime('now') WHERE id=?""",
            (lat, lng, cid))
    db.commit()
    print(f"  Wrote {len(updates)} upgrade updates"); updates.clear()


def _flush_pl(db, updates):
    for cid, website, phone in updates:
        parts = ["last_updated=datetime('now')"]
        if website:
            parts.append(f"website={json.dumps(website)}")
            parts.append("website_source='here_places'")
            parts.append("website_confidence=0.60")
        if phone:
            parts.append(f"phone={json.dumps(phone)}")
            parts.append("phone_source='here_places'")
        db.execute(f"UPDATE churches SET {', '.join(parts)} WHERE id=?", (cid,))
    db.commit()
    print(f"  Wrote {len(updates)} places updates"); updates.clear()


def _prog(done, total, phase):
    pct = done / total * 100
    hit = stats['matched'] / max(stats['called'], 1) * 100
    q = load_quota()
    print(f"  [{phase}] {done:,}/{total:,} ({pct:.1f}%) | "
          f"OK: {stats['matched']:,} ({hit:.0f}%) | "
          f"Quota: {q}/{MAX_MONTHLY}")


def _log(db, source, matched, attempted):
    db.execute("""INSERT INTO provenance_log(source, script_name, started_at,
        completed_at, churches_updated, churches_inserted, fields_populated,
        records_attempted, records_matched, status, notes)
        VALUES (?,?,?,?,?,0,?,?,?,'completed',?)""",
        (source, 'here_geocode.py', datetime.now().isoformat(),
         datetime.now().isoformat(), matched,
         'latitude,longitude,geocode_source,website,phone',
         attempted, matched,
         f'HERE API. {matched} enriched. Quota: {load_quota()}/{MAX_MONTHLY}'))
    db.commit()


def main():
    import argparse
    p = argparse.ArgumentParser(description='HERE.com Enrichment (30K/mo budget)')
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--missing', action='store_true')
    mode.add_argument('--upgrade', action='store_true')
    mode.add_argument('--places', action='store_true')
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--limit', type=int, default=0)
    p.add_argument('--resume', action='store_true')
    args = p.parse_args()

    global HERE_API_KEY
    HERE_API_KEY = load_api_key()
    if not HERE_API_KEY:
        print("ERROR: No HERE API key found."); sys.exit(1)

    q = quota_ok()
    if q == 0:
        sys.exit(1)
    print(f"HERE API: {HERE_API_KEY[:8]}...{HERE_API_KEY[-4:]}")
    print(f"Monthly quota remaining: {q:,}/{MAX_MONTHLY:,}")

    db = sqlite3.connect(DB_PATH)
    ensure_cols(db)
    db.commit()

    if args.missing:
        run_missing(db, args.limit, args.dry_run, args.resume)
    elif args.upgrade:
        run_upgrade(db, args.limit, args.dry_run, args.resume)
    elif args.places:
        run_places(db, args.limit, args.dry_run, args.resume)

    db.close()

    # Final report
    db2 = sqlite3.connect(DB_PATH)
    gt = db2.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NOT NULL AND latitude!=0").fetchone()[0]
    zc = db2.execute("SELECT COUNT(*) FROM churches WHERE geocode_source='zip_centroid'").fetchone()[0]
    he = db2.execute("SELECT COUNT(*) FROM churches WHERE geocode_source='here'").fetchone()[0]
    ms = db2.execute("SELECT COUNT(*) FROM churches WHERE latitude IS NULL OR latitude=0").fetchone()[0]
    print(f"\n{'='*60}")
    print("COVERAGE UPDATE")
    print(f"{'='*60}")
    print(f"  Geotagged:      {gt:>8,} ({gt/263712*100:.1f}%)")
    print(f"  HERE-geocoded:  {he:>8,}")
    print(f"  ZIP-centroid:   {zc:>8,}")
    print(f"  Still missing:  {ms:>8,}")
    print(f"  Quota used:     {load_quota():,}/{MAX_MONTHLY:,}")
    db2.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
