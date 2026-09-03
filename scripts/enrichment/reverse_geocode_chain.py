"""
Chain-run reverse geocoding through multiple countries sequentially.
Usage: python scripts/enrichment/reverse_geocode_chain.py
"""
import subprocess, sys, os, time

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reverse_geocode_countries.py')

# Priority order: Canada, UK, then by record count descending
COUNTRIES = [
    ('IN', 'India'),
    ('BR', 'Brazil'),
    ('JP', 'Japan'),
    ('ID', 'Indonesia'),
    ('DE', 'Germany'),
    ('FR', 'France'),
    ('GB', 'United Kingdom'),
    ('IT', 'Italy'),
    ('CA', 'Canada'),
    ('SA', 'Saudi Arabia'),
    ('TH', 'Thailand'),
    ('ES', 'Spain'),
    ('MX', 'Mexico'),
    ('PH', 'Philippines'),
    ('AU', 'Australia'),
    ('IE', 'Ireland'),
    ('NG', 'Nigeria'),
    ('AR', 'Argentina'),
    ('CO', 'Colombia'),
    ('PE', 'Peru'),
    ('VE', 'Venezuela'),
    ('CL', 'Chile'),
    ('EC', 'Ecuador'),
    ('GT', 'Guatemala'),
    ('DO', 'Dominican Republic'),
    ('HN', 'Honduras'),
    ('SV', 'El Salvador'),
    ('NI', 'Nicaragua'),
    ('CR', 'Costa Rica'),
    ('PA', 'Panama'),
    ('BO', 'Bolivia'),
    ('PY', 'Paraguay'),
    ('UY', 'Uruguay'),
]

# Since CA is already running, start from GB
# Note: CA should be removed from the list since it's already being processed
COUNTRIES = [(c, n) for c, n in COUNTRIES if c != 'CA']

# Reorder: GB first (user priority), then rest
priority = [('GB', 'United Kingdom')]
rest = [(c, n) for c, n in COUNTRIES if c != 'GB']
COUNTRIES = priority + rest

print(f"Chain reverse geocoding: {len(COUNTRIES)} countries")
print(f"Script: {SCRIPT}")
print(f"Order: {', '.join(c for c, _ in COUNTRIES)}")
print()

total_ok = 0
total_fail = 0

for code, name in COUNTRIES:
    print(f"{'='*60}")
    print(f"  Starting: {name} ({code})")
    print(f"{'='*60}")
    sys.stdout.flush()
    
    result = subprocess.run(
        [sys.executable, SCRIPT, '--countries', code],
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    
    if result.returncode == 0:
        total_ok += 1
        print(f"  {name}: OK")
    else:
        total_fail += 1
        print(f"  {name}: FAILED (exit {result.returncode})")
    
    # Brief pause between countries
    if code != COUNTRIES[-1][0]:
        print(f"  Pausing 5s before next country...")
        time.sleep(5)

print(f"\n{'='*60}")
print(f"Chain complete: {total_ok} OK, {total_fail} failed")
