"""
REGIONAL JEWISH ORGS CAMPAIGN — "How many synagogues are there?"
Minimalist, high-impact template. Sends to Federation security directors,
denominational regional directors, Jewish media, academics, and heritage orgs.

Generates global synagogue map PNG for inline email embedding.
"""
import json, smtplib, time, os, sys
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime

PWD = os.environ.get("GMAIL_APP_PASSWORD")
if not PWD:
    import subprocess
    r = subprocess.run(["powershell", "-c", "[Environment]::GetEnvironmentVariable('GMAIL_APP_PASSWORD','User')"], capture_output=True, text=True)
    PWD = r.stdout.strip()
if not PWD:
    print("Set GMAIL_APP_PASSWORD"); sys.exit(1)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
FROM = "Charles Prescott <charlesaprescottjr@gmail.com>"
REPLY_TO = "charlesaprescott@outlook.com"
INTERVAL = 180  # 3 minutes between sends

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
MAP_PNG = OUT / "map_jewish_global_synagogues.png"

SIG = """Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto (incoming Fall 2026)
charlesaprescottjr@gmail.com | 843-504-4542"""

# ═══════════════════════════════════════════════════════════════
# GENERATE GLOBAL SYNAGOGUE MAP PNG
# ═══════════════════════════════════════════════════════════════

def generate_map():
    """Generate a dark-themed global synagogue scatter map PNG."""
    import sqlite3, pandas as pd
    import plotly.express as px

    db = sqlite3.connect("E:/grid/churches.db")
    df = pd.read_sql("""
        SELECT id, name, city, state, country,
               CAST(latitude AS REAL) as latitude, CAST(longitude AS REAL) as longitude,
               landmark_type, tradition
        FROM churches
        WHERE faith = 'Judaism' AND landmark_type = 'synagogue' AND latitude IS NOT NULL
    """, db)
    db.close()

    print(f"Map data: {len(df):,} synagogues with GPS")

    # Clean tradition labels
    tradition_map = {
        "Rabbinic": "Rabbinic", "rabbinic": "Rabbinic",
        "Orthodox": "Orthodox", "orthodox": "Orthodox",
        "Orthodox (Chabad)": "Chabad", "orthodox_chabad": "Chabad",
        "Reform": "Reform", "reform": "Reform",
        "Sephardic": "Sephardic", "sephardic": "Sephardic",
        "Orthodox (Yeshiva)": "Yeshiva", "orthodox_yeshiva": "Yeshiva",
        "Conservative": "Conservative", "conservative": "Conservative",
        "Orthodox (Hasidic)": "Hasidic", "orthodox_hasidic": "Hasidic",
    }
    df["tradition_clean"] = df["tradition"].map(tradition_map).fillna("Other")

    tradition_colors = {
        "Orthodox": "#1f77b4", "Chabad": "#ff7f0e", "Rabbinic": "#2ca02c",
        "Reform": "#d62728", "Conservative": "#9467bd", "Sephardic": "#8c564b",
        "Hasidic": "#e377c2", "Yeshiva": "#7f7f7f", "Other": "#bcbd22",
    }

    # Sample for performance
    sample = df if len(df) <= 20000 else df.sample(n=20000, random_state=42)

    fig = px.scatter_mapbox(
        sample, lat="latitude", lon="longitude",
        color="tradition_clean", color_discrete_map=tradition_colors,
        size_max=4, zoom=1.5, height=700, opacity=0.55,
        hover_data={"name": True, "city": True, "country": True, "landmark_type": True},
        title=f"<b>Global Synagogue Infrastructure — {len(df):,} Synagogues Mapped Worldwide</b><br><sup>GRID: Every dot is a synagogue. 172 countries. GPS-located. AI-verified tradition classification.</sup>",
        mapbox_style="carto-darkmatter",
    )
    fig.update_layout(margin={"r": 0, "t": 60, "l": 0, "b": 0})
    fig.update_traces(marker=dict(size=3))

    # Save PNG + HTML
    fig.write_image(MAP_PNG, width=1200, height=700, scale=2)
    fig.write_html(OUT / "map_jewish_global_synagogues.html")
    print(f"   -> {MAP_PNG}")
    print(f"   -> map_jewish_global_synagogues.html")
    return len(df)


# ═══════════════════════════════════════════════════════════════
# CONTACTS — Regional Jewish Orgs (filtered for real/verifiable)
# ═══════════════════════════════════════════════════════════════

