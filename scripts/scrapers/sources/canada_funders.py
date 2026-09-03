#!/usr/bin/env python3
"""
Canadian Foundation & Funding Source Finder
============================================
Builds a targeted list of Canadian funding sources for theological education at
Trinity College, University of Toronto.

Sources include:
1. CRA (Canada Revenue Agency) registered charities search
2. Known Canadian foundations that fund education/religion
3. Canadian government student aid programs
4. Canadian denominational funding sources
5. Direct scraping of known Canadian foundation websites
"""

import urllib.request
import urllib.parse
import json
import csv
import os
import re
import time
import sys

base_dir = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# KNOWN CANADIAN FUNDING SOURCES FOR THEOLOGICAL EDUCATION
# ============================================================
# These are manually curated from research on Canadian funders
# that support religious/theological education

CANADIAN_FUNDERS = [
    # Major Canadian foundations that fund education/religion
    ("The J.W. McConnell Family Foundation", "https://mcconnellfoundation.ca", "Major Canadian foundation, education focus"),
    ("The Vancouver Foundation", "https://www.vancouverfoundation.ca", "BC-based, education and community"),
    ("The Calgary Foundation", "https://calgaryfoundation.org", "Alberta-based community foundation"),
    ("The Edmonton Community Foundation", "https://www.ecfoundation.org", "Alberta education funding"),
    ("The Winnipeg Foundation", "https://www.wpgfdn.org", "Manitoba education funding"),
    ("The Ontario Trillium Foundation", "https://otf.ca", "Ontario government funder"),
    ("The Catherine Donnelly Foundation", "https://www.catherinedonnellyfoundation.org", "Adult education, theological"),
    ("The George Cedric Metcalf Foundation", "https://metcalffoundation.com", "Ontario social programs"),
    ("The Atkinson Foundation", "https://atkinsonfoundation.ca", "Ontario social justice"),
    ("The Laidlaw Foundation", "https://laidlawfdn.org", "Education and youth"),
    ("The Max Bell Foundation", "https://www.maxbell.org", "Education and public policy"),
    ("The Walter and Duncan Gordon Foundation", "https://www.gordonfn.org", "Canadian education"),
    ("The William and Nancy Turner Foundation", "", "Religious education focus"),
    ("The Schad Foundation", "", "Education funding"),
    ("The Sprott Foundation", "", "Education and religion"),
    
    # Canadian religious/denominational funders
    ("The United Church of Canada Foundation", "https://unitedchurchfoundation.ca", "United Church - directly relevant"),
    ("The Anglican Foundation of Canada", "https://www.anglicanfoundation.org", "Anglican - directly relevant"),
    ("The Presbyterian Church in Canada Foundation", "https://presbyterianfoundation.ca", "Presbyterian funding"),
    ("The Catholic Health Sponsors of Ontario", "", "Catholic education funding"),
    ("The Catholic Foundation of Ontario", "", "Catholic education"),
    ("The Jesuit Foundation of Canada", "", "Jesuit education"),
    ("The Salvation Army Foundation Canada", "", "Christian education"),
    ("The Canadian Bible Society", "https://www.biblesociety.ca", "Biblical education funding"),
    ("The Canadian Council of Churches", "https://www.councilofchurches.ca", "Ecumenical funding"),
    
    # Specific to University of Toronto / Trinity College
    ("Trinity College Alumni Association", "https://www.trinity.utoronto.ca/alumni", "Alumni funding for Trinity"),
    ("The University of Toronto Faculty of Divinity", "https://www.divinity.utoronto.ca", "Divinity school funding"),
    ("The Toronto School of Theology", "https://www.tst.edu", "Multi-denominational theology consortium"),
    
    # Canadian scholarship/grant programs
    ("Canada Student Grants Program", "https://www.canada.ca/en/services/benefits/education.html", "Federal student grants"),
    ("Ontario Student Assistance Program (OSAP)", "https://osap.gov.on.ca", "Ontario student aid"),
    ("Canada Graduate Scholarships", "https://www.nserc-crsng.gc.ca", "Federal graduate research"),
    ("The Social Sciences and Humanities Research Council (SSHRC)", "https://www.sshrc-crsh.gc.ca", "Federal humanities/theology funding"),
    
    # Canadian theological schools associations
    ("The Association of Theological Schools in Canada", "https://www.atsz.ca", "Theological education advocacy"),
    ("The Canadian Association for Theological Education", "", "Theological education network"),
    
    # Religious orders with education funding
    ("The Sisters of St. Joseph of Toronto", "", "Religious order education funding"),
    ("The Sisters of Mercy of the Americas", "", "Education funding"),
    ("The Basilian Fathers", "https://www.basilian.org", "Catholic education"),
    ("The Congregation of St. Basil", "", "Education-focused religious order"),
    ("The Redemptorists of Canada", "", "Catholic mission and education"),
]

