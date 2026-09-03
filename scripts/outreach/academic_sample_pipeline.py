#!/usr/bin/env python3
"""
GrantWizard — Seminary/Academic Sample Pipeline
Sends religious studies programs a curated sample showing the dataset's diversity
across faith traditions, income levels, and enrichment layers.

Usage:
  .venv\Scripts\python scripts/outreach/academic_sample_pipeline.py --dry-run
  .venv\Scripts\python scripts/outreach/academic_sample_pipeline.py --limit 5
"""
import os, sys, base64, json, time, sqlite3, argparse, random
from email.message import EmailMessage
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

PROJECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DB_PATH = os.path.join(PROJECT_DIR, "churches.db")
TOKEN_FILE = os.path.join(SCRIPT_DIR, "..", "..", "data", "gmail_token.json")
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "..", "..", "data", "gmail_credentials.json")
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
CHECKPOINT_FILE = os.path.join(SCRIPT_DIR, "academic_sample_checkpoint.json")

SENDER_EMAIL = "charlesaprescottjr@gmail.com"
SENDER_NAME = "Charles Prescott"

def get_gmail_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


def get_seminaries(limit=0):
    """Get seminary/religious school contacts."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("""
        SELECT id, name, city, state, email, website, denomination, faith_tradition
        FROM churches
        WHERE (name LIKE '%seminary%' OR name LIKE '%divinity%' OR name LIKE '%bible college%'
               OR name LIKE '%theological%' OR name LIKE '%school of theology%'
               OR name LIKE '%rabbinical%' OR name LIKE '%yeshiva%'
               OR name LIKE '%islamic college%')
          AND email != '' AND email IS NOT NULL AND email NOT LIKE '% %'
        ORDER BY name
    """)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    
    if limit > 0:
        rows = rows[:limit]
    return rows


def get_demo_sample():
    """Build a diverse sample of 6 churches showing data breadth."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    samples = []
    
    def pick_sample(where_clause, label):
        """Pick one church with ZIP-level ACS data."""
        c.execute(f"""
            SELECT c.name, c.city, c.state, c.zip, c.faith_tradition, c.denomination,
                   cz.median_hh_income as acs_median_income,
                   cz.poverty_rate as acs_poverty_rate,
                   cz.total_pop as acs_total_pop,
                   cz.median_home_value as acs_median_home_value,
                   c.food_desert_low_inc_low_access_1_10,
                   c.latitude, c.longitude, c.tract_fips, c.ein,
                   c.family, c.org_type
            FROM churches c
            JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
            WHERE {where_clause}
              AND cz.median_hh_income BETWEEN 10000 AND 250000
            ORDER BY RANDOM() LIMIT 1
        """)
        r = c.fetchone()
        if r:
            samples.append(dict(r))
            print(f"  [OK] {label}")
        else:
            print(f"  [--] {label} - no match")
    
    # Top 5 denomination families (2 each)
    pick_sample("c.family = 'Baptist Churches' AND cz.poverty_rate > 20", "Baptist - low-income area")
    pick_sample("c.family = 'Baptist Churches' AND cz.median_hh_income > 100000", "Baptist - high-income area")
    pick_sample("c.family = 'Pentecostal Churches'", "Pentecostal")
    pick_sample("c.family = 'Catholic Churches' AND cz.poverty_rate > 20", "Catholic - low-income area")
    pick_sample("c.family = 'Catholic Churches' AND cz.median_hh_income > 120000", "Catholic - high-income area")
    pick_sample("c.family = 'Presbyterian Churches' AND cz.poverty_rate > 15", "Presbyterian - low-income area")
    pick_sample("c.family = 'Presbyterian Churches' AND cz.median_hh_income > 100000", "Presbyterian - high-income area")
    pick_sample("c.family = 'Churches of Christ'", "Churches of Christ")
    # Other Christian diversity
    pick_sample("c.family = 'Lutheran Churches' AND cz.poverty_rate > 15", "Lutheran - low-income area")
    pick_sample("c.family = 'Methodist Churches' AND cz.poverty_rate > 15", "Methodist - low-income area")
    pick_sample("c.family = 'Episcopal and Anglican Churches' AND cz.median_hh_income > 120000", "Episcopal - high-income area")
    pick_sample("c.family = 'Orthodox Churches'", "Orthodox Christian")
    # Non-Christian faiths
    pick_sample("c.faith_tradition = 'jewish'", "Jewish")
    pick_sample("c.faith_tradition = 'muslim'", "Muslim")
    pick_sample("c.faith_tradition = 'buddhist'", "Buddhist")
    pick_sample("c.faith_tradition = 'hindu'", "Hindu")
    pick_sample("c.faith_tradition = 'sikh'", "Sikh")
    pick_sample("c.faith_tradition = 'bahai'", "Baha'i")
    # Associated organizations
    pick_sample("c.org_type = 'seminary'", "Seminary")
    pick_sample("c.org_type = 'foundation' AND cz.median_hh_income > 80000", "Foundation")
    pick_sample("c.org_type = 'school'", "School/College")
    
    conn.close()
    return samples


