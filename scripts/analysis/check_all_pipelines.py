import subprocess, json, os, time

KEY = os.path.expanduser("~/.ssh/grantwizard-key.pem")

# Enrichment instances
enrich = [
    ("3.16.31.223", 0),
    ("18.225.112.250", 1),
    ("3.137.138.1", 2),
    ("18.223.112.119", 3),
]

print("=== ENRICHMENT PIPELINE ===")
total_found = 0
for ip, chunk in enrich:
    try:
        cmd = 'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i ' + KEY + ' ubuntu@' + ip + ' "python3 -c \'import json; s=json.load(open(\\\"enriched_contacts_state_chunk' + str(chunk) + '.json\\\")); f=len(s.get(\\\"found_emails\\\",{})); d=len(s.get(\\\"domains_tried\\\",{})); ok=sum(1 for v in s.get(\\\"domains_tried\\\",{}).values() if v); print(f,ok,d)\'"'
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        parts = r.stdout.strip().split()
        if len(parts) == 3:
            found, dns_ok, dns_total = int(parts[0]), int(parts[1]), int(parts[2])
            total_found += found
            print("  Chunk %d: %d emails | DNS %d/%d" % (chunk, found, dns_ok, dns_total))
    except Exception as e:
        print("  Chunk %d: error - %s" % (chunk, str(e)[:60]))

print(f"\n  Total enrichment emails: {total_found}")

# Church scraper
print("\n=== CHURCH SCRAPER ===")
try:
    r = subprocess.run(
        f'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i {KEY} ubuntu@3.19.141.81 "tail -1 ~/church_scrape.log"',
        shell=True, capture_output=True, text=True, timeout=10
    )
    print(f"  {r.stdout.strip()}")
    
    # Count emails from output CSV
    r2 = subprocess.run(
        f'ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -i {KEY} ubuntu@3.19.141.81 "wc -l ~/church_emails_found.csv"',
        shell=True, capture_output=True, text=True, timeout=10
    )
    lines = int(r2.stdout.strip().split()[0]) - 1  # minus header
    print(f"  CSV rows (w/ email): {lines}")
except:
    print("  error checking")

# Summary
print("\n=== SUMMARY ===")
print(f"  Existing master list: ~900")
print(f"  Current total (est):  ~{total_found + 900}")
print(f"  Target:               10,000")
print(f"  Gap:                  ~{10000 - (total_found + 900)}")