# ============================================================
# CRA CHARITY SEARCH
# ============================================================

CRA_SEARCH_URL = "https://apps.cra-arc.gc.ca/ebci/hacc/srch/pub/dsplyBscSrch"

def search_cra(query, max_pages=3):
    """Search CRA charity database for organizations matching query."""
    results = []
    print(f"\nSearching CRA for: {query}")
    
    for page in range(1, max_pages + 1):
        params = {
            'q': query,
            'dsrdPg': page,
        }
        url = f"{CRA_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        
        try:
            req = urllib.request.Request(url, headers={'Accept': 'text/html'})
            resp = urllib.request.urlopen(req, timeout=15)
            html = resp.read().decode('utf-8', errors='replace')
            
            # Parse results from HTML
            # Look for charity entries in the table
            entries = re.findall(
                r'<a[^>]*href="[^"]*dsplyPrfl[^"]*bn=[^"]*"[^>]*>\s*([^<]+)\s*</a>',
                html
            )
            
            # Also get BN/registration numbers
            bns = re.findall(r'bn=(\d+)', html)
            
            # Get locations
            locations = re.findall(r'<td[^>]*>([^<]*,\s*[A-Z]{2})</td>', html)
            
            if not entries:
                # Try alternative parsing
                entries = re.findall(r'<strong[^>]*class="[^"]*title[^"]*"[^>]*>([^<]+)</strong>', html)
            
            if entries:
                print(f"  Page {page}: {len(entries)} results")
                for i, name in enumerate(entries[:10]):
                    bn = bns[i] if i < len(bns) else ''
                    loc = locations[i] if i < len(locations) else ''
                    results.append({'name': name.strip(), 'bn': bn, 'location': loc})
                    print(f"    {bn} - {name.strip()[:60]} ({loc})")
            else:
                print(f"  Page {page}: No results found")
                break
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  Page {page}: Error - {e}")
            break
    
    return results


def scrape_website_for_contact(url, name):
    """Scrape a foundation's website for contact/email info."""
    email = ''
    phone = ''
    
    if not url:
        return email, phone
    
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; GrantWizard/1.0)'
        })
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        
        # Find emails
        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)
        if emails:
            # Filter out generic emails, prefer contact/donate/info
            for e in emails:
                if any(x in e.lower() for x in ['info@', 'contact@', 'hello@', 'grant', 'foundation', name.split()[-1].lower()[:5]]):
                    email = e
                    break
            if not email:
                email = emails[0]
        
        # Find phone
        phones = re.findall(r'(?:\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})', html)
        if phones:
            phone = phones[0]
            
    except Exception as e:
        pass
    
    return email, phone


