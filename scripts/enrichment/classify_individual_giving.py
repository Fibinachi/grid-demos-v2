"""
DeepSeek Foundation Classifier
===============================
For each foundation in the list, uses DeepSeek AI to determine
whether they fund INDIVIDUALS (grants to people) or only ORGANIZATIONS.

If they don't fund individuals at all, there's no point emailing
a PhD student asking for personal funding.

Usage: python classify_individual_giving.py
"""
import csv
import os
import json
import time
import re
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_CSV = os.path.join(SCRIPT_DIR, "theology_gmail_send.csv")
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "theology_individual_giving.csv")

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_KEY:
    # Try to load from .env
    env_path = os.path.join(SCRIPT_DIR, '.env')
    if os.path.exists(env_path):
        for line in open(env_path):
            if line.startswith('DEEPSEEK_API_KEY='):
                DEEPSEEK_KEY = line.strip().split('=', 1)[1]

API_URL = "https://api.deepseek.com/v1/chat/completions"
BATCH_SIZE = 50  # foundations per API call

# NTEE codes that are known to fund individuals
LIKELY_INDIVIDUAL_CODES = {
    'T22': 'Scholarships/Student Aid',  # Very likely
    'T30': 'Public Foundations',         # Sometimes
    'T20': 'Private Grantmaking',        # Varies
    'B82': 'Scholarships',               # Very likely
    'B83': 'Student Financial Aid',      # Very likely
    'O50': 'Youth Development',          # Sometimes
    'P20': 'Human Services',             # Varies
    'S20': 'Community Foundations',      # Sometimes fund individuals
    'T11': 'Community Foundations',      # Same
    'T31': 'Community Foundations',      # Same
    'T40': 'Voluntary Employees Beneficiary',
    'T50': 'Private Operating Foundations',
}

NOT_LIKELY_CODES = {
    'T23': 'Private Independent Foundations',  # Usually org-only
    'T24': 'Private Independent Foundations',
    'T90': 'Named Trusts',
    'T99': 'Other Philanthropy',
    'X20': 'Christian Churches',  # Churches fund orgs, sometimes individuals
    'X21': 'Protestant',
    'X22': 'Roman Catholic',
    'X23': 'Other Christian',
    'X30': 'Jewish',
    'X40': 'Islamic',
    'X50': 'Buddhist',
    'X99': 'Religious Other',
    'S22': 'Children\'s Services',
    'S30': 'Adult/Elderly Services',
    'S40': 'Disability Services',
}

def classify_by_ntee(ntee):
    """Quick pre-filter based on NTEE code alone."""
    code = (ntee or '').strip().upper()[:3]
    if code in LIKELY_INDIVIDUAL_CODES:
        return 'likely_individual', LIKELY_INDIVIDUAL_CODES[code]
    if code in NOT_LIKELY_CODES:
        return 'likely_org_only', NOT_LIKELY_CODES[code]
    return 'unknown', ''

def batch_classify(foundations_batch):
    """Send a batch of foundations to DeepSeek for classification."""
    prompt = """You are a foundation research expert. For each foundation below, determine:
1. Do they provide grants to INDIVIDUAL PEOPLE (scholarships, fellowships, student aid, personal grants) or only to ORGANIZATIONS?
2. What is their official website URL? (the main .org/.com page)

Output a JSON array of objects with:
- ein: the EIN
- funds_individuals: boolean (true/false)
- confidence: "high"/"medium"/"low"
- reason: 10 words max why they fund or don't fund individuals
- website: their official website URL (or null if unknown)

Foundations list (EIN | Name | NTEE | Assets | City/State):
"""
    for f in foundations_batch:
        prompt += f"\nEIN: {f['EIN']} | Name: {f['NAME']} | NTEE: {f.get('NTEE_CD','')} | Assets: {f.get('ASSET_AMT','')} | City/State: {f.get('CITY','')}, {f.get('STATE','')}"
    
    prompt += "\n\nRespond ONLY with the JSON array. No explanatory text."
    
    headers = {
        'Authorization': f'Bearer {DEEPSEEK_KEY}',
        'Content-Type': 'application/json',
    }
    
    payload = {
        'model': 'deepseek-chat',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.1,
        'max_tokens': 4000,
    }
    
    import urllib.request
    import ssl
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(API_URL, data=data, headers=headers, method='POST')
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            content = result['choices'][0]['message']['content']
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            else:
                print(f"  ⚠️ Could not parse JSON from response")
                print(f"  Response: {content[:200]}")
                return []
    except Exception as e:
        print(f"  ❌ API error: {e}")
        return []