def format_sample(s):
    """Format one sample church as a readable block."""
    fd = "Yes" if s.get('food_desert_low_inc_low_access_1_10') == 1 else "No"
    inc = f"${s['acs_median_income']:,.0f}" if s.get('acs_median_income') else "N/A"
    pov = f"{s['acs_poverty_rate']:.1f}%" if s.get('acs_poverty_rate') else "N/A"
    pop = f"{int(s['acs_total_pop']):,}" if s.get('acs_total_pop') else "N/A"
    org = s.get('org_type', '') or ''
    ft = s.get('faith_tradition') or ''
    fam = s.get('family', '') or ft or ''
    
    return (
        f"  {s['name'][:45]:45s} | {s.get('city','') or '':18s} {s.get('state','') or ''}\n"
        f"  Type: {org:15s} | Family: {fam[:20]:20s} | Denom: {s.get('denomination','') or '':25s}\n"
        f"  Median income: {inc:>10s} | Poverty: {pov:>6s} | Population: {pop:>10s}\n"
        f"  Food desert: {fd:6s} | Tract FIPS: {s.get('tract_fips','') or 'N/A':15s} | EIN: {s.get('ein','') or 'N/A':12s}\n"
        f"  Coords: {s.get('latitude','N/A')}, {s.get('longitude','N/A')}"
    )


def build_email(seminary, samples):
    """Build email for a seminary contact showing diverse sample data."""
    
    sem_name = seminary.get('name', 'your program')
    contact_name = sem_name.split('(')[0].strip()
    
    # Format samples
    sample_texts = []
    for i, s in enumerate(samples, 1):
        ft_val = s.get('faith_tradition') or s.get('family') or 'unknown'
        ft = str(ft_val).title()
        sample_texts.append(f"\n── Sample {i}: {s['name']} ({ft})\n" + format_sample(s))
    
    samples_block = "\n".join(sample_texts)
    
    body = f"""Hi there,

I've built a national religious organization database — 385,000 records across every faith tradition, cross-referenced against demographic, economic, geographic, and political data at multiple levels.

To put that number in perspective: the EPA-curated, USGS-hosted HIFLD dataset (the government standard, built from the IRS Exempt Organizations BMF) contains roughly 255,000 places of worship. This dataset captures an additional 130,000+ records — smaller congregations, newer church plants, and non-filing organizations tax-exempt under IRS §508(c)(1)(A) that don't appear in government data at all.

Here's a sample showing the breadth of the data — 20 organizations spanning faith traditions and income levels:

{samples_block}

What this dataset includes:

• 385,097 religious organizations — churches, mosques, synagogues, temples, seminaries, foundations, schools
• Every US state and territory
• Multi-faith: Christian (275K), Jewish (17K), Muslim (4.6K), Buddhist (2.7K), Hindu (985), Sikh (245), Baha'i (1.9K), and more
• Sub-tradition classification — mosques tagged as Sunni, Shia, or Nation of Islam; synagogues as Orthodox, Conservative, Reform, or Chabad; Christian denominations across 50+ sub-traditions (Baptist, Pentecostal, Lutheran, Catholic, Presbyterian, Methodist, Episcopal, Orthodox, Reformed, and more)
• Three classification methods: name heuristic, website content analysis, and IRS filing data — each record tagged with source and confidence score
• ACS demographics at ZIP and census tract levels — 61% enriched (poverty, income, education, housing, age, race)
• County-level presidential election returns 2000-2024 (MIT Election Lab): Democratic/Republican vote shares, margins, total turnout — 281K churches joinable
• Voter registration data (EAC EAVS 2020-2024): active/inactive registrations, new registrations, ballots cast, turnout rates, polling place counts
• USDA food desert indicators — tract-level (5.4% enriched)
• FCC broadcast coverage — station proximity (FM/AM/TV)
• FBI UCR crime data — violent crime, property crime, murder, robbery, aggravated assault, burglary, larceny, and motor vehicle theft rates per 100K (county level)
• Geocoded coordinates — 73% (lat/lng), ArcGIS-ready
• IRS EIN linkage — 65%
• Religious adherence rates — county level (ARDA)
• Historic census data — can interleave for longitudinal analysis
• Website URLs, phone numbers, email addresses

This is tract-level geography — neighborhoods of ~4,000 people — not county averages. Useful for spatial analysis, sociology of religion, political geography, demographic research, public policy analysis, and grant research.

This dataset would support a wide range of academic work — sociology of religion (congregational ecology, neighborhood effects), political science (religious geography × voting behavior, polarization, turnout patterns), and public policy (poverty mapping, food access gaps, community infrastructure analysis).

If this is of interest, I'd be glad to share a fuller extract, a custom query for your specific research, or discuss a data license for your program.

Best,
Charles Prescott"""

    return body


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"sent": []}


