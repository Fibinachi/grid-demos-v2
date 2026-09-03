#!/usr/bin/env python3
"""
GrantWizard — Direct-to-Pastor Demographic Report Pipeline
Sends pastors a personalized ZIP-level demographic report as a sample,
then offers to provide deeper tract-level analysis with more data points.

Usage:
  .venv\Scripts\python scripts/outreach/pastor_demo_pipeline.py --limit 5
  .venv\Scripts\python scripts/outreach/pastor_demo_pipeline.py --dry-run --limit 20
  .venv\Scripts\python scripts/outreach/pastor_demo_pipeline.py --resume
"""
import os, sys, base64, json, time, sqlite3, argparse
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
CHECKPOINT_FILE = os.path.join(SCRIPT_DIR, "pastor_demo_checkpoint.json")

SENDER_EMAIL = "charlesaprescottjr@gmail.com"

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


def get_qualified_churches(limit=0, offset=0):
    """Get churches with email + ZIP data, ordered by poverty rate desc."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    query = """
        SELECT c.id, c.name, c.city, c.state, c.zip, c.email, c.pastor_name, c.denomination, c.family,
               cz.poverty_rate, cz.median_hh_income, cz.total_pop,
               cz.median_home_value, cz.median_age,
               cz.pct_bachelors, cz.unemployed_pct,
               c.food_desert_low_inc_low_access_1_10,
               c.food_desert_poverty_rate,
               c.latitude, c.longitude
        FROM churches c
        JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022
        WHERE NULLIF(c.email, '') IS NOT NULL
          AND cz.median_hh_income BETWEEN 10000 AND 250000
          AND COALESCE(NULLIF(c.family, ''), c.denomination, 'Unknown') NOT IN ('Catholic Churches')
        ORDER BY cz.poverty_rate DESC
    """
    if limit > 0:
        query += f" LIMIT {limit} OFFSET {offset}"
    
    c.execute(query)
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


import html as html_mod

def clean_name(raw):
    """Clean a church name: decode HTML entities, strip junk."""
    if not raw:
        return ''
    name = html_mod.unescape(raw)  # &#8217; -> '
    name = name.strip().rstrip(',')
    return name

def is_valid_email(email):
    """Check if email is actually deliverable (single address)."""
    if not email or '@' not in email:
        return False
    if ' ' in email.strip():
        return False  # Two emails mashed together
    if email.strip().lower() in ('needs address', 'none', 'n/a', ''):
        return False
    return True

def is_junk_name(name):
    """Check if a church name is too junky to use."""
    if not name or len(name.strip()) < 3:
        return True
    return False

def build_email(church):
    """Build a personalized demographic report email for a pastor/church."""
    
    name = clean_name(church.get('name', 'this church'))
    city = church.get('city', '')
    state = church.get('state', '')
    zip5 = church.get('zip', '')
    email = church.get('email', '')
    pastor = church.get('pastor_name', '')
    
    pov = church.get('poverty_rate', 0)
    inc = church.get('median_hh_income', 0)
    pop = church.get('total_pop', 0)
    home_val = church.get('median_home_value', 0)
    med_age = church.get('median_age', 0)
    bach_pct = church.get('pct_bachelors', 0)
    unemp = church.get('unemployed_pct', 0)
    fd = church.get('food_desert_low_inc_low_access_1_10') or 0
    fd_pov_raw = church.get('food_desert_poverty_rate')
    fd_pov = float(fd_pov_raw) if fd_pov_raw and fd_pov_raw != 'None' else None
    
    family = (church.get('family', '') or '').lower()
    denom = (church.get('denomination', '') or '').lower()
    combined = f"{family} {denom}"
    
    # Determine message angle based on denomination
    if 'orthodox' in combined and 'union' in combined:
        angle = 'community_service'
    elif any(w in combined for w in ['presbyterian', 'reformed', 'methodist', 'episcopal', 'lutheran', 'anglican', 'congregational', 'brethren', 'mennonite', 'quaker']):
        angle = 'social_ministry'
    elif any(w in combined for w in ['baptist', 'pentecostal', 'evangelical', 'non-denominational', 'church of god', 'church of christ', 'assembly of god', 'nazarene', 'holiness', 'adventist', 'missionary']):
        angle = 'church_growth'
    else:
        angle = 'church_growth'
    
    greeting = f"Hi {pastor.title()}," if pastor and pastor.strip().upper() not in ('Pastor', 'PASTOR', '') else f"Hi there,"
    
    # Build readable location
    location = f"{city}, {state} {zip5}" if city else f"ZIP code {zip5}"
    
    # Format numbers
    inc_str = f"${inc:,.0f}" if inc else "N/A"
    pop_str = f"{int(pop):,}" if pop else "N/A"
    home_str = f"${int(home_val):,}" if home_val else "N/A"
    pov_str = f"{pov:.1f}%" if pov else "N/A"
    bach_str = f"{bach_pct:.1f}%" if bach_pct else "N/A"
    unemp_str = f"{unemp:.1f}%" if unemp else "N/A"
    
    # Food desert note
    fd_note = ""
    if fd == 1:
        fd_note = f"\n  • This area is also classified as a low-income, low-access food desert (tract-level poverty rate: {fd_pov:.1f}%)."
    
    if angle == 'community_service':
        body = f"""{greeting}

I'm building a national database that cross-references community organizations against demographic and economic data. I thought you might find this snapshot of {name}'s area useful — it shows the needs your community service work already addresses:

  Population:                {pop_str}
  Poverty rate:              {pov_str}
  Median household income:   {inc_str}
  Median home value:         {home_str}
  Median age:                {med_age}
  Bachelor's degree or more: {bach_str}
  Unemployment rate:         {unemp_str}{fd_note}

