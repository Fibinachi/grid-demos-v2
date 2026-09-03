"""
HUMANITARIAN SENDER — Disaster preparedness mapping for aid distribution.
Pitch: GRID maps 3.5M worship sites globally as pre-positioned community
hubs — instant shelter/distribution network map before the hurricane hits.

Key data points for humanitarian orgs:
  - 3.5M worship sites with GPS across 291 countries
  - FEMA 18-hazard risk scores joined to 980K US churches
  - 463K contacts (phone/email/website) for community leader reach
  - Denominational hierarchies — know who controls which buildings
  - 100% faith-classified via FTLM taxonomy (1,066 traditions)
  - Global coverage: US 1M | IN 226K | BR 205K | ID 152K | plus 287 more

Runs via build_unified_queue.py — add to queue, unified sender picks up.
Or standalone for priority Tier 1+2 targets.
"""
import json, smtplib, time, os, sys
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime

SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
FROM = "Charles Prescott <charlesaprescottjr@gmail.com>"
PWD = os.environ.get("GMAIL_APP_PASSWORD")
if not PWD:
    print("Set GMAIL_APP_PASSWORD"); sys.exit(1)

INTERVAL = 180  # 3 min between sends (Gmail free tier)
OUT = Path("outputs/outreach")
SENT_LOG = OUT / "gmail_sent.txt"
FAIL_LOG = OUT / "gmail_failed.txt"

SIG = """Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542"""

ADX = "https://us-east-1.console.aws.amazon.com/dataexchange/home?region=us-east-1#/data-sets/993cef8f87cacadaee6e20e52d939084"
BQ = "https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure"

# ── Load leads ──
LEADS = json.load(open(OUT / "humanitarian_leads.json"))

# ── Load already sent ──
already = set()
for f in [SENT_LOG, OUT/"whale_sent.txt", OUT/"church_campaign_sent.txt",
          OUT/"jewish_sent.txt", OUT/"academic_sent.txt"]:
    if f.exists():
        for line in f.read_text().strip().split('\n'):
            if line.strip():
                already.add(line.strip().lower().split('|')[0].strip())

# ── Filter unsent ──
pending = [l for l in LEADS if l['email'].lower() not in already]
print(f"Humanitarian targets: {len(pending)} new (of {len(LEADS)} total)")
from collections import Counter
for t, n in Counter(l['tier'] for l in pending).most_common():
    print(f"  Tier {t}: {n}")

# ── Attach map if exists ──
MAP_PATH = OUT / "map_us_disaster_risk.png"
MAP_CID = "disaster_risk_map"

