"""
WHALING LIST — 300 high-value prospects for July 4 weekend.
Sends 100/day using Gmail SMTP (1 per ~14 min = ~100/day).
"""
import json, smtplib, time, os
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ── Config ──
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587
FROM = "Charles Prescott <charlesaprescottjr@gmail.com>"
PWD = os.environ.get("GMAIL_APP_PASSWORD")
INTERVAL = 180  # 3 min = ~480/day (just under Gmail 500/day limit). 152 whales x 3min = ~7.6hr
OUT = Path("outputs/outreach")
SENT_LOG = OUT / "gmail_sent.txt"
FAIL_LOG = OUT / "gmail_failed.txt"
WHALE_SENT = OUT / "whale_sent.txt"

ADX = "https://us-east-1.console.aws.amazon.com/dataexchange/home?region=us-east-1#/data-sets/993cef8f87cacadaee6e20e52d939084"
BQ = "https://console.cloud.google.com/bigquery?project=american-rel-infra&p=american-rel-infra&d=American_Religious_Infrastructure&t=demo_vt_churches&page=table"
SIG = """Charles Prescott
Creator, GRID -- Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542"""

# ── WHALES: 300 high-value prospects across 8 sectors ──
WHALES = [
    #══════════════════════ TECH / DATA PLATFORMS ══════════════════════
    {"org": "Google Maps - Content Partners", "email": "contentpartners@google.com", "sector": "Big Tech"},
    {"org": "Apple Maps - Data Partnerships", "email": "mappartners@apple.com", "sector": "Big Tech"},
    {"org": "Meta - Data Partnerships", "email": "datapartners@fb.com", "sector": "Big Tech"},
    {"org": "Microsoft Maps - Partner", "email": "mapspartner@microsoft.com", "sector": "Big Tech"},
    {"org": "Amazon Location Service", "email": "aws-location@amazon.com", "sector": "Big Tech"},
    {"org": "Palantir - Data Acquisition", "email": "dataacquisitions@palantir.com", "sector": "Big Tech"},
    {"org": "Yelp - Data Licensing", "email": "datalicensing@yelp.com", "sector": "Big Tech"},
    {"org": "TripAdvisor - Content", "email": "contentlicensing@tripadvisor.com", "sector": "Big Tech"},
    {"org": "Airbnb - Data Science", "email": "data@airbnb.com", "sector": "Big Tech"},
    {"org": "Uber - Maps Data", "email": "mapspartnerships@uber.com", "sector": "Big Tech"},
    {"org": "Snap Inc - Location Data", "email": "partnerships@snap.com", "sector": "Big Tech"},
    {"org": "Pinterest - Data", "email": "partners@pinterest.com", "sector": "Big Tech"},
    {"org": "TikTok - Data Licensing", "email": "datalicensing@tiktok.com", "sector": "Big Tech"},
    {"org": "Snowflake - Data Marketplace", "email": "marketplace@snowflake.com", "sector": "Data Infra"},
    {"org": "Databricks - Marketplace", "email": "marketplace@databricks.com", "sector": "Data Infra"},
    {"org": "Palantir Foundry", "email": "foundry@palantir.com", "sector": "Big Tech"},
    {"org": "OpenAI - Data Partnerships", "email": "datapartnerships@openai.com", "sector": "Big Tech"},
    {"org": "Anthropic - Data", "email": "partnerships@anthropic.com", "sector": "Big Tech"},

    #══════════════════════ INSURANCE (church property risk) ══════════════════════
    {"org": "State Farm - Data Licensing", "email": "data.acquisition@statefarm.com", "sector": "Insurance"},
    {"org": "Allstate - Underwriting Data", "email": "data@allstate.com", "sector": "Insurance"},
    {"org": "Liberty Mutual - Data", "email": "datalicensing@libertymutual.com", "sector": "Insurance"},
    {"org": "Nationwide - Underwriting", "email": "underwritingdata@nationwide.com", "sector": "Insurance"},
    {"org": "Travelers - Risk Data", "email": "data@travelers.com", "sector": "Insurance"},
    {"org": "The Hartford - Data", "email": "datainnovation@thehartford.com", "sector": "Insurance"},
    {"org": "Chubb - Property Data", "email": "data.solutions@chubb.com", "sector": "Insurance"},
    {"org": "AIG - Risk Analytics", "email": "riskdata@aig.com", "sector": "Insurance"},
    {"org": "Berkshire Hathaway GUARD", "email": "info@guard.com", "sector": "Insurance"},
    {"org": "Zurich North America", "email": "data@zurichna.com", "sector": "Insurance"},
    {"org": "CNA Insurance", "email": "datasolutions@cna.com", "sector": "Insurance"},
    {"org": "Auto-Owners Insurance", "email": "info@auto-owners.com", "sector": "Insurance"},
    {"org": "American Family Insurance", "email": "data@amfam.com", "sector": "Insurance"},
    {"org": "Farmers Insurance", "email": "datalicensing@farmers.com", "sector": "Insurance"},
    {"org": "USAA - Data", "email": "data.solutions@usaa.com", "sector": "Insurance"},
    {"org": "Erie Insurance", "email": "info@erieinsurance.com", "sector": "Insurance"},
    {"org": "Cincinnati Insurance", "email": "info@cinfin.com", "sector": "Insurance"},
    {"org": "Reliance Standard", "email": "info@rsli.com", "sector": "Insurance"},
    {"org": "Tokio Marine HCC", "email": "info@tmhcc.com", "sector": "Insurance"},
    {"org": "Markel - Specialty", "email": "data@markel.com", "sector": "Insurance"},
    {"org": "Philadelphia Insurance", "email": "info@phly.com", "sector": "Insurance"},
    {"org": "Selective Insurance", "email": "info@selective.com", "sector": "Insurance"},
    {"org": "Hanover Insurance", "email": "data@hanover.com", "sector": "Insurance"},
    {"org": "Progressive - Data", "email": "datalicensing@progressive.com", "sector": "Insurance"},
    {"org": "GEICO - Data", "email": "dataanalytics@geico.com", "sector": "Insurance"},

    #══════════════════════ REAL ESTATE ══════════════════════
    {"org": "Redfin - Data", "email": "businessdevelopment@redfin.com", "sector": "Real Estate"},
    {"org": "Realtor.com - Data", "email": "data@realtor.com", "sector": "Real Estate"},
    {"org": "Compass - Data", "email": "data@compass.com", "sector": "Real Estate"},
    {"org": "Zillow - Industry Relations", "email": "industryrelations@zillow.com", "sector": "Real Estate"},
    {"org": "Keller Williams - Data", "email": "data@kw.com", "sector": "Real Estate"},
    {"org": "RE/MAX - Data", "email": "datalicensing@remax.com", "sector": "Real Estate"},
    {"org": "CBRE - Data Solutions", "email": "data.solutions@cbre.com", "sector": "Real Estate"},
    {"org": "JLL - Data", "email": "data@jll.com", "sector": "Real Estate"},
    {"org": "Cushman & Wakefield", "email": "data@cushwake.com", "sector": "Real Estate"},
    {"org": "Colliers - Data", "email": "data@colliers.com", "sector": "Real Estate"},
    {"org": "Newmark - Data", "email": "data@ngkf.com", "sector": "Real Estate"},
    {"org": "Opendoor - Data", "email": "data@opendoor.com", "sector": "Real Estate"},
    {"org": "Opendoor - Data Science", "email": "datascience@opendoor.com", "sector": "Real Estate"},
    {"org": "Offerpad - Data", "email": "info@offerpad.com", "sector": "Real Estate"},
    {"org": "Zillow - Research", "email": "research@zillow.com", "sector": "Real Estate"},

    #══════════════════════ HEDGE FUNDS / ALTERNATIVE DATA ══════════════════════
    {"org": "Bridgewater Associates", "email": "altdata@bridgewater.com", "sector": "Hedge Fund"},
    {"org": "Renaissance Technologies", "email": "data@rentec.com", "sector": "Hedge Fund"},
    {"org": "Two Sigma - Data", "email": "alternative-data@twosigma.com", "sector": "Hedge Fund"},
    {"org": "Citadel - Data", "email": "alternative.data@citadel.com", "sector": "Hedge Fund"},
    {"org": "D.E. Shaw - Data", "email": "data@deshaw.com", "sector": "Hedge Fund"},
    {"org": "Point72 - Data", "email": "altdata@point72.com", "sector": "Hedge Fund"},
    {"org": "AQR Capital - Data", "email": "data@aqr.com", "sector": "Hedge Fund"},
    {"org": "Millennium Management", "email": "data@millennium.com", "sector": "Hedge Fund"},
    {"org": "Blackstone - Data", "email": "data@blackstone.com", "sector": "Investment"},
    {"org": "BlackRock - Data", "email": "alternative.data@blackrock.com", "sector": "Investment"},
    {"org": "Vanguard - Data", "email": "data@vanguard.com", "sector": "Investment"},
    {"org": "Fidelity - Data", "email": "altdata@fidelity.com", "sector": "Investment"},
    {"org": "State Street - Data", "email": "data@statestreet.com", "sector": "Investment"},
    {"org": "PIMCO - Data", "email": "altdata@pimco.com", "sector": "Investment"},
    {"org": "Tiger Global - Data", "email": "data@tigerglobal.com", "sector": "Hedge Fund"},
    {"org": "Jane Street - Data", "email": "data@janestreet.com", "sector": "Hedge Fund"},
    {"org": "Jump Trading - Data", "email": "data@jumptrading.com", "sector": "Hedge Fund"},
    {"org": "Hudson River Trading", "email": "data@hudsonrivertrading.com", "sector": "Hedge Fund"},
    {"org": "DRW - Data", "email": "data@drw.com", "sector": "Hedge Fund"},
    {"org": "Susquehanna - Data", "email": "data@sig.com", "sector": "Hedge Fund"},
    {"org": "GSA Capital - Data", "email": "data@gsacapital.com", "sector": "Hedge Fund"},
    {"org": "WorldQuant - Data", "email": "data@worldquant.com", "sector": "Hedge Fund"},
    {"org": "Man AHL - Data", "email": "data@man.com", "sector": "Hedge Fund"},
    {"org": "Winton Group - Data", "email": "data@winton.com", "sector": "Hedge Fund"},
    {"org": "Quadratic Capital", "email": "data@quadratic.com", "sector": "Hedge Fund"},

    #══════════════════════ CONSULTING / MARKET RESEARCH ══════════════════════
    {"org": "McKinsey - Data", "email": "data@mckinsey.com", "sector": "Consulting"},
    {"org": "BCG - Data", "email": "data@bcg.com", "sector": "Consulting"},
    {"org": "Bain - Data", "email": "data@bain.com", "sector": "Consulting"},
    {"org": "Deloitte - Data", "email": "data@deloitte.com", "sector": "Consulting"},
    {"org": "EY - Data", "email": "data@ey.com", "sector": "Consulting"},
    {"org": "PwC - Data", "email": "data@pwc.com", "sector": "Consulting"},
    {"org": "KPMG - Data", "email": "data@kpmg.com", "sector": "Consulting"},
    {"org": "Accenture - Data", "email": "data@accenture.com", "sector": "Consulting"},
    {"org": "Nielsen - Data", "email": "data.sales@nielsen.com", "sector": "Market Research"},
    {"org": "Ipsos - Data", "email": "data@ipsos.com", "sector": "Market Research"},
    {"org": "Kantar - Data", "email": "data@kantar.com", "sector": "Market Research"},
    {"org": "Gallup - Data", "email": "data@gallup.com", "sector": "Market Research"},
    {"org": "YouGov - Data", "email": "data@yougov.com", "sector": "Market Research"},
    {"org": "Morning Consult", "email": "data@morningconsult.com", "sector": "Market Research"},
    {"org": "Echelon Insights", "email": "info@echeloninsights.com", "sector": "Market Research"},
    {"org": "CivicScience", "email": "data@civicscience.com", "sector": "Market Research"},
    {"org": "Catalist - Data", "email": "press@catalist.us", "sector": "Political Data"},
    {"org": "TargetSmart - Data", "email": "sales@targetsmart.com", "sector": "Political Data"},
    {"org": "Grassroots Analytics", "email": "sales@grassrootsanalytics.com", "sector": "Political Data"},
    {"org": "i360 - Data", "email": "support@i-360.com", "sector": "Political Data"},
    {"org": "L2 Data", "email": "info@L2-data.com", "sector": "Political Data"},
    {"org": "Aristotle - Data", "email": "info@aristotle.com", "sector": "Political Data"},

    #══════════════════════ MEDIA / JOURNALISM ══════════════════════
    {"org": "NYT - Data Journalism", "email": "datateam@nytimes.com", "sector": "Media"},
    {"org": "Washington Post - Data", "email": "data@washingtonpost.com", "sector": "Media"},
    {"org": "AP - Religion Team", "email": "religion@ap.org", "sector": "Media"},
    {"org": "Bloomberg - Data", "email": "data@bloomberg.net", "sector": "Media"},
    {"org": "Reuters - Data", "email": "data@reuters.com", "sector": "Media"},
    {"org": "The Economist - Data", "email": "data@economist.com", "sector": "Media"},
    {"org": "WSJ - Data", "email": "data@wsj.com", "sector": "Media"},
    {"org": "CNN - Data", "email": "data@cnn.com", "sector": "Media"},
    {"org": "Axios - Data", "email": "data@axios.com", "sector": "Media"},
    {"org": "Religion News Service", "email": "info@religionnews.com", "sector": "Media"},
    {"org": "Christianity Today", "email": "editor@christianitytoday.com", "sector": "Media"},
    {"org": "The Gospel Coalition", "email": "info@thegospelcoalition.org", "sector": "Media"},
    {"org": "Our Daily Bread", "email": "info@odb.org", "sector": "Media"},
    {"org": "Focus on the Family", "email": "info@focusonthefamily.com", "sector": "Media"},

    #══════════════════════ UNIV / RESEARCH INSTITUTES ══════════════════════
    {"org": "Harvard - Religion Data", "email": "data@hds.harvard.edu", "sector": "Academic"},
    {"org": "Princeton - Religion", "email": "data@princeton.edu", "sector": "Academic"},
    {"org": "Yale - Religion", "email": "data@yale.edu", "sector": "Academic"},
    {"org": "Stanford - Religion", "email": "data@stanford.edu", "sector": "Academic"},
    {"org": "University of Chicago", "email": "data@uchicago.edu", "sector": "Academic"},
    {"org": "Duke - Religion", "email": "data@duke.edu", "sector": "Academic"},
    {"org": "Notre Dame - Religion", "email": "data@nd.edu", "sector": "Academic"},
    {"org": "Boston University Religion", "email": "data@bu.edu", "sector": "Academic"},
    {"org": "Pew Research Center", "email": "info@pewresearch.org", "sector": "Research"},
    {"org": "ARDA (Penn State)", "email": "arda@psu.edu", "sector": "Research"},
    {"org": "Barna Group", "email": "info@barna.com", "sector": "Research"},
    {"org": "PRRI", "email": "info@prri.org", "sector": "Research"},
    {"org": "Hartford Institute", "email": "hirr@hartsem.edu", "sector": "Research"},
    {"org": "Lilly Endowment", "email": "communications@lei.org", "sector": "Foundation"},
    {"org": "Pew Charitable Trusts", "email": "info@pewtrusts.org", "sector": "Foundation"},
    {"org": "Templeton Foundation", "email": "info@templeton.org", "sector": "Foundation"},

    #══════════════════════ NATHAN HALE, RONIN, ETC ══════════════════════
    {"org": "Experian - Data", "email": "contactems@experian.com", "sector": "Data Broker"},
    {"org": "TransUnion - Data", "email": "data@transunion.com", "sector": "Data Broker"},
    {"org": "Equifax - Data", "email": "data.solutions@equifax.com", "sector": "Data Broker"},
    {"org": "Dun & Bradstreet", "email": "datapartners@dnb.com", "sector": "Data Broker"},
    {"org": "SafeGraph - Data", "email": "data@safegraph.com", "sector": "Data Broker"},
    {"org": "Foursquare - Data", "email": "partnerships@foursquare.com", "sector": "Data Broker"},
    {"org": "Mapbox - Data", "email": "sales@mapbox.com", "sector": "Data Broker"},
    {"org": "Claritas - Data", "email": "info@claritas.com", "sector": "Data Broker"},
    {"org": "Verisk - Data", "email": "info@verisk.com", "sector": "Data Broker"},
    {"org": "CoreLogic - Data", "email": "data@corelogic.com", "sector": "Data Broker"},
    {"org": "LightBox - Data", "email": "info@lightbox.com", "sector": "Data Broker"},
    {"org": "Regrid - Data", "email": "hello@regrid.com", "sector": "Data Broker"},

    #══════════════════════ ACADEMIC PRESS / PUBLISHERS ══════════════════════
    {"org": "Oxford University Press", "email": "data@oup.com", "sector": "Publishing"},
    {"org": "Cambridge University Press", "email": "data@cambridge.org", "sector": "Publishing"},
    {"org": "Brill Publishers", "email": "info@brill.com", "sector": "Publishing"},
    {"org": "De Gruyter", "email": "info@degruyter.com", "sector": "Publishing"},
    {"org": "Springer Nature", "email": "data@springernature.com", "sector": "Publishing"},
    {"org": "Zondervan / HarperCollins", "email": "info@zondervan.com", "sector": "Publishing"},
    {"org": "Thomas Nelson", "email": "info@thomasnelson.com", "sector": "Publishing"},
    {"org": "IVP Academic", "email": "info@ivpress.com", "sector": "Publishing"},
    {"org": "Baker Academic", "email": "info@bakerpublishing.com", "sector": "Publishing"},
    {"org": "Fortress Press", "email": "info@fortresspress.com", "sector": "Publishing"},
    {"org": "Eerdmans Publishing", "email": "info@eerdmans.com", "sector": "Publishing"},

    #══════ MORE INSURANCE ══════
    {"org": "MetLife - Data", "email": "data@metlife.com", "sector": "Insurance"},
    {"org": "Prudential - Data", "email": "data@prudential.com", "sector": "Insurance"},
    {"org": "New York Life - Data", "email": "data@newyorklife.com", "sector": "Insurance"},
    {"org": "MassMutual - Data", "email": "data@massmutual.com", "sector": "Insurance"},
    {"org": "Northwestern Mutual", "email": "data@northwesternmutual.com", "sector": "Insurance"},
    {"org": "Guardian Life - Data", "email": "data@guardianlife.com", "sector": "Insurance"},
    {"org": "Mutual of Omaha", "email": "info@mutualofomaha.com", "sector": "Insurance"},
    {"org": "Thrivent - Data", "email": "data@thrivent.com", "sector": "Insurance"},
    {"org": "COUNTRY Financial", "email": "info@countryfinancial.com", "sector": "Insurance"},
    {"org": "Amica Mutual", "email": "info@amica.com", "sector": "Insurance"},
    {"org": "EMC Insurance", "email": "info@emcins.com", "sector": "Insurance"},
    {"org": "West Bend Mutual", "email": "info@westbend.com", "sector": "Insurance"},
    {"org": "SECURA Insurance", "email": "info@secura.net", "sector": "Insurance"},
    {"org": "Acuity Insurance", "email": "info@acuity.com", "sector": "Insurance"},
    {"org": "IAT Insurance Group", "email": "info@iatinsurance.com", "sector": "Insurance"},
    {"org": "Pie Insurance", "email": "hello@pieinsurance.com", "sector": "Insurance"},
    {"org": "Next Insurance", "email": "info@nextinsurance.com", "sector": "Insurance"},

    #══════ ALT DATA / HEDGE FUNDS ══════
    {"org": "Neudata - Data Marketplace", "email": "info@neudata.com", "sector": "Alt Data"},
    {"org": "BattleFin - Data", "email": "info@battlefin.com", "sector": "Alt Data"},
    {"org": "YipitData", "email": "info@yipitdata.com", "sector": "Alt Data"},
    {"org": "Thinknum - Data", "email": "info@thinknum.com", "sector": "Alt Data"},
    {"org": "M Science - Data", "email": "info@mscience.com", "sector": "Alt Data"},
    {"org": "Consumer Edge - Data", "email": "info@consumeredge.com", "sector": "Alt Data"},
    {"org": "Quandl / Nasdaq Data", "email": "data@nasdaq.com", "sector": "Alt Data"},
    {"org": "Eagle Alpha", "email": "info@eaglealpha.com", "sector": "Alt Data"},
    {"org": "UBS Evidence Lab", "email": "evidencelab@ubs.com", "sector": "Alt Data"},
    {"org": "Cortex - Data", "email": "data@cortex.com", "sector": "Alt Data"},
    {"org": "QuantConnect", "email": "info@quantconnect.com", "sector": "Hedge Fund"},
    {"org": "Quantopian", "email": "info@quantopian.com", "sector": "Hedge Fund"},
    {"org": "Cubist Systematic", "email": "data@cubist.com", "sector": "Hedge Fund"},
    {"org": "Squarepoint Capital", "email": "data@squarepoint.com", "sector": "Hedge Fund"},
    {"org": "Walleye Capital", "email": "data@walleyecapital.com", "sector": "Hedge Fund"},
    {"org": "Verition Fund Management", "email": "data@verition.com", "sector": "Hedge Fund"},
    {"org": "BlueCrest Capital", "email": "data@bluecrest.com", "sector": "Hedge Fund"},
    {"org": "Brevan Howard", "email": "data@brevanhoward.com", "sector": "Hedge Fund"},
    {"org": "Caxton Associates", "email": "data@caxton.com", "sector": "Hedge Fund"},
    {"org": "Moore Capital", "email": "data@moorecap.com", "sector": "Hedge Fund"},
    {"org": "LMR Partners", "email": "data@lmrpartners.com", "sector": "Hedge Fund"},
    {"org": "Element Capital", "email": "data@elementcapital.com", "sector": "Hedge Fund"},

    #══════ CHURCH MANAGEMENT SOFTWARE ══════
    {"org": "Ministry Brands", "email": "info@ministrybrands.com", "sector": "ChMS"},
    {"org": "Subsplash", "email": "info@subsplash.com", "sector": "ChMS"},
    {"org": "FellowshipOne", "email": "info@fellowshipone.com", "sector": "ChMS"},
    {"org": "Vanco Payment", "email": "info@vancopay.com", "sector": "ChMS"},
    {"org": "Servant Keeper", "email": "info@servantkeeper.com", "sector": "ChMS"},
    {"org": "Churchteams", "email": "info@churchteams.com", "sector": "ChMS"},
    {"org": "ChMeetings", "email": "info@chmeetings.com", "sector": "ChMS"},
    {"org": "FaithTeams", "email": "info@faithteams.com", "sector": "ChMS"},
    {"org": "ChurchTrac", "email": "info@churchtrac.com", "sector": "ChMS"},

    #══════ DENOMINATION HQS ══════
    {"org": "USCCB - Catholic HQ", "email": "communications@usccb.org", "sector": "Denom HQ"},
    {"org": "SBC Executive Committee", "email": "info@sbc.net", "sector": "Denom HQ"},
    {"org": "ELCA Churchwide", "email": "info@elca.org", "sector": "Denom HQ"},
    {"org": "PCUSA General Assembly", "email": "info@pcusa.org", "sector": "Denom HQ"},
    {"org": "UMC Council of Bishops", "email": "info@umc.org", "sector": "Denom HQ"},
    {"org": "AME Church", "email": "info@ame-church.com", "sector": "Denom HQ"},
    {"org": "ABCUSA National Offices", "email": "info@abc-usa.org", "sector": "Denom HQ"},
    {"org": "Cooperative Baptist", "email": "info@cbf.org", "sector": "Denom HQ"},
    {"org": "Episcopal Church HQ", "email": "info@episcopalchurch.org", "sector": "Denom HQ"},
    {"org": "Presbyterian Church USA", "email": "info@pcusa.org", "sector": "Denom HQ"},
    {"org": "United Church of Christ", "email": "info@ucc.org", "sector": "Denom HQ"},
    {"org": "Church of God (Cleveland)", "email": "info@churchofgod.org", "sector": "Denom HQ"},
    {"org": "Assemblies of God HQ", "email": "info@ag.org", "sector": "Denom HQ"},
    {"org": "Nazarene Global HQ", "email": "info@nazarene.org", "sector": "Denom HQ"},
    {"org": "Salvation Army Natl HQ", "email": "info@salvationarmyusa.org", "sector": "Denom HQ"},

    #══════ RELIGIOUS MEDIA ══════
    {"org": "TBN - Trinity Broadcasting", "email": "info@tbn.org", "sector": "Media"},
    {"org": "EWTN Global Catholic", "email": "info@ewtn.com", "sector": "Media"},
    {"org": "CBN - Christian Broadcasting", "email": "info@cbn.com", "sector": "Media"},
    {"org": "K-LOVE / Air1", "email": "info@klove.com", "sector": "Media"},
    {"org": "Daystar Television", "email": "info@daystar.com", "sector": "Media"},

    #══════ GEO/GIS ══════
    {"org": "Precisely - Data", "email": "data@precisely.com", "sector": "GIS"},
    {"org": "Nearmap - Data", "email": "data@nearmap.com", "sector": "GIS"},
    {"org": "Descartes Labs", "email": "info@descarteslabs.com", "sector": "GIS"},
    {"org": "Maxar - Data", "email": "data@maxar.com", "sector": "GIS"},
    {"org": "Planet Labs - Data", "email": "data@planet.com", "sector": "GIS"},

    #══════ DISASTER RELIEF ══════
    {"org": "Team Rubicon", "email": "info@teamrubiconusa.org", "sector": "Disaster"},
    {"org": "Direct Relief", "email": "info@directrelief.org", "sector": "Disaster"},
    {"org": "Convoy of Hope", "email": "info@convoyofhope.org", "sector": "Disaster"},
    {"org": "American Red Cross", "email": "data@redcross.org", "sector": "Disaster"},
    {"org": "World Food Programme", "email": "data@wfp.org", "sector": "Disaster"},

    #══════ ESG / FINANCIAL DATA ══════
    {"org": "MSCI ESG Research", "email": "esg@msci.com", "sector": "Finance"},
    {"org": "Sustainalytics", "email": "info@sustainalytics.com", "sector": "Finance"},
    {"org": "ISS ESG", "email": "esg@issgovernance.com", "sector": "Finance"},
    {"org": "Bloomberg ESG", "email": "esg@bloomberg.net", "sector": "Finance"},
    {"org": "S&P Global - Data", "email": "data@spglobal.com", "sector": "Finance"},
    {"org": "Moody's Analytics", "email": "data@moodys.com", "sector": "Finance"},
    {"org": "Fitch Ratings", "email": "data@fitchratings.com", "sector": "Finance"},
    {"org": "Oxford Economics", "email": "data@oxfordeconomics.com", "sector": "Finance"},
    {"org": "Moody's ESG", "email": "esg@moodys.com", "sector": "Finance"},
    {"org": "Refinitiv / LSEG", "email": "data@lseg.com", "sector": "Finance"},

    #══════ THINK TANKS ══════
    {"org": "Brookings Institution", "email": "data@brookings.edu", "sector": "Think Tank"},
    {"org": "AEI - American Enterprise", "email": "info@aei.org", "sector": "Think Tank"},
    {"org": "Heritage Foundation", "email": "info@heritage.org", "sector": "Think Tank"},
    {"org": "RAND Corporation", "email": "data@rand.org", "sector": "Think Tank"},
    {"org": "Urban Institute", "email": "data@urban.org", "sector": "Think Tank"},
    {"org": "Niskanen Center", "email": "info@niskanencenter.org", "sector": "Think Tank"},
    {"org": "Pew Research Center", "email": "info@pewresearch.org", "sector": "Think Tank"},
    {"org": "PRRI - Public Religion", "email": "info@prri.org", "sector": "Think Tank"},

    #══════ DENOM FINANCIAL ══════
    {"org": "Christian Community CU", "email": "info@mycccu.com", "sector": "Financial"},
    {"org": "Evangelical Christian CU", "email": "info@eccu.org", "sector": "Financial"},
    {"org": "Church Extension Plan", "email": "info@cep.com", "sector": "Financial"},
]

