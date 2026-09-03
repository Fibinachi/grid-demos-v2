"""Quick test of IPQS and PDL keys"""
import os, json, urllib.request

ipqs_key = os.environ.get("IPQS_KEY", "")
pdl_key = os.environ.get("PDL_KEY", "")

# Test IPQS - correct endpoint
try:
    url = "https://www.ipqualityscore.com/api/json/email/" + ipqs_key + "/info@morrisfoundation.org"
    with urllib.request.urlopen(url, timeout=15) as r:
        d = json.loads(r.read())
        print("IPQS: valid=%-5s risky=%-5s score=%-3s generic=%-5s deliverability=%-5s" % (
            d.get("valid"), d.get("risky"), d.get("fraud_score"), d.get("generic"), d.get("deliverability")))
except Exception as e:
    print("IPQS error:", str(e)[:100])

# Test PDL
if pdl_key:
    try:
        url = "https://api.peopledatalabs.com/v5/company/enrich?domain=morrisfoundation.org"
        req = urllib.request.Request(url, headers={"X-Api-Key": pdl_key})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read())
            name = d.get("name", "N/A")[:40]
            industry = d.get("industry", "N/A")[:30]
            print("PDL:  name=%-40s industry=%-30s" % (name, industry))
            if "error" in d:
                print("PDL msg:", d["error"].get("message","")[:80])
    except Exception as e:
        print("PDL error:", str(e)[:100])
else:
    print("PDL: no key set")