def main():
    print("=" * 70)
    print("  CANADIAN FUNDING SOURCE FINDER")
    print("  Building targeted list for Trinity College theological education")
    print("=" * 70)
    
    # ============================================================
    # PART 1: Search CRA for Canadian charities related to theology
    # ============================================================
    print(f"\n{'─' * 70}")
    print("PART 1: CRA Charity Database Search")
    print(f"{'─' * 70}")
    
    cra_searches = [
        "theological+education+foundation",
        "religious+foundation+scholarship",
        "theology+seminary+foundation",
        "christian+education+foundation",
        "anglican+education+foundation",
        "divinity+school+foundation",
    ]
    
    all_cra_results = []
    seen_names = set()
    
    for query in cra_searches:
        results = search_cra(query, max_pages=2)
        for r in results:
            name_key = r['name'].lower().strip()
            if name_key not in seen_names:
                seen_names.add(name_key)
                all_cra_results.append(r)
        time.sleep(1)
    
    print(f"\nTotal unique CRA results: {len(all_cra_results)}")
    
    # ============================================================
    # PART 2: Build combined list
    # ============================================================
    print(f"\n{'─' * 70}")
    print("PART 2: Enriching Canadian funders with contact info")
    print(f"{'─' * 70}")
    
    all_funders = []
    
    # Add known Canadian funders
    for name, url, notes in CANADIAN_FUNDERS:
        print(f"\n  {name}...")
        
        # Try to scrape contact info
        email, phone = scrape_website_for_contact(url, name)
        
        domain = ''
        if url:
            domain = re.sub(r'^https?://', '', url).split('/')[0]
        
        all_funders.append({
            'name': name,
            'url': url or '',
            'domain': domain,
            'email': email,
            'phone': phone,
            'notes': notes,
            'source': 'curated_list',
            'country': 'Canada',
        })
        
        if email:
            print(f"    Email: {email}")
        if phone:
            print(f"    Phone: {phone}")
        
        time.sleep(1)
    
    # Add CRA results
    for r in all_cra_results:
        all_funders.append({
            'name': r['name'],
            'url': '',
            'domain': '',
            'email': '',
            'phone': '',
            'notes': f"CRA charity, BN: {r.get('bn', '')}, Location: {r.get('location', '')}",
            'source': 'cra_search',
            'country': 'Canada',
        })
    
    # ============================================================
    # PART 3: Write output
    # ============================================================
    output_path = os.path.join(base_dir, 'canadian_funding_sources.csv')
    fieldnames = ['name', 'url', 'domain', 'email', 'phone', 'notes', 'source', 'country']
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_funders)
    
    print(f"\n{'=' * 70}")
    print(f"RESULTS SUMMARY")
    print(f"{'=' * 70}")
    print(f"Total Canadian funding sources: {len(all_funders)}")
    print(f"  Curated list: {len([r for r in all_funders if r['source']=='curated_list'])}")
    print(f"  CRA search results: {len([r for r in all_funders if r['source']=='cra_search'])}")
    print(f"  With emails: {len([r for r in all_funders if r['email']])}")
    print(f"  With websites: {len([r for r in all_funders if r['url']])}")
    
    print(f"\nSaved: {output_path}")
    
    # Print the curated list with contact info
    print(f"\n{'=' * 70}")
    print(f"CURATED CANADIAN FUNDERS (sorted by relevance)")
    print(f"{'=' * 70}")
    
    # Known Canadian funders relevant to theological education
    top_picks = [
        ("Anglican Foundation of Canada", "https://www.anglicanfoundation.org", "Directly relevant - Anglican Church of Canada"),
        ("United Church of Canada Foundation", "https://unitedchurchfoundation.ca", "Education grants for theology"),
        ("J.W. McConnell Family Foundation", "https://mcconnellfoundation.ca", "Major Canadian education funder"),
        ("Trinity College Alumni Association", "https://www.trinity.utoronto.ca/alumni", "Direct alumni funding"),
        ("Toronto School of Theology", "https://www.tst.edu", "Local theology consortium"),
        ("Ontario Student Assistance Program", "https://osap.gov.on.ca", "Ontario government aid"),
        ("SSHRC", "https://www.sshrc-crsh.gc.ca", "Federal humanities/theology research"),
        ("Catherine Donnelly Foundation", "https://www.catherinedonnellyfoundation.org", "Adult education, theological focus"),
        ("Vancouver Foundation", "https://www.vancouverfoundation.ca", "Major Canadian community foundation"),
        ("Laidlaw Foundation", "https://laidlawfdn.org", "Education and youth programs"),
    ]
    
    for name, url, desc in top_picks:
        print(f"  {name}")
        print(f"    URL: {url}")
        print(f"    Why: {desc}")
        print()


if __name__ == '__main__':
    main()