This kind of data is useful for grant applications, program planning, and demonstrating community need. I can drill down much further — census tract level, food access, school performance, SNAP participation, senior population, you name it.

If a deeper profile of your area would be helpful, just reply. No charge, and I won't follow up if you're not interested.

Best,
Charles Prescott"""
        subj = f"Community needs at a glance — {name[:34]} ({pov:.0f}% poverty)"
    elif angle == 'social_ministry':
        body = f"""{greeting}

I'm building a national church database that cross-references congregations against demographic and economic data — designed to help church leaders understand their communities for social ministry and community impact. I thought you might find this snapshot of {name}'s area useful:

  Population:                {pop_str}
  Poverty rate:              {pov_str}
  Median household income:   {inc_str}
  Median home value:         {home_str}
  Median age:                {med_age}
  Bachelor's degree or more: {bach_str}
  Unemployment rate:         {unemp_str}{fd_note}

This tells you who lives in your neighborhood — where the needs are, what resources are available, and where your congregation's ministry could make the biggest difference. I can drill down much further: census tract level, food access, school performance, senior population, broadband access, FEMA flood risk, religious adherence rates.

If you'd like a deeper profile of your area — for a grant application, a needs assessment, or strategic planning — just reply. No charge, and I won't follow up if you're not interested.

Best,
Charles Prescott"""
        subj = f"Your community at a glance — {name[:38]} ({pov:.0f}% poverty)"
    else:  # church_growth
        body = f"""{greeting}

I'm building a national church database that cross-references congregations against demographic and economic data — designed to help church leaders understand their communities better for outreach, growth, and strategic planning. I thought you might find this snapshot of {name}'s area useful:

  Population:                {pop_str}
  Poverty rate:              {pov_str}
  Median household income:   {inc_str}
  Median home value:         {home_str}
  Median age:                {med_age}
  Bachelor's degree or more: {bach_str}
  Unemployment rate:         {unemp_str}{fd_note}

This tells you something about who lives in your neighborhood — age ranges, income levels, education — the kind of information that shapes how you communicate, what programs you offer, and where your church can make the biggest impact.

I can drill down much further: census tract level (hyper-local), food access, school performance, broadband availability, religious adherence rates, even FEMA flood risk. Whatever would be most useful for understanding your community and reaching it effectively.

If you'd like a deeper profile of your area, just reply. No charge, and I won't follow up if you're not interested.

Best,
Charles Prescott"""
        subj = f"Your community at a glance — {name[:38]} ({pov:.0f}% poverty)"
    
    return body, subj


def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {"sent": [], "offset": 0, "last_run": None}


def save_checkpoint(data):
    data["last_run"] = datetime.now().isoformat()
    with open(CHECKPOINT_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Max emails to send")
    parser.add_argument("--dry-run", action="store_true", help="Preview only, don't send")
    parser.add_argument("--start-from", type=int, default=0, help="Skip first N churches")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    args = parser.parse_args()
    
    print("GrantWizard — Pastor Demographic Report Pipeline")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    
    offset = args.start_from
    sent_ids = set()
    
    if args.resume:
        cp = load_checkpoint()
        sent_ids = set(cp.get("sent", []))
        offset = cp.get("offset", 0)
        print(f"Resuming from checkpoint: {len(sent_ids)} already sent, offset={offset}")
    
    churches = get_qualified_churches(limit=args.limit, offset=offset)
    print(f"Loaded {len(churches)} churches starting at offset {offset}")
    
    if not churches:
        print("Nothing to do!")
        return
    
    service = get_gmail_service() if not args.dry_run else None
    
    sent_count = 0
    skipped = 0
    
    for i, church in enumerate(churches):
        ch_id = church['id']
        email = church['email']
        name = clean_name(church.get('name', ''))
        church['name'] = name  # Use cleaned name
        
        if ch_id in sent_ids:
            skipped += 1
            continue
        
        if not is_valid_email(email):
            skipped += 1
            continue
        
        if is_junk_name(name):
            skipped += 1
            continue
            
        body, subject = build_email(church)
        
        location = f"{church.get('city', '')} {church.get('state', '')}"
        pov = church.get('poverty_rate', 0)
        
        if args.dry_run:
            print(f"\n--- [{i+1}/{len(churches)}] {name[:50]:50s} | {location:20s} | {email:35s} | Pov:{pov:.1f}%")
            print(f"  Subject: {subject[:90]}")
            print(f"  Preview: {body[:200]}...")
            continue
        
        # Send
        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg['To'] = email
            msg['From'] = SENDER_EMAIL
            msg['Subject'] = subject
            
            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            response = service.users().messages().send(
                userId='me', body={'raw': raw}
            ).execute()
            
            print(f"  [{i+1}/{len(churches)}] ✅ {name[:40]:40s} -> {email:35s} (msg: {response.get('id')})")
            sent_count += 1
            sent_ids.add(ch_id)
            
            # Save checkpoint every 5 sends
            if sent_count % 5 == 0:
                save_checkpoint({"sent": list(sent_ids), "offset": offset + i + 1})
            
            time.sleep(2.5)  # Gmail rate limit
            
        except Exception as e:
            print(f"  [{i+1}/{len(churches)}] ❌ {name[:40]:40s} -> {email:35s} | ERROR: {e}")
    
    if not args.dry_run:
        final_offset = offset + len(churches)
        save_checkpoint({"sent": list(sent_ids), "offset": final_offset})
    
    print(f"\nDone! Sent: {sent_count}, Skipped: {skipped}, Checkpoint offset: {offset + len(churches)}")


if __name__ == '__main__':
    main()