def save_checkpoint(data):
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    
    print("GrantWizard — Seminary/Academic Sample Pipeline")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    
    # Get fresh diverse sample
    samples = get_demo_sample()
    print(f"Demo sample: {len(samples)} records")
    for s in samples:
        ft = (s.get('faith_tradition') or s.get('family') or '?').title()[:12]
        inc = s.get('acs_median_income', 0) or 0
        fam = s.get('family', '') or ''
        org = s.get('org_type', '') or ''
        print(f"  {ft:12s} | {s['name'][:45]:45s} | Inc: ${inc:,.0f} | {org:15s} {fam[:20]}")
    
    # Get seminaries
    seminaries = get_seminaries(limit=args.limit)
    print(f"\nSeminaries: {len(seminaries)}")
    
    cp = load_checkpoint() if args.resume else {"sent": []}
    sent_ids = set(cp.get("sent", []))
    
    if not args.dry_run:
        service = get_gmail_service()
    
    sent_count = 0
    for i, sem in enumerate(seminaries):
        sem_id = sem['id']
        email = sem['email']
        name = sem['name']
        
        if sem_id in sent_ids:
            continue
        if not email or '@' not in email or ' ' in email:
            continue
        
        body = build_email(sem, samples)
        subject = f"Religious organization database — 385K records, multi-faith, with tract-level demographics"
        
        if args.dry_run:
            print(f"\n[{i+1}/{len(seminaries)}] {name[:50]:50s} | {email}")
            print(f"  Subject: {subject[:80]}")
            print(f"  Preview: {body[:300]}...")
            continue
        
        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg['To'] = email
            msg['From'] = SENDER_EMAIL
            msg['Subject'] = subject
            
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            service.users().messages().send(userId='me', body={'raw': raw}).execute()
            
            print(f"  [{i+1}/{len(seminaries)}] ✅ {name[:45]:45s} -> {email}")
            sent_count += 1
            sent_ids.add(sem_id)
            
            if sent_count % 5 == 0:
                save_checkpoint({"sent": list(sent_ids)})
            
            time.sleep(2.5)
        except Exception as e:
            print(f"  [{i+1}/{len(seminaries)}] ❌ {name[:45]:45s} -> {email} | {e}")
    
    save_checkpoint({"sent": list(sent_ids)})
    print(f"\nDone! Sent: {sent_count}")

if __name__ == '__main__':
    main()