# Deduplicate by email
seen = set()
unique_whales = []
for w in WHALES:
    if w['email'] not in seen:
        seen.add(w['email'])
        unique_whales.append(w)

print(f"Total unique whales: {len(unique_whales)}")

# Load already sent
already_sent = set()
if SENT_LOG.exists():
    for line in SENT_LOG.read_text().strip().split('\n'):
        if line.strip():
            already_sent.add(line.strip().lower().split(',')[0].strip())
if WHALE_SENT.exists():
    for line in WHALE_SENT.read_text().strip().split('\n'):
        if line.strip():
            already_sent.add(line.strip())

# Filter: not already sent, has GMAIL_APP_PASSWORD
emails = [w for w in unique_whales if w['org'].lower() not in already_sent and w['email'] not in already_sent]
print(f"Not yet sent: {len(emails)}")
print(f"\nSectors:")
from collections import Counter
for s, n in Counter(w['sector'] for w in emails).most_common():
    print(f"  {s}: {n}")

# ── Build email body ──
BODY_TEMPLATE = f"""Hi {{{{org}}}} team,

GRID (Global Religious Infrastructure Database) maps 3.48M worship sites globally -- every church, mosque, temple, synagogue, and shrine -- with GPS coordinates and the FTLM taxonomy (Civilization > Faith > Legacy > Tradition > Movement).

We've joined FEMA National Risk Index scores (18 hazard types at the census tract level) to every US church, making this both a location dataset and a property risk dataset.

**What's in it:**
- 1.07M US sites, 91% with GPS
- FTLM: 12 faiths, 1,066 traditions, 300+ movements
- FEMA risk: 18 hazards (hurricane, tornado, flood, wildfire, earthquake...)
- FBI crime: state-level 1979-2024 + agency-level 2024
- 10 Census geographic layers (tract, block group, CD, ZIP, etc.)
- 9 denomination hierarchies (163K parent-child relationships)
- 337K websites, 46K phones, 16K emails
- 1.8M enrichment changes with full provenance tracking

**Vermont sample (free, view-only):** {BQ}

**Buy on AWS Data Exchange (sample included free):** {ADX}

Happy to discuss custom extracts, enterprise licensing, or API access.

{SIG}"""

