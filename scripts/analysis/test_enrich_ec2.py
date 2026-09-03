"""Quick test of catch-all + wayback on EC2."""
import sys, os
sys.path.insert(0, '/home/ubuntu/grantwizard')
os.chdir('/home/ubuntu/grantwizard')

from enrich_emails import check_catch_all, try_wayback, try_whois

# Test 3 domains
tests = ['gatesfoundation.com', 'societyfoundation.com', 'mellonfoundation.com']

for domain in tests:
    print(f"\n{'='*50}")
    print(f"  Domain: {domain}")
    print(f"{'='*50}")
    
    print(f"\n  🪤 Catch-all: ", end='')
    result = check_catch_all(domain)
    print(result)
    
    print(f"  📋 WHOIS: ", end='')
    emails = try_whois(domain)
    print(emails[:2] if emails else 'none')
    
    print(f"  🕰️ Wayback: ", end='')
    sys.stdout.flush()
    emails = try_wayback(domain)
    print(emails[:3] if emails else 'none')

print("\n✅ Test complete")
