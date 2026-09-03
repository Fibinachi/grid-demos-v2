"""Ticker — shows VK scraper progress at a glance."""
import sqlite3, os, time
from datetime import datetime

CHECKPOINT = 'E:/grid/_osm_checkpoint.txt'
DB = 'E:/grid/churches.db'
GROUPS = {
    "Final 8": {"JP","ID","AR","IN","AU","BR","US","CA"},
}

def tick():
    with open(CHECKPOINT) as f:
        done = {line.strip() for line in f if line.strip()}
    
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("SELECT COUNT(1) FROM churches WHERE source='osm_import'")
    osm_total = c.fetchone()[0]
    c.execute("SELECT COUNT(1) FROM churches")
    grand_total = c.fetchone()[0]
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"  VK SCRAPER — {datetime.now().strftime('%H:%M:%S')}")
    print(f"  Query: amenity=place_of_worship + building=shrine + wayside_shrine")
    print(f"  DB: {grand_total:,} churches ({osm_total:,} OSM)")
    print(f"{'='*60}")
    
    for group, codes in GROUPS.items():
        remaining = [c for c in codes if c not in done]
        complete = [c for c in codes if c in done]
        bar = "█" * len(complete) + "░" * len(remaining)
        status = "✅ DONE" if not remaining else f"🔄 {len(complete)}/{len(codes)}"
        rlist = ", ".join(remaining) if remaining else ""
        print(f"  {group:12s} [{bar}] {status}  {rlist}")
    
    total_done = sum(1 for g in GROUPS.values() for c in g if c in done)
    total = sum(len(g) for g in GROUPS.values())
    print(f"\n  OVERALL: {total_done}/{total} ({total_done*100//total}%)")
    
    # Current activity
    mtime = os.path.getmtime(CHECKPOINT)
    ago = time.time() - mtime
    if ago < 300:
        print(f"  Last checkpoint: {ago:.0f}s ago (scraper ACTIVE)")
    else:
        print(f"  Last checkpoint: {ago/60:.0f}m ago (may be idle)")

if __name__ == "__main__":
    import sys
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            tick()
            print(f"\n  Refreshing every {interval}s — Ctrl+C to stop")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n  Ticker stopped.")