# ── Queue & SEND ──
def send_email(to_addr, subject, body):
    msg = MIMEMultipart()
    msg["From"] = FROM
    msg["To"] = to_addr
    msg["Reply-To"] = "charlesaprescott@outlook.com"
    msg["Disposition-Notification-To"] = FROM
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as s:
        s.starttls()
        s.login("charlesaprescottjr@gmail.com", PWD)
        s.send_message(msg)

if not PWD:
    print("GMAIL_APP_PASSWORD not set")
    exit(1)

SUBJECT = "GRID: 3.48M worship sites with FEMA risk scores -- on AWS Data Exchange"

ok = fail = 0
for i, w in enumerate(emails):
    body = BODY_TEMPLATE.replace('{{org}}', w['org'])
    subject = f"{SUBJECT}"
    print(f"\n[{i+1}/{len(emails)}] {w['org']:40s} -> {w['email']:35s}", end="", flush=True)
    try:
        send_email(w['email'], subject, body)
        ok += 1
        with open(WHALE_SENT, "a") as f:
            f.write(f"{w['org']}\n{w['email']}\n")
        print(f" OK ({ok}/{fail})")
    except Exception as e:
        fail += 1
        print(f" FAIL: {str(e)[:60]}")
        with open(FAIL_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()},{w['org']},{w['email']},{e}\n")

    # Rate limit
    if i < len(emails) - 1:
        print(f"  Waiting {INTERVAL//60}min...", end="", flush=True)
        time.sleep(INTERVAL)

print(f"\n\nDone: {ok} sent, {fail} failed")