def build_message(lead):
    """Build email body with tier-appropriate pitch."""
    tier = lead['tier']
    sector = lead['sector']
    org = lead['org']

    # ── Common data summary ──
    data_block = """GRID DATA SNAPSHOT:
• 3,481,509 worship sites across 291 countries — GPS-coordinated
• 1,073,812 US churches with FEMA 18-hazard risk scores
• 463,362 contact points (phone/email/website) for community leader reach
• 100% faith-classified: Christian 2.58M | Islam 361K | Hindu 202K | Buddhist 199K | Jewish 27K | Sikh 7K | plus 6 more
• 163K denominational hierarchy relationships — know who controls each building
• County-level demographics (ACS) joined to every US church
• Free Vermont sample on AWS Data Exchange (500 churches + FEMA scores)
"""

    # ── Tier-specific pitches ──
    if tier == 1:  # UN/Govt coordination
        body = f"""Dear {org},

When a hurricane makes landfall or an earthquake strikes, the first question is always: where can we set up aid distribution? Where are the community hubs? Who are the trusted local leaders?

GRID (Global Religious Infrastructure Database) answers these questions before the disaster hits.

GRID maps 3,481,509 churches, mosques, temples, synagogues, and gurdwaras across 291 countries — each with GPS coordinates, contact information, and denominational hierarchy. These buildings are the world's largest pre-positioned network of community infrastructure: roofs, kitchens, parking lots, sound systems, and trusted local leadership.

{data_block}
For {sector} operations, GRID offers:

PREDISASTER PLANNING:
- Map every potential shelter, distribution point, and community hub before the crisis
- Join FEMA National Risk Index scores (18 hazard types) to identify vulnerable community assets
- Pre-identify faith leaders with phone/email for emergency communication trees

REAL-TIME RESPONSE:
- Within minutes of a disaster: generate maps of all worship sites in the affected area
- Filter by facility type (large churches/mosques have kitchens + parking for supply staging)
- Contact community leaders directly (463K phone/email records)

POST-DISASTER RECOVERY:
- Track facility damage against pre-disaster baseline
- Identify community hubs for cash aid distribution
- Map resumption of services as a recovery indicator

The Vermont sample (free) on AWS Data Exchange shows the full schema:
{ADX}

BigQuery demo views available:
{BQ}

Would your GIS/information management team be interested in a briefing on how GRID can integrate with your existing humanitarian data platforms (HDX, IFRC GO, etc.)?

{SIG}"""

    elif tier == 2:  # Major INGOs
        body = f"""Dear {org},

In every disaster zone, one pattern holds: religious buildings become shelters, supply depots, and coordination centers — whether anyone planned it or not. GRID lets you plan it.

GRID (Global Religious Infrastructure Database) maps 3.5 million worship sites worldwide, so your field teams can know — before they deploy — where every potential distribution point, community kitchen, and shelter is located.

{data_block}
For {org} field operations, GRID enables:

BEFORE DEPLOYMENT:
- Pre-map all worship sites in your operating areas
- Identify the largest facilities (capacity for supply staging)
- Know which denomination controls each building (Catholic diocese, SBC association, Islamic foundation)
- Assess FEMA risk scores for facilities in hurricane/earthquake zones

DURING RESPONSE:
- Instant CSV export of all worship sites within a disaster radius
- Contact community leaders directly (463K phone/email records)
- Share maps with field teams via BigQuery or flat files

AFTER ACTION:
- Facility damage assessment against baseline inventory
- Recovery tracking: when does the mosque/church reopen?
- Community network mapping for long-term resilience programs

Free Vermont sample (500 churches + FEMA 18-hazard scores):
{ADX}

I'd be happy to generate a custom preview for your priority operating countries.

Would your emergency response or GIS team be interested in a 15-minute walkthrough?

{SIG}"""

    elif tier in (3, 4):  # Specialized + faith-based
        faith_note = ""
        if sector == "Faith-Based Relief":
            if "Islamic" in org:
                faith_note = "GRID has 361K mosques classified across 17 Muslim traditions (Sunni/Shia/Ibadi etc.) — your mosque network, already mapped."
            elif "Catholic" in org or "Caritas" in org:
                faith_note = "GRID has 33K Catholic parishes in a full diocese→parish hierarchy — your distribution network, already mapped."
            elif "Lutheran" in org:
                faith_note = "GRID has 57K Lutheran churches in ELCA/LCMS/WELS hierarchy — your network, already mapped."
            elif "Adventist" in org or "ADRA" in org:
                faith_note = "GRID has SDA churches classified by conference — your network, ready for mapping."

        body = f"""Dear {org},

Religious buildings are the world's most underutilized humanitarian infrastructure. When disaster strikes, communities already gather there. GRID makes that network visible and actionable.

GRID (Global Religious Infrastructure Database) maps 3,481,509 worship sites across 291 countries — each GPS-tagged, faith-classified, and contact-enriched.

{faith_note}

{data_block}
For {org} operations:

IMMEDIATE USE:
- Map all worship sites in your target communities before deployment
- Identify facilities with kitchens, parking, and capacity for supply distribution
- Contact faith leaders directly (463K numbers/emails)
- Share maps with field teams instantly (CSV/GeoJSON/BigQuery)

LONG-TERM RESILIENCE:
- Track facility status as a community recovery indicator
- Build communication networks through existing religious leadership structures
- Join FEMA risk scores to prioritize vulnerable community assets

I'd love to generate a custom preview of GRID data for your priority operating area — just let me know which countries or regions.

Free Vermont sample:
{ADX}

Would your programs team be interested in a brief walkthrough?

{SIG}"""

    else:  # Tier 5 — Research / Platforms
        body = f"""Dear {org},

GRID (Global Religious Infrastructure Database) is the first complete dataset on global religious infrastructure — and it's directly relevant to humanitarian data analysis.

3,481,509 worship sites. 291 countries. GPS coordinates. 463K contacts. FEMA 18-hazard risk scores on every US church. All 100% faith-classified under the FTLM taxonomy (1,066 traditions).

{data_block}
For {org}'s work, GRID provides a new analytical dimension:

- Community asset mapping: Where are the gathering points in any crisis zone?
- Vulnerability analysis: Which religious communities face the highest natural hazard exposure?
- Network resilience: How do denominational hierarchies map to aid distribution channels?
- Recovery indicators: When do worship services resume after a disaster?

GRID is available for humanitarian research at no cost for non-commercial use. The Vermont sample (free) on AWS shows the full schema:
{ADX}

Would this be useful for your humanitarian data analysis work?

{SIG}"""

    return body


