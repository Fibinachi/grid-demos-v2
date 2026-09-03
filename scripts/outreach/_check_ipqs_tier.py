"""Check IPQS account tier."""
import urllib.request, json

key = "TDBK4MVtTuFqehjtWvS5YKAZU99b4hf9"

# Check account info
url = f"https://www.ipqualityscore.com/api/json/account/{key}"
req = urllib.request.Request(url, headers={"User-Agent": "GRID/1.0"})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    print("ACCOUNT INFO:")
    print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Account error: {e}")

# Test known-good domains
print("\nTEST EMAILS:")
for email in ["test@gmail.com", "test@outlook.com", "test@yahoo.com"]:
    url2 = f"https://www.ipqualityscore.com/api/json/email/{key}/{email}"
    req2 = urllib.request.Request(url2, headers={"User-Agent": "GRID/1.0"})
    try:
        with urllib.request.urlopen(req2, timeout=10) as resp:
            d = json.loads(resp.read())
        print(f"  {email}: valid={d.get('valid')}, score={d.get('overall_score')}, msg={d.get('message','')[:80]}")
    except Exception as e:
        print(f"  {email}: ERROR {e}")
