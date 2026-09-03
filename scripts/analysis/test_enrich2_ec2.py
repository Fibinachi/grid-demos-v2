"""Test catch-all + wayback on real foundation domains."""
import sys, os
sys.path.insert(0, '/home/ubuntu/grantwizard')
os.chdir('/home/ubuntu/grantwizard')

from enrich_emails import check_catch_all, try_wayback, get_mx

# Real foundation domains with actual websites
tests = [
    ('Gates Foundation', 'gatesfoundation.org'),
    ('Knight Foundation', 'knightfoundation.org'),
    ('MacArthur Foundation', 'macfound.org'),
    ('Rockefeller Foundation', 'rockefellerfoundation.org'),
    ('Ford Foundation', 'fordfoundation.org'),
    ('Annie E Casey Foundation', 'aecf.org'),
    ('Conrad N Hilton', 'hiltonfoundation.org'),
    ('Walton Family', 'waltonfamilyfoundation.org'),
]

for name, domain in tests:
    print(f"\n  {name}")
    print(f"  {'─'*40}")
    
    # Check MX first
    mx = get_mx(domain)
    print(f"  📍 {domain:35s} MX: {mx[:1] if mx else 'NONE'}")
    
    if mx:
        result = check_catch_all(domain)
        icon = '🪤' if result == 'catchall' else '🔒' if result == 'strict' else '❓'
        print(f"  {icon} Catch-all: {result}")
    
    print(f"  🕰️ Wayback: ", end='')
    sys.stdout.flush()
    wayback_emails = try_wayback(domain)
    if wayback_emails:
        for e in wayback_emails[:5]:
            print(f"\n        {e}")
    else:
        print("none")

print("\n✅ Done")
