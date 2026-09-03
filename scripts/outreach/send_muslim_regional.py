"""
REGIONAL MUSLIM ORGS CAMPAIGN — "How many mosques are there?"
Minimalist, high-impact template. Sends to Muslim umbrella orgs, relief agencies,
Islamic finance, halal certifiers, academic centers, media, embassies, and directories.

Generates global mosque map PNG for inline email embedding.
397K mosques mapped worldwide across 53 traditions in 200+ countries.
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
MAP_PNG = OUT / "map_muslim_global_mosques.png"

SIG = """Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto (incoming Fall 2026)
charlesaprescottjr@gmail.com | 843-504-4542"""

# ═══════════════════════════════════════════════════════════════
# GENERATE GLOBAL MOSQUE MAP PNG
# ═══════════════════════════════════════════════════════════════

def generate_map():
    """Generate a dark-themed global mosque scatter map PNG."""
    import sqlite3, pandas as pd
    import plotly.express as px

    db = sqlite3.connect("E:/grid/churches.db")
    df = pd.read_sql("""
        SELECT id, name, city, state, country,
               CAST(latitude AS REAL) as latitude, CAST(longitude AS REAL) as longitude,
               landmark_type, tradition
        FROM churches
        WHERE faith = 'Islam' AND latitude IS NOT NULL
    """, db)
    db.close()

    print(f"Map data: {len(df):,} Muslim sites with GPS")

    # Clean tradition labels — collapse to major branches
    tradition_map = {
        # Sunni branches
        "Sunni": "Sunni", "sunni": "Sunni", "Hanafi": "Sunni (Hanafi)",
        "Shafii": "Sunni (Shafi'i)", "Maliki": "Sunni (Maliki)", "Hanbali": "Sunni (Hanbali)",
        "Salafi": "Salafi", "salafi": "Salafi", "Wahhabi": "Salafi",
        "African Methodist Episcopal": "Sunni",  # misclassification noise
        "islam": "Islam (General)", "Islam": "Islam (General)",
        "non_denominational": "Non-Denominational",
        # Shia branches
        "Twelver": "Shia (Twelver)", "Ismaili": "Shia (Ismaili)",
        "Zaydi": "Shia (Zaydi)", "Alawite": "Shia (Alawite)",
        "shia": "Shia", "Shia": "Shia",
        # Other branches
        "Ibadi": "Ibadi", "ibadi": "Ibadi",
        "Sufi": "Sufi", "sufi": "Sufi",
        "Ahmadiyya": "Ahmadiyya", "ahmadiyya": "Ahmadiyya",
        "Alevi": "Alevi", "Quranist": "Quranist",
        "Nation of Islam": "Nation of Islam",
        "Moorish Science": "Moorish Science",
        "Hindu (general)": "Islam (General)",  # misc noise
    }
    df["tradition_clean"] = df["tradition"].map(tradition_map).fillna("Islam (General)")

    # Simplify for legend: collapse to 8 categories
    def simplify_trad(t):
        if "Sunni" in str(t): return "Sunni"
        if "Salafi" in str(t): return "Salafi"
        if "Shia" in str(t): return "Shia"
        if t == "Ibadi": return "Ibadi"
        if t == "Sufi": return "Sufi"
        if t == "Ahmadiyya": return "Ahmadiyya"
        if t in ("Alevi", "Quranist", "Nation of Islam", "Moorish Science"): return "Other Traditions"
        return "Islam (General)"

    df["tradition_simple"] = df["tradition_clean"].apply(simplify_trad)

    tradition_colors = {
        "Sunni": "#1f77b4",
        "Salafi": "#2ca02c",
        "Shia": "#d62728",
        "Ibadi": "#ff7f0e",
        "Sufi": "#9467bd",
        "Ahmadiyya": "#8c564b",
        "Islam (General)": "#17becf",
        "Other Traditions": "#e377c2",
    }

    # Sample for performance — 397K is too many for mapbox
    sample = df if len(df) <= 40000 else df.sample(n=40000, random_state=42)

    fig = px.scatter_mapbox(
        sample, lat="latitude", lon="longitude",
        color="tradition_simple", color_discrete_map=tradition_colors,
        size_max=4, zoom=1.3, height=700, opacity=0.45,
        hover_data={"name": True, "city": True, "country": True, "landmark_type": True},
        title=f"<b>Global Mosque Infrastructure — {len(df):,} Muslim Sites Mapped Worldwide</b><br><sup>GRID: Every dot is a mosque, shrine, or Islamic school. 200+ countries. GPS-located. AI-verified across 53 traditions.</sup>",
        mapbox_style="carto-darkmatter",
    )
    fig.update_layout(margin={"r": 0, "t": 60, "l": 0, "b": 0}, legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
    fig.update_traces(marker=dict(size=2.5))

    # Save PNG + HTML
    fig.write_image(MAP_PNG, width=1200, height=700, scale=2)
    fig.write_html(OUT / "map_muslim_global_mosques.html")
    print(f"   -> {MAP_PNG}")
    print(f"   -> map_muslim_global_mosques.html")
    return len(df)


# ═══════════════════════════════════════════════════════════════
# CONTACTS — Comprehensive Muslim Organization Outreach
# ═══════════════════════════════════════════════════════════════

CONTACTS = [
    # ═══════════════════════════════════════════════════════════
    # UMBRELLA / NATIONAL ADVOCACY
    # ═══════════════════════════════════════════════════════════
    {"org": "Islamic Society of North America (ISNA)", "contact": "Executive Director", "region": "National", "send_via": "info@isna.net", "buyer": "Umbrella/Advocacy"},
    {"org": "Islamic Circle of North America (ICNA)", "contact": "President / Outreach", "region": "National", "send_via": "info@icna.org", "buyer": "Umbrella/Advocacy"},
    {"org": "Council on American-Islamic Relations (CAIR)", "contact": "National Executive Director", "region": "National", "send_via": "info@cair.com", "buyer": "Advocacy/Civil Rights"},
    {"org": "Muslim Public Affairs Council (MPAC)", "contact": "Policy Director", "region": "National", "send_via": "info@mpac.org", "buyer": "Advocacy/Policy"},
    {"org": "Muslim American Society (MAS)", "contact": "Executive Director", "region": "National", "send_via": "info@muslimamericansociety.org", "buyer": "Umbrella/Advocacy"},
    {"org": "Islamic Supreme Council of America (ISCA)", "contact": "Director", "region": "National", "send_via": "info@islamicsupremecouncil.org", "buyer": "Umbrella"},
    {"org": "Federation of Islamic Associations (FIA)", "contact": "President", "region": "National", "send_via": "info@fiaonline.org", "buyer": "Umbrella"},
    {"org": "Muslim Advocates", "contact": "Legal Director", "region": "National", "send_via": "info@muslimadvocates.org", "buyer": "Advocacy/Legal"},
    {"org": "Emerge USA", "contact": "Executive Director", "region": "National", "send_via": "info@emergeusa.org", "buyer": "Advocacy/Civic"},
    {"org": "Inner-City Muslim Action Network (IMAN)", "contact": "Executive Director", "region": "Chicago", "send_via": "info@iman.org", "buyer": "Advocacy/Community"},
    {"org": "American Muslims for Palestine (AMP)", "contact": "National Director", "region": "National", "send_via": "info@ampalestine.org", "buyer": "Advocacy"},
    {"org": "Muslim Legal Fund of America (MLFA)", "contact": "Executive Director", "region": "National", "send_via": "info@mlfa.org", "buyer": "Advocacy/Legal"},
    {"org": "Shoulder to Shoulder Campaign", "contact": "Director", "region": "National", "send_via": "info@shouldertoshouldercampaign.org", "buyer": "Interfaith"},
    {"org": "Interfaith Youth Core (IFYC)", "contact": "Program Director", "region": "National", "send_via": "info@ifyc.org", "buyer": "Interfaith"},

    # ═══════════════════════════════════════════════════════════
    # CAIR REGIONAL CHAPTERS (largest chapters)
    # ═══════════════════════════════════════════════════════════
    {"org": "CAIR-Los Angeles (Greater LA)", "contact": "Executive Director", "region": "California", "send_via": "info@losangeles.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-San Francisco Bay Area", "contact": "Executive Director", "region": "California", "send_via": "info@sfba.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-Chicago", "contact": "Executive Director", "region": "Illinois", "send_via": "info@chicago.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-New York", "contact": "Executive Director", "region": "New York", "send_via": "info@ny.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-Florida", "contact": "Executive Director", "region": "Florida", "send_via": "info@fl.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-Texas (Houston)", "contact": "Executive Director", "region": "Texas", "send_via": "info@houston.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-Michigan", "contact": "Executive Director", "region": "Michigan", "send_via": "info@michigan.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-Philadelphia", "contact": "Executive Director", "region": "Pennsylvania", "send_via": "info@philadelphia.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-Minnesota", "contact": "Executive Director", "region": "Minnesota", "send_via": "info@mn.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-Washington", "contact": "Executive Director", "region": "Washington", "send_via": "info@wa.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-Ohio (Columbus)", "contact": "Executive Director", "region": "Ohio", "send_via": "info@ohio.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-Dallas/Fort Worth", "contact": "Executive Director", "region": "Texas", "send_via": "info@dfw.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-Arizona", "contact": "Executive Director", "region": "Arizona", "send_via": "info@az.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-Washington DC (Capital)", "contact": "Executive Director", "region": "DC/MD/VA", "send_via": "info@dc.cair.com", "buyer": "Advocacy/Regional"},
    {"org": "CAIR-New Jersey", "contact": "Executive Director", "region": "New Jersey", "send_via": "info@nj.cair.com", "buyer": "Advocacy/Regional"},

    # ═══════════════════════════════════════════════════════════
    # RELIEF / HUMANITARIAN
    # ═══════════════════════════════════════════════════════════
    {"org": "Islamic Relief USA", "contact": "CEO / Programs Director", "region": "National", "send_via": "info@irusa.org", "buyer": "Relief"},
    {"org": "Islamic Relief Worldwide", "contact": "CEO", "region": "International", "send_via": "info@islamic-relief.org", "buyer": "Relief"},
    {"org": "Zakat Foundation of America", "contact": "Executive Director", "region": "National", "send_via": "info@zakat.org", "buyer": "Relief"},
    {"org": "Muslim Aid USA", "contact": "Director", "region": "National", "send_via": "info@muslimaidusa.org", "buyer": "Relief"},
    {"org": "Muslim Aid (UK HQ)", "contact": "CEO", "region": "International", "send_via": "info@muslimaid.org", "buyer": "Relief"},
    {"org": "ICNA Relief USA", "contact": "Executive Director", "region": "National", "send_via": "info@icnarelief.org", "buyer": "Relief"},
    {"org": "United Muslim Relief (UMR)", "contact": "Director", "region": "National", "send_via": "info@umrelief.org", "buyer": "Relief"},
    {"org": "Helping Hand for Relief and Development (HHRD)", "contact": "CEO", "region": "National", "send_via": "info@hhrd.org", "buyer": "Relief"},
    {"org": "Human Appeal USA", "contact": "Director", "region": "National", "send_via": "info@humanappealusa.org", "buyer": "Relief"},
    {"org": "Human Appeal International (UK)", "contact": "CEO", "region": "International", "send_via": "info@humanappeal.org.uk", "buyer": "Relief"},
    {"org": "Penny Appeal USA", "contact": "Director", "region": "National", "send_via": "info@pennyappealusa.org", "buyer": "Relief"},
    {"org": "Penny Appeal (UK)", "contact": "CEO", "region": "International", "send_via": "info@pennyappeal.org", "buyer": "Relief"},
    {"org": "Islamic Help USA", "contact": "Director", "region": "National", "send_via": "info@islamichelpusa.org", "buyer": "Relief"},
    {"org": "Baitulmaal", "contact": "Director", "region": "National", "send_via": "info@baitulmaal.org", "buyer": "Relief"},
    {"org": "Ummah Welfare Trust", "contact": "Director", "region": "International", "send_via": "info@uwt.org", "buyer": "Relief"},
    {"org": "Muslim Hands USA", "contact": "Director", "region": "National", "send_via": "info@muslimhandsusa.org", "buyer": "Relief"},
    {"org": "Muslim Hands (UK HQ)", "contact": "CEO", "region": "International", "send_via": "info@muslimhands.org.uk", "buyer": "Relief"},

    # ═══════════════════════════════════════════════════════════
    # ACADEMIC / RESEARCH / ISLAMIC STUDIES CENTERS
    # ═══════════════════════════════════════════════════════════
    {"org": "International Institute of Islamic Thought (IIIT)", "contact": "Research Director", "region": "National", "send_via": "info@iiit.org", "buyer": "Academic/Research"},
    {"org": "Institute for Social Policy & Understanding (ISPU)", "contact": "Research Director", "region": "National", "send_via": "info@ispu.org", "buyer": "Academic/Research"},
    {"org": "Duke Islamic Studies Center", "contact": "Director", "region": "North Carolina", "send_via": "disc@duke.edu", "buyer": "Academic/Research"},
    {"org": "Georgetown — ACMCU (Muslim-Christian Understanding)", "contact": "Director", "region": "Washington DC", "send_via": "acmcu@georgetown.edu", "buyer": "Academic/Research"},
    {"org": "Harvard Islamic Studies Program", "contact": "Director", "region": "Massachusetts", "send_via": "islamicstudies@harvard.edu", "buyer": "Academic/Research"},
    {"org": "Yale MacMillan Center — Islamic Studies", "contact": "Director", "region": "Connecticut", "send_via": "macmillan@yale.edu", "buyer": "Academic/Research"},
    {"org": "University of Chicago — Middle Eastern Studies", "contact": "Director", "region": "Illinois", "send_via": "cmes@uchicago.edu", "buyer": "Academic/Research"},
    {"org": "Columbia — Middle East Institute", "contact": "Director", "region": "New York", "send_via": "mei@columbia.edu", "buyer": "Academic/Research"},
    {"org": "UCLA Center for Near Eastern Studies", "contact": "Director", "region": "California", "send_via": "cnes@international.ucla.edu", "buyer": "Academic/Research"},
    {"org": "University of Michigan — Islamic Studies", "contact": "Director", "region": "Michigan", "send_via": "islamicstudies@umich.edu", "buyer": "Academic/Research"},
    {"org": "UNC Center for Middle East and Islamic Studies", "contact": "Director", "region": "North Carolina", "send_via": "cmeis@unc.edu", "buyer": "Academic/Research"},
    {"org": "Stanford Abbasi Program in Islamic Studies", "contact": "Director", "region": "California", "send_via": "islamicstudies@stanford.edu", "buyer": "Academic/Research"},
    {"org": "Oxford Centre for Islamic Studies", "contact": "Director", "region": "International", "send_via": "info@oxcis.ac.uk", "buyer": "Academic/Research"},
    {"org": "Cambridge Centre for Islamic Studies", "contact": "Director", "region": "International", "send_via": "info@cis.cam.ac.uk", "buyer": "Academic/Research"},
    {"org": "SOAS — Centre of Islamic Studies", "contact": "Director", "region": "International", "send_via": "islamicstudies@soas.ac.uk", "buyer": "Academic/Research"},
    {"org": "Zaytuna College", "contact": "President", "region": "California", "send_via": "info@zaytuna.edu", "buyer": "Academic/Education"},
    {"org": "Bayyinah Institute", "contact": "Director", "region": "Texas", "send_via": "info@bayyinah.com", "buyer": "Academic/Education"},
    {"org": "Al-Maghrib Institute", "contact": "Director", "region": "Texas", "send_via": "info@almaghrib.org", "buyer": "Academic/Education"},
    {"org": "Qalam Institute", "contact": "Director", "region": "Texas", "send_via": "info@qalaminstitute.org", "buyer": "Academic/Education"},
    {"org": "Mishkah University", "contact": "President", "region": "Florida", "send_via": "info@mishkahu.org", "buyer": "Academic/Education"},
    {"org": "American Islamic College (Chicago)", "contact": "President", "region": "Illinois", "send_via": "info@aicchicago.edu", "buyer": "Academic/Education"},
    {"org": "Graduate Theological Foundation — Islamic Studies", "contact": "Dean", "region": "Indiana", "send_via": "info@gtfeducation.org", "buyer": "Academic/Education"},
    {"org": "Fiqh Council of North America", "contact": "Chairman", "region": "National", "send_via": "info@fiqhcouncil.org", "buyer": "Academic/Religious"},
    {"org": "Islamic Society of North America — Islamic Schools", "contact": "Education Director", "region": "National", "send_via": "education@isna.net", "buyer": "Academic/Education"},
    {"org": "DinarStandard — Muslim Market Research", "contact": "CEO", "region": "National", "send_via": "info@dinarstandard.com", "buyer": "Research/Business"},

    # ═══════════════════════════════════════════════════════════
    # MEDIA / PUBLISHING
    # ═══════════════════════════════════════════════════════════
    {"org": "Al Jazeera English (News Desk)", "contact": "News Editor", "region": "International", "send_via": "pressoffice@aljazeera.net", "buyer": "Media"},
    {"org": "Al Jazeera America / AJ+", "contact": "Digital Editor", "region": "National", "send_via": "ajplus@aljazeera.net", "buyer": "Media"},
    {"org": "TRT World (Turkish Radio & Television)", "contact": "News Editor", "region": "International", "send_via": "info@trtworld.com", "buyer": "Media"},
    {"org": "Islam Channel (UK)", "contact": "Editor", "region": "International", "send_via": "info@islamchannel.tv", "buyer": "Media"},
    {"org": "MuslimMatters.org", "contact": "Editor", "region": "National", "send_via": "info@muslimmatters.org", "buyer": "Media"},
    {"org": "AboutIslam.net", "contact": "Editor", "region": "International", "send_via": "info@aboutislam.net", "buyer": "Media"},
    {"org": "IlmFeed", "contact": "Editor", "region": "International", "send_via": "info@ilmfeed.com", "buyer": "Media"},
    {"org": "The Muslim Vibe", "contact": "Editor", "region": "International", "send_via": "info@themuslimvibe.com", "buyer": "Media"},
    {"org": "Muslim Girl", "contact": "Editor", "region": "National", "send_via": "info@muslimgirl.com", "buyer": "Media"},
    {"org": "Mvslim", "contact": "Editor", "region": "International", "send_via": "info@mvslim.com", "buyer": "Media"},
    {"org": "Al Jumuah Magazine", "contact": "Editor", "region": "National", "send_via": "info@aljumuah.com", "buyer": "Media/Publishing"},
    {"org": "American Muslim Today", "contact": "Editor", "region": "National", "send_via": "info@americanmuslimtoday.com", "buyer": "Media"},
    {"org": "Muslim Journal (Nation of Islam affiliated)", "contact": "Editor", "region": "National", "send_via": "info@muslimjournal.net", "buyer": "Media"},
    {"org": "Islamic Horizons (ISNA magazine)", "contact": "Editor", "region": "National", "send_via": "horizons@isna.net", "buyer": "Media/Publishing"},
    {"org": "The Message International", "contact": "Editor", "region": "National", "send_via": "info@messageinternational.com", "buyer": "Media/Publishing"},
    {"org": "Kube Publishing / The Islamic Foundation", "contact": "Publisher", "region": "International", "send_via": "info@kubepublishing.com", "buyer": "Publishing"},
    {"org": "Amana Publications", "contact": "Publisher", "region": "National", "send_via": "info@amana-publications.com", "buyer": "Publishing"},
    {"org": "Sandala Ltd (Islamic book distributor)", "contact": "Director", "region": "International", "send_via": "info@sandala.org", "buyer": "Publishing"},

    # ═══════════════════════════════════════════════════════════
    # ISLAMIC FINANCE
    # ═══════════════════════════════════════════════════════════
    {"org": "Amana Mutual Funds (Saturna Capital)", "contact": "President", "region": "National", "send_via": "info@amanafunds.com", "buyer": "Finance"},
    {"org": "Guidance Residential", "contact": "CEO", "region": "National", "send_via": "info@guidanceresidential.com", "buyer": "Finance"},
    {"org": "Devon Bank (Islamic Banking Division)", "contact": "SVP Islamic Banking", "region": "Illinois", "send_via": "info@devonbank.com", "buyer": "Finance"},
    {"org": "University Islamic Financial", "contact": "President", "region": "Michigan", "send_via": "info@universityislamicfinancial.com", "buyer": "Finance"},
    {"org": "Al Baraka Bank USA", "contact": "CEO", "region": "National", "send_via": "info@albaraka.com", "buyer": "Finance"},
    {"org": "Islamic Finance Foundation (IFF)", "contact": "Director", "region": "National", "send_via": "info@islamicfinancefoundation.org", "buyer": "Finance"},
    {"org": "Lariba (American Finance House)", "contact": "President", "region": "California", "send_via": "info@lariba.com", "buyer": "Finance"},
    {"org": "Shariah Capital", "contact": "CEO", "region": "National", "send_via": "info@shariahcapital.com", "buyer": "Finance"},
    {"org": "Ijarah Finance (auto/mortgage)", "contact": "CEO", "region": "Michigan", "send_via": "info@ijarahfinance.com", "buyer": "Finance"},
    {"org": "Guidance Financial Group", "contact": "CEO", "region": "National", "send_via": "info@guidancefinancialgroup.com", "buyer": "Finance"},

    # ═══════════════════════════════════════════════════════════
    # HALAL CERTIFICATION
    # ═══════════════════════════════════════════════════════════
    {"org": "Islamic Food and Nutrition Council of America (IFANCA)", "contact": "Executive Director", "region": "National", "send_via": "info@ifanca.org", "buyer": "Halal"},
    {"org": "Halal Food Standards Alliance of America (HFSAA)", "contact": "Director", "region": "National", "send_via": "info@hfsaa.org", "buyer": "Halal"},
    {"org": "Islamic Services of America (ISA)", "contact": "President", "region": "Iowa", "send_via": "info@isaiowa.org", "buyer": "Halal"},
    {"org": "American Halal Association", "contact": "President", "region": "National", "send_via": "info@americanhalalassociation.org", "buyer": "Halal"},
    {"org": "Shari'ah Association of North America (SANA)", "contact": "Director", "region": "National", "send_via": "info@sanahalal.com", "buyer": "Halal"},
    {"org": "Halal Monitoring Authority (HMA Canada)", "contact": "Director", "region": "Canada", "send_via": "info@hma.jucanada.org", "buyer": "Halal"},
    {"org": "Halal Transactions of Omaha", "contact": "Director", "region": "Nebraska", "send_via": "info@hto.org", "buyer": "Halal"},
    {"org": "Muslim Consumer Group", "contact": "Director", "region": "National", "send_via": "info@muslimconsumergroup.com", "buyer": "Halal"},

    # ═══════════════════════════════════════════════════════════
    # MOSQUE DIRECTORIES / TECH
    # ═══════════════════════════════════════════════════════════
    {"org": "IslamicFinder", "contact": "CEO / Product", "region": "International", "send_via": "info@islamicfinder.org", "buyer": "Directory/Tech"},
    {"org": "Salatomatic / Zabihah", "contact": "Founder", "region": "National", "send_via": "info@salatomatic.com", "buyer": "Directory/Tech"},
    {"org": "Muslim Pro", "contact": "CEO / Content", "region": "International", "send_via": "info@muslimpro.com", "buyer": "Directory/Tech"},
    {"org": "Masjidway / Mosalasala", "contact": "Founder", "region": "International", "send_via": "info@mosqueway.com", "buyer": "Directory/Tech"},
    {"org": "HalalTrip", "contact": "CEO", "region": "International", "send_via": "info@halaltrip.com", "buyer": "Directory/Tech"},

    # ═══════════════════════════════════════════════════════════
    # INTERNATIONAL ORGANIZATIONS
    # ═══════════════════════════════════════════════════════════
    {"org": "Organization of Islamic Cooperation (OIC)", "contact": "Secretary General Office", "region": "International", "send_via": "info@oic-oci.org", "buyer": "International"},
    {"org": "Islamic Development Bank (IsDB)", "contact": "President's Office", "region": "International", "send_via": "info@isdb.org", "buyer": "International/Finance"},
    {"org": "ISESCO (Islamic Educational, Scientific, Cultural Org)", "contact": "Director General", "region": "International", "send_via": "info@isesco.org.ma", "buyer": "International"},
    {"org": "Muslim World League (MWL)", "contact": "Secretary General", "region": "International", "send_via": "info@themwl.org", "buyer": "International"},
    {"org": "World Assembly of Muslim Youth (WAMY)", "contact": "Director", "region": "International", "send_via": "info@wamy.org", "buyer": "International/Youth"},
    {"org": "International Islamic Relief Organization (IIROSA)", "contact": "Director", "region": "International", "send_via": "info@iirosa.org", "buyer": "International/Relief"},
    {"org": "Diyanet Center of America", "contact": "Director", "region": "Maryland", "send_via": "info@diyanetamerica.org", "buyer": "International/Religious"},
    {"org": "Presidency of Religious Affairs (Diyanet, Turkey)", "contact": "International Relations", "region": "International", "send_via": "info@diyanet.gov.tr", "buyer": "International/Religious"},
    {"org": "International Union of Muslim Scholars (IUMS)", "contact": "Secretariat", "region": "International", "send_via": "info@iumsonline.net", "buyer": "International/Religious"},
    {"org": "Royal Aal al-Bayt Institute for Islamic Thought", "contact": "Director", "region": "International", "send_via": "info@aalalbayt.org", "buyer": "International/Academic"},

    # ═══════════════════════════════════════════════════════════
    # EMBASSY RELIGIOUS / CULTURAL AFFAIRS (MENA + major Muslim-majority)
    # ═══════════════════════════════════════════════════════════
    {"org": "Embassy of Saudi Arabia — Cultural Attaché", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@saudiembassy.net", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of UAE — Cultural Division", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@uae-embassy.org", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Qatar — Cultural Attaché", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@qatarembassy.org", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Kuwait — Cultural Office", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@kuwaitembassy.us", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Morocco — Cultural Center", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@moroccanembassydc.org", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Jordan — Cultural Attaché", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@jordanembassyus.org", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Egypt — Cultural & Educational Bureau", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@egyptembassy.net", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Indonesia — Cultural Attaché", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@embassyofindonesia.org", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Malaysia — Education Division", "contact": "Education Attaché", "region": "Washington DC", "send_via": "info@kln.gov.my", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Pakistan — Press & Culture", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@embassyofpakistanusa.org", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Turkey — Culture & Tourism", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@turkishembassy.com", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Bangladesh — Cultural Wing", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@bdembassyusa.org", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Oman — Cultural Attaché", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@omaniembassyusa.org", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Bahrain — Cultural Office", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@bahrainembassyusa.org", "buyer": "Embassy/Cultural"},
    {"org": "Embassy of Algeria — Cultural Affairs", "contact": "Cultural Attaché", "region": "Washington DC", "send_via": "info@algerianembassy.org", "buyer": "Embassy/Cultural"},

    # ═══════════════════════════════════════════════════════════
    # YOUTH / STUDENTS
    # ═══════════════════════════════════════════════════════════
    {"org": "Muslim Students Association (MSA) National", "contact": "President", "region": "National", "send_via": "info@msanational.org", "buyer": "Youth/Students"},
    {"org": "Muslim Youth of North America (MYNA)", "contact": "Director", "region": "National", "send_via": "info@myna.org", "buyer": "Youth/Students"},
    {"org": "MAS Youth (Muslim American Society)", "contact": "Youth Director", "region": "National", "send_via": "youth@muslimamericansociety.org", "buyer": "Youth/Students"},
    {"org": "ICNA Young Muslims", "contact": "Director", "region": "National", "send_via": "ym@icna.org", "buyer": "Youth/Students"},
    {"org": "MISF (Muslim International Student Fund)", "contact": "Director", "region": "National", "send_via": "info@misfusa.org", "buyer": "Youth/Education"},
    {"org": "Islamic Scholarship Fund (ISF)", "contact": "Director", "region": "National", "send_via": "info@islamicscholarshipfund.org", "buyer": "Youth/Education"},

    # ═══════════════════════════════════════════════════════════
    # WOMEN'S ORGANIZATIONS
    # ═══════════════════════════════════════════════════════════
    {"org": "Muslim Women's Alliance", "contact": "President", "region": "National", "send_via": "info@muslimwomensalliance.org", "buyer": "Women"},
    {"org": "WISE (Women's Islamic Initiative in Spirituality & Equality)", "contact": "Director", "region": "National", "send_via": "info@wisemuslimwomen.org", "buyer": "Women"},
    {"org": "KARAMAH (Muslim Women Lawyers for Human Rights)", "contact": "Executive Director", "region": "National", "send_via": "info@karamah.org", "buyer": "Women/Legal"},
    {"org": "Sisters in Islam (Malaysia, global)", "contact": "Director", "region": "International", "send_via": "info@sistersinislam.org.my", "buyer": "Women"},
    {"org": "Muslim Women's Network (UK)", "contact": "Director", "region": "International", "send_via": "info@mwnuk.co.uk", "buyer": "Women"},

    # ═══════════════════════════════════════════════════════════
    # CHAPLAINCY / PRISON / MILITARY
    # ═══════════════════════════════════════════════════════════
    {"org": "Association of Muslim Chaplains (AMC)", "contact": "President", "region": "National", "send_via": "info@associationofmuslimchaplains.org", "buyer": "Chaplaincy"},
    {"org": "Muslim Chaplains Association (MCA)", "contact": "Director", "region": "National", "send_via": "info@muslimchaplains.org", "buyer": "Chaplaincy"},
    {"org": "Islamic Prisoner Support Network", "contact": "Director", "region": "National", "send_via": "info@islamicprisoner.org", "buyer": "Chaplaincy/Prison"},
    {"org": "Tayba Foundation (prison education)", "contact": "Director", "region": "National", "send_via": "info@taybafoundation.org", "buyer": "Chaplaincy/Prison"},

    # ═══════════════════════════════════════════════════════════
    # FUNERAL / BURIAL
    # ═══════════════════════════════════════════════════════════
    {"org": "Islamic Funeral Services of America", "contact": "Director", "region": "National", "send_via": "info@islamicfuneral.com", "buyer": "Funeral"},
    {"org": "Garden of Peace (Muslim Cemetery Boston)", "contact": "Director", "region": "Massachusetts", "send_via": "info@gardenofpeace.org", "buyer": "Funeral"},
    {"org": "Janazah Services Network", "contact": "Director", "region": "National", "send_via": "info@janazahservices.com", "buyer": "Funeral"},

    # ═══════════════════════════════════════════════════════════
    # HAJJ / UMRAH TRAVEL
    # ═══════════════════════════════════════════════════════════
    {"org": "Nusuk (Saudi Hajj Ministry platform)", "contact": "Partnerships", "region": "International", "send_via": "info@nusuk.sa", "buyer": "Travel/Hajj"},
    {"org": "Al-Haramain Travel", "contact": "Director", "region": "National", "send_via": "info@alharamaintravel.com", "buyer": "Travel/Hajj"},
    {"org": "Dar El Salam Travel", "contact": "Director", "region": "National", "send_via": "info@darelsalamtravel.com", "buyer": "Travel/Hajj"},
    {"org": "Adam Travel (Boston/MA)", "contact": "Director", "region": "Massachusetts", "send_via": "info@adamtravel.com", "buyer": "Travel/Hajj"},
    {"org": "Caravan Travel (NJ)", "contact": "Director", "region": "New Jersey", "send_via": "info@caravantravel.com", "buyer": "Travel/Hajj"},

    # ═══════════════════════════════════════════════════════════
    # REGIONAL ISLAMIC SOCIETIES / COUNCILS (US cities/states)
    # ═══════════════════════════════════════════════════════════
    {"org": "Islamic Center of Southern California", "contact": "Executive Director", "region": "California", "send_via": "info@islamiccenter.org", "buyer": "Regional/Mosque"},
    {"org": "Islamic Center of Greater Miami", "contact": "Director", "region": "Florida", "send_via": "info@icgmiami.org", "buyer": "Regional/Mosque"},
    {"org": "Islamic Society of Boston (ISB)", "contact": "Director", "region": "Massachusetts", "send_via": "info@isboston.org", "buyer": "Regional/Mosque"},
    {"org": "Islamic Association of North Texas (IANT)", "contact": "Director", "region": "Texas", "send_via": "info@iant.com", "buyer": "Regional/Mosque"},
    {"org": "Islamic Center of Washington DC", "contact": "Director", "region": "Washington DC", "send_via": "info@theislamiccenter.us", "buyer": "Regional/Mosque"},
    {"org": "Islamic Center of Greater Toledo", "contact": "Director", "region": "Ohio", "send_via": "info@icgt.org", "buyer": "Regional/Mosque"},
    {"org": "Muslim Community Center (MCC Chicago)", "contact": "Director", "region": "Illinois", "send_via": "info@mccchicago.org", "buyer": "Regional/Mosque"},
    {"org": "Islamic Center of Detroit (ICD)", "contact": "Director", "region": "Michigan", "send_via": "info@icdonline.org", "buyer": "Regional/Mosque"},
    {"org": "All Dulles Area Muslim Society (ADAMS)", "contact": "Executive Director", "region": "Virginia", "send_via": "info@adamscenter.org", "buyer": "Regional/Mosque"},
    {"org": "Muslim Association of Canada (MAC)", "contact": "Executive Director", "region": "Canada", "send_via": "info@macnet.ca", "buyer": "Regional/Canada"},
    {"org": "Islamic Foundation of Toronto", "contact": "Director", "region": "Canada", "send_via": "info@islamicfoundation.ca", "buyer": "Regional/Canada"},
    {"org": "Islamic Society of Britain", "contact": "Director", "region": "United Kingdom", "send_via": "info@isb.org.uk", "buyer": "Regional/UK"},
    {"org": "Muslim Council of Britain (MCB)", "contact": "Secretary General", "region": "United Kingdom", "send_via": "info@mcb.org.uk", "buyer": "Umbrella/UK"},
    {"org": "Union of Islamic Organizations of France (UOIF)", "contact": "President", "region": "France", "send_via": "info@uoif.fr", "buyer": "Umbrella/Europe"},
    {"org": "Central Council of Muslims in Germany (ZMD)", "contact": "Chairperson", "region": "Germany", "send_via": "info@zentralrat.de", "buyer": "Umbrella/Europe"},
    {"org": "Australian National Imams Council (ANIC)", "contact": "Secretary", "region": "Australia", "send_via": "info@anic.org.au", "buyer": "Umbrella/Australia"},

    # ═══════════════════════════════════════════════════════════
    # HEALTH / MEDICAL
    # ═══════════════════════════════════════════════════════════
    {"org": "Islamic Medical Association of North America (IMANA)", "contact": "President", "region": "National", "send_via": "info@imana.org", "buyer": "Health/Medical"},
    {"org": "American Muslim Health Professionals (AMHP)", "contact": "Executive Director", "region": "National", "send_via": "info@amhp.us", "buyer": "Health/Medical"},

    # ═══════════════════════════════════════════════════════════
    # DENOMINATIONAL (specific Islamic branches/traditions)
    # ═══════════════════════════════════════════════════════════
    {"org": "Ahmadiyya Muslim Community USA", "contact": "National President", "region": "National", "send_via": "info@ahmadiyya.us", "buyer": "Denominational"},
    {"org": "Ahmadiyya Muslim Community (UK/International)", "contact": "Amir", "region": "International", "send_via": "info@alislam.org", "buyer": "Denominational"},
    {"org": "Ismaili Council for the USA (Aga Khan)", "contact": "President", "region": "National", "send_via": "info@ismailiusa.org", "buyer": "Denominational"},
    {"org": "Ismaili Council for Canada (Aga Khan)", "contact": "President", "region": "Canada", "send_via": "info@ismaili.ca", "buyer": "Denominational"},
    {"org": "Nation of Islam (NOI Headquarters)", "contact": "Office of Minister Louis Farrakhan", "region": "Illinois", "send_via": "info@noi.org", "buyer": "Denominational"},
]

# ═══════════════════════════════════════════════════════════════
# EMAIL TEMPLATE
# ═══════════════════════════════════════════════════════════════

SUBJECT = "How many mosques are there?"

def send_email(to, subj, mosque_count, map_cid):
    """Send multipart email with inline map image."""
    msg = MIMEMultipart("related")
    msg["From"] = FROM
    msg["To"] = to
    msg["Reply-To"] = REPLY_TO
    msg["Subject"] = subj

    html = f"""<html><body style="font-family: Georgia, serif; color: #222;">