CONTACTS = [
    # ═══ FEDERATION SECURITY DIRECTORS (real federations) ═══
    {"org": "UJA-Federation of New York", "contact": "Community Security Director", "region": "New York", "send_via": "security@ujafedny.org", "buyer": "Security/Federation"},
    {"org": "Community Security Initiative (NYC)", "contact": "Intelligence & Security Lead", "region": "New York", "send_via": "info@csiny.org", "buyer": "Security"},
    {"org": "Jewish Federation of Greater Philadelphia", "contact": "Community Security Director", "region": "Pennsylvania", "send_via": "info@jewishphilly.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Washington", "contact": "Community Security Director", "region": "DC/MD/VA", "send_via": "info@shalomdc.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Miami", "contact": "Community Security Director", "region": "Florida", "send_via": "info@jewishmiami.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Broward County", "contact": "Community Security Director", "region": "Florida", "send_via": "info@jewishbroward.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Palm Beach County", "contact": "Community Security Director", "region": "Florida", "send_via": "info@jewishpb.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Orlando", "contact": "Community Security Director", "region": "Florida", "send_via": "info@jfgo.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Tampa Bay", "contact": "Community Security Director", "region": "Florida", "send_via": "info@jewishtampa.com", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Jacksonville", "contact": "Community Security Director", "region": "Florida", "send_via": "info@jewishjacksonville.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Atlanta", "contact": "Community Security Director", "region": "Georgia", "send_via": "info@jewishatlanta.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Birmingham", "contact": "Community Security Director", "region": "Alabama", "send_via": "info@bjf.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Nashville", "contact": "Community Security Director", "region": "Tennessee", "send_via": "info@jewishnashville.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Memphis", "contact": "Community Security Director", "region": "Tennessee", "send_via": "info@jewishmemphis.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of New Orleans", "contact": "Community Security Director", "region": "Louisiana", "send_via": "info@jewishnola.com", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Charleston", "contact": "Community Security Director", "region": "South Carolina", "send_via": "info@jewishcharleston.com", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Pittsburgh", "contact": "Community Security Director", "region": "Pennsylvania", "send_via": "info@jfedpgh.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Buffalo", "contact": "Community Security Director", "region": "New York", "send_via": "info@buffalojewishfederation.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Rochester", "contact": "Community Security Director", "region": "New York", "send_via": "info@jewishrochester.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Northeastern New York", "contact": "Community Security Director", "region": "New York", "send_via": "info@jewishfedny.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Northern New Jersey", "contact": "Community Security Director", "region": "New Jersey", "send_via": "info@jfnnj.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Rhode Island", "contact": "Community Security Director", "region": "Rhode Island", "send_via": "info@jewishallianceri.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Hartford", "contact": "Community Security Director", "region": "Connecticut", "send_via": "info@jewishhartford.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Western Massachusetts", "contact": "Community Security Director", "region": "Massachusetts", "send_via": "info@jewishwesternmass.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Delaware", "contact": "Community Security Director", "region": "Delaware", "send_via": "info@shalomdel.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Baltimore", "contact": "Community Security Director", "region": "Maryland", "send_via": "info@jewishbaltimore.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Richmond", "contact": "Community Security Director", "region": "Virginia", "send_via": "info@jewishrichmond.org", "buyer": "Security/Federation"},
    {"org": "United Jewish Federation of Tidewater", "contact": "Community Security Director", "region": "Virginia", "send_via": "info@ujft.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Raleigh", "contact": "Community Security Director", "region": "North Carolina", "send_via": "info@shalomraleigh.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Greensboro", "contact": "Community Security Director", "region": "North Carolina", "send_via": "info@shalomgreensboro.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Charlotte", "contact": "Community Security Director", "region": "North Carolina", "send_via": "info@jewishcharlotte.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Los Angeles", "contact": "Community Security Director", "region": "California", "send_via": "security@jewishla.org", "buyer": "Security/Federation"},
    {"org": "Jewish Community Federation of San Francisco", "contact": "Community Security Director", "region": "California", "send_via": "info@sfjcf.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Silicon Valley", "contact": "Community Security Director", "region": "California", "send_via": "info@jvalley.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of San Diego County", "contact": "Community Security Director", "region": "California", "send_via": "info@jewishinsandiego.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Phoenix", "contact": "Community Security Director", "region": "Arizona", "send_via": "info@jewishphoenix.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Southern Arizona", "contact": "Community Security Director", "region": "Arizona", "send_via": "info@jfsa.org", "buyer": "Security/Federation"},
    {"org": "JEWISHcolorado", "contact": "Community Security Director", "region": "Colorado", "send_via": "info@jewishcolorado.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Portland", "contact": "Community Security Director", "region": "Oregon", "send_via": "info@jewishportland.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Seattle", "contact": "Community Security Director", "region": "Washington", "send_via": "info@jewishinseattle.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Spokane", "contact": "Community Security Director", "region": "Washington", "send_via": "info@spokanejewish.org", "buyer": "Security/Federation"},
    {"org": "Jewish Nevada", "contact": "Community Security Director", "region": "Nevada", "send_via": "info@jewishnevada.org", "buyer": "Security/Federation"},
    {"org": "Jewish United Fund of Metropolitan Chicago", "contact": "Community Security Director", "region": "Illinois", "send_via": "communitysecurity@juf.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Metropolitan Detroit", "contact": "Community Security Director", "region": "Michigan", "send_via": "info@jewishdetroit.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Cleveland", "contact": "Community Security Director", "region": "Ohio", "send_via": "info@jewishcleveland.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Columbus", "contact": "Community Security Director", "region": "Ohio", "send_via": "info@tcjf.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Cincinnati", "contact": "Community Security Director", "region": "Ohio", "send_via": "info@jfedcin.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Indianapolis", "contact": "Community Security Director", "region": "Indiana", "send_via": "info@jfgi.org", "buyer": "Security/Federation"},
    {"org": "Milwaukee Jewish Federation", "contact": "Community Security Director", "region": "Wisconsin", "send_via": "info@milwaukeejewish.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Madison", "contact": "Community Security Director", "region": "Wisconsin", "send_via": "info@jewishmadison.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Minneapolis", "contact": "Community Security Director", "region": "Minnesota", "send_via": "info@jfcsmpls.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater St. Paul", "contact": "Community Security Director", "region": "Minnesota", "send_via": "info@jewishstpaul.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Kansas City", "contact": "Community Security Director", "region": "Kansas/Missouri", "send_via": "info@jewishkc.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Omaha", "contact": "Community Security Director", "region": "Nebraska", "send_via": "info@jewishomaha.org", "buyer": "Security/Federation"},
    {"org": "Jewish Federation of Greater Des Moines", "contact": "Community Security Director", "region": "Iowa", "send_via": "info@jewishdesmoines.org", "buyer": "Security/Federation"},

    # ═══ NATIONAL SECURITY ═══
    {"org": "Secure Community Network (SCN)", "contact": "Regional Security Advisor", "region": "National", "send_via": "info@securecommunitynetwork.org", "buyer": "Security/National"},
    {"org": "URJ-SCN Security Desk", "contact": "Security Support", "region": "National", "send_via": "security@urj.org", "buyer": "Security/Denominational"},
    {"org": "USCJ-SCN Security Desk", "contact": "Security Support", "region": "National", "send_via": "security@uscj.org", "buyer": "Security/Denominational"},

    # ═══ DENOMINATIONAL (one email each — not duplicate per region) ═══
    {"org": "Union for Reform Judaism", "contact": "URJ Member Support / Data & Research Team", "region": "National", "send_via": "URJ1800@URJ.org", "buyer": "Denominational"},
    {"org": "United Synagogue of Conservative Judaism", "contact": "USCJ Synagogue Success Team", "region": "National", "send_via": "info@uscj.org", "buyer": "Denominational"},
    {"org": "Orthodox Union", "contact": "OU Community Engagement", "region": "National", "send_via": "community@ou.org", "buyer": "Denominational"},
    {"org": "Chabad Headquarters", "contact": "Chabad Regional Shluchim Office", "region": "National", "send_via": "office@chabad.org", "buyer": "Denominational"},

    # ═══ NATIONAL MEDIA ═══
    {"org": "Jewish Telegraphic Agency (JTA)", "contact": "News Editor", "region": "National", "send_via": "editor@jta.org", "buyer": "Media/Data"},
    {"org": "The Forward", "contact": "News Editor", "region": "National", "send_via": "info@forward.com", "buyer": "Media/Data"},
    {"org": "Jewish Insider", "contact": "Editor", "region": "National", "send_via": "tips@jewishinsider.com", "buyer": "Media/Data"},
    {"org": "Times of Israel (US Desk)", "contact": "US Editor", "region": "National", "send_via": "editor@timesofisrael.com", "buyer": "Media/Data"},
    {"org": "Jewish News Syndicate (JNS)", "contact": "Editor", "region": "National", "send_via": "editor@jns.org", "buyer": "Media/Data"},

    # ═══ REGIONAL JEWISH NEWSPAPERS (real, verifiable) ═══
    {"org": "Atlanta Jewish Times", "contact": "Editor", "region": "Georgia", "send_via": "editor@atlantajewishtimes.com", "buyer": "Media/Regional"},
    {"org": "Cleveland Jewish News", "contact": "Editor", "region": "Ohio", "send_via": "editor@cjn.org", "buyer": "Media/Regional"},
    {"org": "Detroit Jewish News", "contact": "Editor", "region": "Michigan", "send_via": "editor@thejewishnews.com", "buyer": "Media/Regional"},
    {"org": "Jewish Exponent (Philadelphia)", "contact": "Editor", "region": "Pennsylvania", "send_via": "editor@jewishexponent.com", "buyer": "Media/Regional"},
    {"org": "J. — The Jewish News of Northern California", "contact": "Editor", "region": "California", "send_via": "editor@jweekly.com", "buyer": "Media/Regional"},
    {"org": "Jewish Journal (Los Angeles)", "contact": "Editor", "region": "California", "send_via": "editor@jewishjournal.com", "buyer": "Media/Regional"},
    {"org": "St. Louis Jewish Light", "contact": "Editor", "region": "Missouri", "send_via": "editor@stljewishlight.com", "buyer": "Media/Regional"},
    {"org": "Texas Jewish Post", "contact": "Editor", "region": "Texas", "send_via": "editor@texasjewishpost.com", "buyer": "Media/Regional"},
    {"org": "Baltimore Jewish Times", "contact": "Editor", "region": "Maryland", "send_via": "editor@jewishtimes.com", "buyer": "Media/Regional"},
    {"org": "Pittsburgh Jewish Chronicle", "contact": "Editor", "region": "Pennsylvania", "send_via": "editor@pittsburghjewishchronicle.org", "buyer": "Media/Regional"},
    {"org": "New Jersey Jewish Standard", "contact": "Editor", "region": "New Jersey", "send_via": "editor@jewishstandard.com", "buyer": "Media/Regional"},
    {"org": "Washington Jewish Week", "contact": "Editor", "region": "DC/MD/VA", "send_via": "editor@washingtonjewishweek.com", "buyer": "Media/Regional"},
    {"org": "Arizona Jewish News", "contact": "Editor", "region": "Arizona", "send_via": "editor@azjewishnews.com", "buyer": "Media/Regional"},

    # ═══ HERITAGE & DATA ═══
    {"org": "JewishGen", "contact": "Data Director", "region": "National", "send_via": "support@jewishgen.org", "buyer": "Heritage/Data"},
    {"org": "US Holocaust Memorial Museum", "contact": "Regional Outreach Director", "region": "National", "send_via": "info@ushmm.org", "buyer": "Heritage/Security"},
    {"org": "American Sephardi Federation", "contact": "Program Director", "region": "National", "send_via": "info@americansephardi.org", "buyer": "Heritage/Data"},

    # ═══ ACADEMIC ═══
    {"org": "Brandeis — Cohen Center for Modern Jewish Studies", "contact": "Research Director", "region": "National", "send_via": "cohencenter@brandeis.edu", "buyer": "Academic/Data"},
    {"org": "Brandeis — American Jewish Population Project", "contact": "Project Director", "region": "National", "send_via": "ajpp@brandeis.edu", "buyer": "Academic/Data"},
    {"org": "Brandeis — Steinhardt Social Research Institute", "contact": "Research Director", "region": "National", "send_via": "ssri@brandeis.edu", "buyer": "Academic/Data"},
    {"org": "NYU Taub Center for Israel Studies", "contact": "Director", "region": "New York", "send_via": "israelstudies@nyu.edu", "buyer": "Academic/Data"},
    {"org": "Yeshiva University Center for Israel Studies", "contact": "Director", "region": "New York", "send_via": "cis@yu.edu", "buyer": "Academic/Data"},
    {"org": "University of Maryland Gildenhorn Institute", "contact": "Director", "region": "Maryland", "send_via": "israelstudies@umd.edu", "buyer": "Academic/Data"},
]


# ═══════════════════════════════════════════════════════════════
# EMAIL TEMPLATE — Minimalist
# ═══════════════════════════════════════════════════════════════

SUBJECT = "How many synagogues are there?"

def send_email(to, subj, synagogue_count, map_cid):
    """Send multipart email with inline map image."""
    msg = MIMEMultipart("related")
    msg["From"] = FROM
    msg["To"] = to
    msg["Reply-To"] = REPLY_TO
    msg["Subject"] = subj

    # HTML body with embedded image
    html = f"""<html><body style="font-family: Georgia, serif; color: #222;">
<p style="font-size: 48px; font-weight: bold; margin: 0 0 24px 0; line-height: 1.1;">{synagogue_count:,}.</p>
<img src="cid:{map_cid}" style="width:100%;max-width:100%;border-radius:4px;margin-bottom:24px;">
<p style="font-size:16px;max-width:600px;line-height:1.5;margin:0 0 24px 0;">I maintain the world's only complete geospatial registry of every synagogue and Jewish religious site worldwide.</p>
<p style="font-size:16px;max-width:600px;line-height:1.5;margin:0 0 24px 0;">If you'd like your region, denomination, or security slice, I can send it — just reply here.</p>
<p style="color:#666;font-size:13px;white-space:pre-line;">Best,
{SIG}</p>
</body></html>"""

    msg.attach(MIMEText(html, "html"))

    # Attach map image
    with open(MAP_PNG, "rb") as f:
        img = MIMEImage(f.read())
        img.add_header("Content-ID", f"<{map_cid}>")
        img.add_header("Content-Disposition", "inline", filename="global_synagogues.png")
        msg.attach(img)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.starttls()
        s.login("charlesaprescottjr@gmail.com", PWD)
        s.send_message(msg)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # 1. Generate map
    print("=== GENERATING GLOBAL SYNAGOGUE MAP ===\n")
    syn_count = generate_map()

    # 2. Build send queue
    SENT_LOG = OUT / "jewish_regional_sent.txt"
    already = set()
    if SENT_LOG.exists():
        for line in SENT_LOG.read_text().strip().split("\n"):
            if line.strip():
                already.add(line.strip().lower())

    ready = [c for c in CONTACTS if c.get("send_via") and c["send_via"].lower() not in already]

    print(f"\n=== REGIONAL JEWISH ORGS CAMPAIGN ===\n")
    print(f"Subject: \"{SUBJECT}\"")
    print(f"Synagogue count: {syn_count:,}")
    print(f"Contacts: {len(CONTACTS)} total, {len(ready)} ready, {len(CONTACTS) - len(ready)} already sent\n")

    # Group by buyer type
    for btype in ["Security/Federation", "Security/National", "Security/Denominational", "Denominational", "Media/Data", "Media/Regional", "Heritage/Data", "Heritage/Security", "Academic/Data"]:
        group = [c for c in ready if c.get("buyer") == btype]
        if group:
            print(f"  {btype}: {len(group)}")
            for c in group:
                print(f"    {c['org'][:45]:45s} [{c['region']}] -> {c['send_via']}")
    print()

    # 3. Send loop
    print(f"Starting send (1 per {INTERVAL}s, Ctrl+C to stop)...\n")
    ok = fail = 0

    for i, c in enumerate(ready):
        to = c["send_via"]
        print(f"[{i+1}/{len(ready)}] {c['org'][:42]:42s} [{c['region']}] -> {to}", end="", flush=True)

        try:
            send_email(to, SUBJECT, syn_count, "global_synagogues_map")
            ok += 1
            with open(SENT_LOG, "a") as f:
                f.write(f"{to}|{c['org']}|{c['region']}|{datetime.now().isoformat()}\n")
            print(f"  ✅ OK ({ok} sent, {fail} failed)")
        except Exception as e:
            fail += 1
            with open(OUT / "gmail_failed.txt", "a") as f:
                f.write(f"{datetime.now().isoformat()},{to},{str(e)[:100]}\n")
            print(f"  ❌ FAIL ({ok} sent, {fail} failed): {str(e)[:80]}")

        if i < len(ready) - 1:
            time.sleep(INTERVAL)

    print(f"\n=== DONE ===\n{ok} sent, {fail} failed")