def send(to, subj, body, map_path=None):
    """Send email with optional map attachment."""
    msg = MIMEMultipart()
    msg["From"] = FROM
    msg["To"] = to
    msg["Reply-To"] = "charlesaprescott@outlook.com"
    msg["Subject"] = subj
    msg.attach(MIMEText(body, "plain"))

    if map_path and Path(map_path).exists():
        with open(map_path, "rb") as f:
            img = MIMEImage(f.read())
            img.add_header("Content-ID", f"<{MAP_CID}>")
            img.add_header("Content-Disposition", "inline", filename="GRID_Disaster_Risk_Map.png")
            msg.attach(img)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.starttls()
        s.login("charlesaprescottjr@gmail.com", PWD)
        s.send_message(msg)


# ============================================================
# MAIN: SEND LOOP
# ============================================================
if __name__ == "__main__":
    if not pending:
        print("All leads already sent. Nothing to do.")
        sys.exit(0)

    # Show what we're about to send
    print(f"\n=== READY TO SEND {len(pending)} EMAILS ===\n")
    for l in sorted(pending, key=lambda x: (x['tier'], x['org'])):
        print(f"  T{l['tier']} | {l['sector'][:22]:<22s} | {l['org'][:50]:<50s} -> {l['email']}")
    print()

    input("Press Enter to start sending (Ctrl+C to abort)... ")

    ok = fail = 0
    for i, lead in enumerate(pending):
        org = lead['org']
        email = lead['email']
        tier = lead['tier']
        sector = lead['sector']

        subject = f"GRID: Pre-Disaster Community Infrastructure Mapping for Humanitarian Response"
        if tier == 1:
            subject = f"GRID: 3.5M Worship Sites Mapped — Pre-Positioned Community Hubs for {org}"
        elif tier <= 3:
            subject = f"GRID: Instant Shelter/Distribution Network Map — Before the Next Disaster"

        body = build_message(lead)

        print(f"\n[{i+1}/{len(pending)}] T{tier} {org} -> {email}")

        try:
            send(email, subject, body, MAP_PATH)
            print(f"  ✅ SENT")
            with open(SENT_LOG, "a") as f:
                f.write(f"{email}|{org}|{datetime.now().isoformat()}\n")
            ok += 1
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            with open(FAIL_LOG, "a") as f:
                f.write(f"{email}|{org}|{e}|{datetime.now().isoformat()}\n")
            fail += 1

        if i < len(pending) - 1:
            print(f"  ⏳ Waiting {INTERVAL}s...")
            time.sleep(INTERVAL)

    print(f"\n=== DONE ===\n✅ {ok} sent\n❌ {fail} failed")
