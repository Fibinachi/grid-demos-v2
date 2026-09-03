"""
Priority Foundation Sender
==========================
Sends personalized emails to curated priority list using the new
research-focused messaging (Theology of Risk Management).

Usage: python priority_sender.py [--dry-run]
"""
import csv, os, sys, time, random, json, argparse, base64
from datetime import datetime
from email.message import EmailMessage

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from gmail_api_sender import GMAIL_USER, authenticate_gmail

INPUT_CSV = os.path.join(SCRIPT_DIR, "foundations_priority_send.csv")
SENT_LOG = os.path.join(SCRIPT_DIR, "priority_sent_log.txt")
SLEEP_BETWEEN = 180  # 3 minutes between sends

# ── Research-focused intro hooks ─────────────────────────────────────────

RESEARCH_INTRO = """My research proposes a novel interdisciplinary framework — the "Theology of Risk Management" — analyzing how religious institutions navigate the tension between theological mandates (confession, restorative justice, pastoral care) and corporate imperatives (liability avoidance, fiduciary solvency, risk mitigation).

This question emerged from my 15 years practicing tax law, during which I formed more than twenty religious organizations as an attorney. I witnessed first-hand how institutional defense mechanisms can displace theological accountability — a phenomenon I term the "Accountability Displacement Gap."

I am now pursuing this research at the Toronto School of Theology, through Trinity College, because Canada's Truth and Reconciliation Commission process provides an unparalleled dataset for examining how religious organizations respond when their legal obligations conflict with their theological commitments. No other institution in North America offers this intersection of legal analysis, theological ethics, and empirical data on institutional crisis."""

# Shorter version for funders with smaller attention budgets
RESEARCH_SHORT = """My research proposes a "Theology of Risk Management" — examining how religious institutions balance theological obligations (confession, restorative justice) against legal liability (risk mitigation, fiduciary duty). I am pursuing this at Trinity College, University of Toronto, drawing on Canada's Truth and Reconciliation Commission data as a case study in institutional crisis and accountability."""

# ── Personalized hooks by category ───────────────────────────────────────
CATEGORY_HOOKS = {
    'Theology Foundation': RESEARCH_INTRO,
    'Research-Aligned Foundation': RESEARCH_SHORT,
    'National Anglican Funding Body': f"""As a student at Trinity College — an institution founded in the Anglican heritage — my research examines how religious institutions navigate moments when their legal obligations conflict with their theological commitments. The Anglican Church of Canada's participation in the Truth and Reconciliation Commission process provides an important case study for this work.""",
    'Small Family Foundation': f"""After 15 years as a tax attorney — where I formed more than twenty religious organizations — I found myself asking questions the law couldn't answer: what does accountability mean when institutions fail? I'm now pursuing this research at Trinity College, University of Toronto.""",
}

# ── Body template ────────────────────────────────────────────────────────
BODY = """
My background includes a JD from Rutgers Law, an LLM in Taxation, and extensive experience in nonprofit formation and legal practice. This interdisciplinary foundation — combining legal analysis with theological inquiry and game theory modeling — provides a unique lens for examining how institutional decision-making shapes organizational ethics.

I am beginning graduate study in Fall 2026 and am seeking to identify foundations whose mission aligns with research at the intersection of law, theology, and institutional ethics.

If your foundation considers requests from individual scholars or supports research-oriented initiatives, I would be grateful for any guidance on eligibility, application procedures, or upcoming opportunities. I am happy to provide my full research proposal, CV, or any additional information.

Thank you for your time and for the important work your foundation does.

With gratitude,
Charles Prescott
JD, LLM
Certificate in Theological Studies (Fall 2026)
Trinity College, University of Toronto
charles@columbiataxlawyer.com
843-504-4542
"""

def build_email(row):
    """Build a personalized email for one foundation."""
    name = row['NAME'].strip()
    category = row.get('CATEGORY', '').strip()
    reason = row.get('REASON', '').strip()
    
    # Select intro hook
    hook = CATEGORY_HOOKS.get(category, RESEARCH_SHORT)
    
    # Build subject
    subject = "Research Inquiry: Theology of Risk Management — Institutional Ethics & Accountability"
    
    # Build body
    body = f"""Dear {name} team,

{hook}
{BODY}"""
    
    return subject, body

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true', help='Preview without sending')
    args = parser.parse_args()
    
    # Load priority list
    with open(INPUT_CSV) as f:
        rows = [r for r in csv.DictReader(f) if r['STATUS'] == 'NEW']
    
    print(f"📂 Loaded {len(rows)} new, never-contacted foundations")
    
    if args.dry_run:
        print(f"\n{'='*70}")
        print(f"  DRY RUN — Previewing first 3 emails")
        print(f"{'='*70}")
        for row in rows[:3]:
            subject, body = build_email(row)
            print(f"\n{'─'*70}")
            print(f"To: {row['NAME']} <{row['EMAIL']}>")
            print(f"Subj: {subject}")
            print(f"{'─'*70}")
            print(body[:600])
            print(f"{'─'*70}")
            input("\nPress Enter to continue...")
        return
    
    # Authenticate
    print("\n🔑 Authenticating with Gmail API...")
    service = authenticate_gmail()
    print("✅ Authenticated!")
    
    # Load sent log
    sent = set()
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG) as f:
            sent = {l.strip().split(',')[0] for l in f if l.strip()}
    
    # Send
    sent_count = 0
    start = datetime.now()
    
    for i, row in enumerate(rows):
        email_addr = row['EMAIL'].strip().lower()
        name = row['NAME'].strip()
        
        if email_addr in sent:
            print(f"  [{i+1}/{len(rows)}] ⏭️ Already sent: {name}")
            continue
        
        subject, body = build_email(row)
        
        # Send
        msg = EmailMessage()
        msg['To'] = email_addr
        msg['From'] = 'Charles Prescott <charlesaprescottjr@gmail.com>'
        msg['Subject'] = subject
        msg.set_content(body)
        
        try:
            if not args.dry_run:
                raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                service.users().messages().send(
                    userId=GMAIL_USER, body={'raw': raw}
                ).execute()
                
                with open(SENT_LOG, 'a') as f:
                    f.write(f"{email_addr},{name},{subject},{datetime.now().isoformat()}\n")
                
                sent_count += 1
                elapsed = (datetime.now() - start).total_seconds()
                rate = sent_count / elapsed * 3600 if elapsed > 0 else 0
                
                print(f"  [{i+1}/{len(rows)}] ✅ Sent ({sent_count} total, {rate:.0f}/hr): {name[:40]}")
                
                # Sleep between sends
                if i < len(rows) - 1:
                    delay = SLEEP_BETWEEN + random.uniform(-30, 30)
                    print(f"     Sleeping {delay:.0f}s...")
                    time.sleep(delay)
                    
        except Exception as e:
            print(f"  [{i+1}/{len(rows)}] ❌ Error: {e}")
    
    print(f"\n{'='*70}")
    print(f"  DONE: {sent_count} emails sent")
    print(f"  Time: {datetime.now() - start}")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()
