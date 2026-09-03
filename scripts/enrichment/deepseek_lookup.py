#!/usr/bin/env python3
"""
Use DeepSeek API to find real contact emails for foundations.
Processes in batches for efficiency.
"""
import json
import csv
import os
import sys
import time
import urllib.request

base_dir = os.path.dirname(os.path.abspath(__file__))

DEEPSEEK_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
if not DEEPSEEK_KEY:
    raise ValueError("DEEPSEEK_API_KEY environment variable is required")
API_URL = "https://api.deepseek.com/v1/chat/completions"

def ask_deepseek(batch, max_retries=2):
    """Ask DeepSeek for contact info for a batch of foundations."""
    foundations_text = "\n".join([f"{r['EIN']}|{r['NAME']}|{r.get('DOMAIN','')}" for r in batch])
    
    prompt = f"""For each foundation below, find their REAL official website and a real contact email (preferably a person's email like director@, president@, or at least a working contact form). Skip generic info@ addresses if there's a better option.

Return ONLY a JSON array with one object per foundation:
[{{"ein": "EIN", "website": "real url", "email": "real contact email", "confidence": "high/medium/low"}}]

Foundations:
{foundations_text}"""
    
    payload = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 2000,
    }).encode()
    
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(API_URL, data=payload, 
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {DEEPSEEK_KEY}"
                })
            resp = urllib.request.urlopen(req, timeout=30)
            result = json.loads(resp.read())
            content = result['choices'][0]['message']['content']
            
            # Parse JSON from response
            # Find JSON array in the response
            import re
            json_match = re.search(r'\[.*?\]', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(content)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            print(f"  DeepSeek error: {e}", flush=True)
            return []

def main():
    # Load the 529 foundations from the send list (with domains)
    input_path = os.path.join(base_dir, 'staff_scrape_input.csv')
    with open(input_path) as f:
        all_rows = list(csv.DictReader(f))
    
    # First try the 95 resolving domains with the staff finder
    # Then use DeepSeek for the 434 non-resolving ones
    resolving_path = os.path.join(base_dir, 'staff_scrape_resolving.csv')
    with open(resolving_path) as f:
        resolving = list(csv.DictReader(f))
    
    resolving_eins = {r['EIN'] for r in resolving}
    non_resolving = [r for r in all_rows if r['EIN'] not in resolving_eins]
    
    print(f"Total foundations: {len(all_rows)}")
    print(f"Resolving domains (scrape these): {len(resolving)}")
    print(f"Non-resolving (use DeepSeek): {len(non_resolving)}")
    
    # Process non-resolving with DeepSeek in batches of 20
    batch_size = 20
    all_deepseek_results = []
    
    for i in range(0, len(non_resolving), batch_size):
        batch = non_resolving[i:i+batch_size]
        print(f"\nDeepSeek batch {i//batch_size + 1}/{(len(non_resolving)-1)//batch_size + 1}: {len(batch)} foundations...", flush=True)
        
        results = ask_deepseek(batch)
        all_deepseek_results.extend(results)
        
        if results:
            print(f"  Got {len(results)} results")
            for r in results[:3]:
                print(f"  {r.get('ein','')[:10]} - {r.get('email','N/A')} ({r.get('website','')})")
        else:
            print(f"  No results from DeepSeek")
        
        # Rate limit
        if i + batch_size < len(non_resolving):
            time.sleep(2)
    
    # Save DeepSeek results
    ds_path = os.path.join(base_dir, 'deepseek_contacts_found.json')
    with open(ds_path, 'w') as f:
        json.dump(all_deepseek_results, f, indent=2)
    print(f"\nDeepSeek results saved: {ds_path}")
    print(f"Total results: {len(all_deepseek_results)}")
    
    # Also save as CSV
    csv_path = os.path.join(base_dir, 'deepseek_contacts_found.csv')
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['EIN', 'WEBSITE', 'EMAIL', 'CONFIDENCE'])
        for r in all_deepseek_results:
            w.writerow([r.get('ein',''), r.get('website',''), r.get('email',''), r.get('confidence','')])
    print(f"CSV saved: {csv_path}")

if __name__ == '__main__':
    main()