<p style="font-size: 48px; font-weight: bold; margin: 0 0 24px 0; line-height: 1.1;">{mosque_count:,}.</p>
<img src="cid:{map_cid}" style="width:100%;max-width:100%;border-radius:4px;margin-bottom:24px;">
<p style="font-size:16px;max-width:600px;line-height:1.5;margin:0 0 24px 0;">I maintain the world's only complete geospatial registry of every mosque and Islamic religious site worldwide. Sunni, Shia, Ibadi, Sufi, Ahmadiyya — every tradition, every country.</p>
<p style="font-size:16px;max-width:600px;line-height:1.5;margin:0 0 24px 0;">If you'd like your country, tradition, or regional slice, I can send it — just reply here.</p>
<p style="color:#666;font-size:13px;white-space:pre-line;">Best,
{SIG}</p>
</body></html>"""

    msg.attach(MIMEText(html, "html"))

    with open(MAP_PNG, "rb") as f:
        img = MIMEImage(f.read())
        img.add_header("Content-ID", f"<{map_cid}>")
        img.add_header("Content-Disposition", "inline", filename="global_mosques.png")
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
    print("=== GENERATING GLOBAL MOSQUE MAP ===\n")
    mosque_count = generate_map()

    # 2. Build send queue
    SENT_LOG = OUT / "muslim_regional_sent.txt"
    already = set()
    if SENT_LOG.exists():
        for line in SENT_LOG.read_text().strip().split("\n"):
            if line.strip():
                already.add(line.strip().lower())

    ready = [c for c in CONTACTS if c.get("send_via") and c["send_via"].lower() not in already]

    print(f"\n=== MUSLIM ORGS OUTREACH CAMPAIGN ===\n")
    print(f"Subject: \"{SUBJECT}\"")
    print(f"Mosque count: {mosque_count:,}")
    print(f"Contacts: {len(CONTACTS)} total, {len(ready)} ready, {len(CONTACTS) - len(ready)} already sent\n")

    # Group by buyer type
    from collections import Counter
    for btype, count in Counter(c["buyer"] for c in CONTACTS).most_common():
        group = [c for c in ready if c.get("buyer") == btype]
        if group:
            print(f"  {btype}: {len(group)}/{count}")
            for c in group:
                print(f"    {c['org'][:52]:52s} [{c['region']}] -> {c['send_via']}")
    print()

    # Save contact list
    json.dump(CONTACTS, open(OUT / "muslim_org_leads.json", "w"), indent=2)

    # 3. Send loop
    print(f"Starting send (1 per {INTERVAL}s, Ctrl+C to stop)...\n")
    ok = fail = 0

    for i, c in enumerate(ready):
        to = c["send_via"]
        print(f"[{i+1}/{len(ready)}] {c['org'][:48]:48s} [{c['region']}] -> {to}", end="", flush=True)

        try:
            send_email(to, SUBJECT, mosque_count, "global_mosques_map")
            ok += 1
            with open(SENT_LOG, "a") as f:
                f.write(f"{to}|{c['org']}|{c['region']}|{c['buyer']}|{datetime.now().isoformat()}\n")
            print(f"  ✅ OK ({ok} sent, {fail} failed)")
        except Exception as e:
            fail += 1
            with open(OUT / "gmail_failed.txt", "a") as f:
                f.write(f"{datetime.now().isoformat()},{to},{str(e)[:100]}\n")
            print(f"  ❌ FAIL ({ok} sent, {fail} failed): {str(e)[:80]}")

        if i < len(ready) - 1:
            time.sleep(INTERVAL)

    print(f"\n=== DONE ===\n{ok} sent, {fail} failed")