def main():
    if not DEEPSEEK_KEY:
        print("❌ DEEPSEEK_API_KEY not found. Set it or add to .env file")
        return
    
    # Load foundations
    with open(INPUT_CSV) as f:
        rows = list(csv.DictReader(f))
    
    print(f"📂 Loaded {len(rows)} foundations")
    print(f"🔍 Classifying by individual giving likelihood...")
    print()
    
    # First pass: quick NTEE-based classification
    results = []
    need_deepseek = []
    
    for r in rows:
        ntee_verdict, ntee_reason = classify_by_ntee(r.get('NTEE_CD', ''))
        if ntee_verdict != 'unknown':
            results.append({
                'EIN': r['EIN'],
                'NAME': r['NAME'],
                'NTEE_CD': r.get('NTEE_CD', ''),
                'ASSET_AMT': r.get('ASSET_AMT', '0'),
                'EMAIL': r.get('EMAIL', ''),
                'WEBSITE': '',
                'funds_individuals': 'yes' if ntee_verdict == 'likely_individual' else 'no',
                'confidence': 'high',
                'reason': ntee_reason,
            })
        else:
            need_deepseek.append(r)
    
    print(f"  NTEE-based: {len(results)} classified ({len(need_deepseek)} need AI)")
    
    # Second pass: DeepSeek for unknown codes
    if need_deepseek:
        print(f"\n{'='*60}")
        print(f"  DEEPSEEK ANALYSIS ({len(need_deepseek)} foundations)")
        print(f"{'='*60}")
        
        for i in range(0, len(need_deepseek), BATCH_SIZE):
            batch = need_deepseek[i:i+BATCH_SIZE]
            pct = (i + len(batch)) / len(need_deepseek) * 100
            print(f"\n  Batch {i//BATCH_SIZE + 1}/{(len(need_deepseek)-1)//BATCH_SIZE + 1} ({pct:.0f}%)")
            
            classifications = batch_classify(batch)
            
            if classifications:
                for c in classifications:
                    results.append({
                        'EIN': c.get('ein', ''),
                        'NAME': next((r['NAME'] for r in batch if r['EIN'] == c.get('ein', '')), ''),
                        'NTEE_CD': next((r.get('NTEE_CD', '') for r in batch if r['EIN'] == c.get('ein', '')), ''),
                        'ASSET_AMT': next((r.get('ASSET_AMT', '0') for r in batch if r['EIN'] == c.get('ein', '')), ''),
                        'EMAIL': next((r.get('EMAIL', '') for r in batch if r['EIN'] == c.get('ein', '')), ''),
                        'WEBSITE': c.get('website', ''),
                        'funds_individuals': 'yes' if c.get('funds_individuals', False) else 'no',
                        'confidence': c.get('confidence', 'low'),
                        'reason': c.get('reason', ''),
                    })
            else:
                # API failed - mark as unknown
                for r in batch:
                    results.append({
                        'EIN': r['EIN'],
                        'NAME': r['NAME'],
                        'NTEE_CD': r.get('NTEE_CD', ''),
                        'ASSET_AMT': r.get('ASSET_AMT', '0'),
                        'EMAIL': r.get('EMAIL', ''),
                        'WEBSITE': '',
                        'funds_individuals': 'unknown',
                        'confidence': 'none',
                        'reason': 'API error',
                    })
            
            # Rate limit
            time.sleep(2)
        
        print(f"\n{'='*60}")
    
    # Save results
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        fn = ['EIN', 'NAME', 'NTEE_CD', 'ASSET_AMT', 'EMAIL', 'WEBSITE', 'funds_individuals', 'confidence', 'reason']
        w = csv.DictWriter(f, fieldnames=fn)
        w.writeheader()
        w.writerows(results)
    
    # Print summary
    yes_count = sum(1 for r in results if r['funds_individuals'] == 'yes')
    no_count = sum(1 for r in results if r['funds_individuals'] == 'no')
    unk_count = sum(1 for r in results if r['funds_individuals'] == 'unknown')
    
    print(f"\n{'='*60}")
    print(f"  RESULTS")
    print(f"{'='*60}")
    print(f"  Funds individuals: {yes_count} ({yes_count/len(results)*100:.0f}%)")
    print(f"  Organizations only: {no_count} ({no_count/len(results)*100:.0f}%)")
    print(f"  Unknown: {unk_count}")
    print(f"  Saved: {OUTPUT_CSV}")
    
    # Show top orgs that fund individuals
    print(f"\n  Foundations likely to fund individuals:")
    for r in sorted(results, key=lambda x: (0 if x['confidence'] == 'high' else 1 if x['confidence'] == 'medium' else 2, -float(x.get('ASSET_AMT', 0) or 0))):
        if r['funds_individuals'] == 'yes':
            print(f"    ✅ {r['NAME'][:40]:40s} [{r['confidence']:6s}] {r['EMAIL'][:30]}")

if __name__ == '__main__':
    main()
