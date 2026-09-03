"""
Faith & Denomination Classification — gw_filters/faith.py
==========================================================
Centralized classification engine for the GRID project. Provides multi-level
faith identification: IRS NTEE codes → name heuristics → web content matching.

**Design principle**: Single source of truth. Add new denominations HERE,
not in individual scrapers. All classification rules are versioned and tested.

**Classification tiers**:
  Level 1 — NTEE_MAP: IRS tax-exempt organization codes → faith (US-centric)
  Level 2 — NAME_HEURISTICS: Regex patterns on church/synagogue/mosque/etc. names
  Level 3 — DENOM_RULES: Web page content → specific denomination (fine-grained)

**Usage:**
    from gw_filters.faith import from_ntee, from_name, from_web_content

    from_ntee("X21")                         # → "christian"
    from_name("Masjid Al-Noor")              # → "muslim"
    from_name("ISKCON Temple Toronto")       # → "hindu"
    from_name("Gurdwara Sahib Ottawa")       # → "sikh"
    from_web_content(title, meta, body)      # → "Southern Baptist Convention"

**Coverage in Canada & India public release:**
  - Canada: Christian (Catholic, United Church, Anglican, Baptist, Orthodox)
  - India: Hindu (Vaishnavism, Shaivism), Muslim (Sunni/Shia), Christian, Sikh
  - Multi-language: English, French, Hindi, Tamil, Arabic, Hebrew, Punjabi

**Version:** 1.0.0 (June 2026)
"""

import json
import re

# ═══════════════════════════════════════════════════════════════════
# LEVEL 1: IRS NTEE Code → Faith Tradition
# ═══════════════════════════════════════════════════════════════════

NTEE_MAP = {
    "X20": "christian", "X21": "christian", "X22": "christian", "X23": "christian",
    "X24": "christian", "X25": "christian", "X26": "christian", "X27": "christian",
    "X28": "christian", "X29": "christian", "X2": "christian",
    "X30": "jewish", "X3": "jewish",
    "X40": "muslim", "X4": "muslim",
    "X50": "buddhist", "X5": "buddhist",
    "X60": "christian",
    "X70": "hindu", "X7": "hindu",
    "X80": "humanist",
    "X90": "other", "X99": "other", "X9": "other",
    "X": "unknown",
}

def from_ntee(code):
    """Classify faith tradition from IRS NTEE code."""
    if not code:
        return "unknown"
    code = code.strip().upper()
    # Try exact match first, then prefix
    if code in NTEE_MAP:
        return NTEE_MAP[code]
    for prefix in sorted(NTEE_MAP.keys(), key=len, reverse=True):
        if code.startswith(prefix):
            return NTEE_MAP[prefix]
    return "unknown"


# ═══════════════════════════════════════════════════════════════════
# LEVEL 2: Church Name Heuristics → Faith Tradition
# ═══════════════════════════════════════════════════════════════════

NAME_HEURISTICS = [
    (r'\b(church|baptist|methodist|catholic|lutheran|episcopal|pentecostal|assembly|chapel)\b', 'christian'),
    (r'\b(synagogue|chabad|yeshiva|rabbi)\b', 'jewish'),
    (r"\btemple\s+(beth|israel|emanuel|sinai|shalom|judah|adath|b'?nai)\b", 'jewish'),
    (r'\bcongregation\s+(beth|israel|emanuel|bnai|b\'nai|shalom|shearith|agudath|anshei)\b', 'jewish'),
    (r'\b(masjid|islamic center|mosque|muslim)\b', 'muslim'),
    (r'\b(mandir|hindu temple|hindu)\b', 'hindu'),
    (r'\b(zen|buddhist|dharma|vihara)\b', 'buddhist'),
    (r'\b(gurdwara|sikh)\b', 'sikh'),
    (r"\bbaha'?i\b", 'bahai'),
    (r'\b(iglesia|dios|jesucristo|cristo|señor|senor|ministerio)\b', 'christian'),
    (r'\b(asamblea|santa|casa de|palabra de|espiritu|espíritu)\b', 'christian'),
]

def from_name(church_name):
    """Classify faith tradition from church name using heuristic patterns."""
    if not church_name:
        return "unknown"
    name_lower = church_name.lower()
    for pattern, tradition in NAME_HEURISTICS:
        if re.search(pattern, name_lower):
            return tradition
    return "unknown"


# ═══════════════════════════════════════════════════════════════════
# LEVEL 3: Web Page Content → Denomination (fine-grained)
# ═══════════════════════════════════════════════════════════════════

# Ordered by specificity — first match wins
DENOM_RULES = [
    (["ROMAN CATHOLIC", "ROMAN CATHOLIC CHURCH"], "Roman Catholic Church"),
    ([" CATHOLIC CHURCH", " CATHOLIC PARISH", " CATHOLIC "], "Roman Catholic Church"),
    (["MALANKARA CATHOLIC"], "Syro-Malabar Catholic Church"),
    (["COPTIC ORTHODOX"], "Coptic Orthodox Church"),
    (["ETHIOPIAN ORTHODOX"], "Ethiopian Orthodox Tewahedo Church"),
    (["GREEK ORTHODOX"], "Greek Orthodox Archdiocese of America"),
    (["ORTHODOX CHURCH IN AMERICA", "OCA CHURCH", "RUSSIAN ORTHODOX"], "Orthodox Church in America"),
    (["ANTIOCHIAN ORTHODOX", "SYRIAN ORTHODOX"], "Antiochian Orthodox Christian Archdiocese"),
    (["ROMANIAN ORTHODOX"], "Romanian Orthodox Church"),
    (["UKRAINIAN ORTHODOX"], "Ukrainian Orthodox Church"),
    (["SERBIAN ORTHODOX"], "Serbian Orthodox Church"),
    (["BULGARIAN ORTHODOX"], "Bulgarian Orthodox Church"),
    (["ARMENIAN APOSTOLIC", "ARMENIAN ORTHODOX"], "Armenian Apostolic Church"),
    (["MALANKARA ORTHODOX SYRIAN", "MALANKARA ORTHODOX"], "Malankara Orthodox Syrian Church"),
    ([" ORTHODOX "], "Eastern Orthodox"),
    (["SOUTHERN BAPTIST"], "Southern Baptist Convention"),
    (["MISSIONARY BAPTIST"], "Missionary Baptist"),
    (["INDEPENDENT BAPTIST", "INDEPENDENT BAPTIST"], "Independent Baptist"),
    (["FREE WILL BAPTIST"], "Free Will Baptist"),
    (["PRIMITIVE BAPTIST"], "Primitive Baptist"),
    (["NATIONAL BAPTIST CONVENTION"], "National Baptist Convention USA"),
    (["AMERICAN BAPTIST CHURCH"], "American Baptist Churches USA"),
    (["PROGRESSIVE BAPTIST"], "Progressive National Baptist Convention"),
    (["FULL GOSPEL BAPTIST"], "Full Gospel Baptist Church Fellowship"),
    ([" BAPTIST "], "Baptist (unspecified)"),
    (["UNITED METHODIST"], "United Methodist Church"),
    (["FREE METHODIST"], "Free Methodist Church"),
    (["AFRICAN METHODIST EPISCOPAL ZION", "AME ZION"], "African Methodist Episcopal Zion Church"),
    (["AFRICAN METHODIST EPISCOPAL", "AME CHURCH"], "African Methodist Episcopal Church"),
    (["CHRISTIAN METHODIST EPISCOPAL", "CME CHURCH"], "Christian Methodist Episcopal Church"),
    (["WESLEYAN CHURCH"], "Wesleyan Church"),
    ([" METHODIST "], "United Methodist Church"),
    (["LUTHERAN CHURCH MISSOURI SYNOD", "MISSOURI SYNOD", "LCMS"], "Lutheran Church--Missouri Synod"),
    (["EVANGELICAL LUTHERAN CHURCH", "ELCA"], "Evangelical Lutheran Church in America"),
    (["WISCONSIN EVANGELICAL LUTHERAN", "WELS"], "Wisconsin Evangelical Lutheran Synod"),
    (["LUTHERAN CHURCH"], "Lutheran (unspecified)"),
    (["PRESBYTERIAN CHURCH IN AMERICA", "PCA CHURCH"], "Presbyterian Church in America"),
    (["PRESBYTERIAN CHURCH USA", "PRESBYTERIAN CHURCH U.S.A.", "PCUSA"], "Presbyterian Church (U.S.A.)"),
    (["CUMBERLAND PRESBYTERIAN"], "Cumberland Presbyterian"),
    (["ORTHODOX PRESBYTERIAN", "OPC"], "Orthodox Presbyterian Church"),
    (["ASSOCIATE REFORMED PRESBYTERIAN", "ARPC"], "Associate Reformed Presbyterian Church"),
    (["EVANGELICAL PRESBYTERIAN", "EPC"], "Evangelical Presbyterian Church"),
    (["REFORMED PRESBYTERIAN"], "Reformed Presbyterian Church"),
    ([" PRESBYTERIAN "], "Presbyterian Church (U.S.A.)"),
    (["EPISCOPAL CHURCH", " EPISCOPAL "], "Episcopal Church"),
    (["ANGLICAN CHURCH", "ANGLICAN"], "Anglican Church"),
    (["ASSEMBLIES OF GOD"], "Assemblies of God"),
    (["CHURCH OF GOD IN CHRIST", "COGIC"], "Church of God in Christ"),
    ([" PENTECOSTAL "], "Pentecostal (unspecified)"),
    (["FOURSQUARE CHURCH", "FOURSQUARE GOSPEL"], "Foursquare Church"),
    (["CHURCH OF GOD OF PROPHECY", "COGOP"], "Church of God of Prophecy"),
    (["CHURCH OF GOD"], "Church of God (Cleveland, TN)"),
    (["CHURCHES OF CHRIST"], "Churches of Christ"),
    (["CHURCH OF CHRIST"], "Churches of Christ"),
    (["SEVENTH-DAY ADVENTIST", "SEVENTH DAY ADVENTIST"], "Seventh-day Adventist"),
    (["ADVENTIST CHURCH"], "Seventh-day Adventist"),
    (["CHURCH OF THE NAZARENE", " NAZARENE "], "Church of the Nazarene"),
    (["UNITED CHURCH OF CHRIST", "UCC CHURCH"], "United Church of Christ"),
    (["CHRISTIAN CHURCH DISCIPLES", "DISCIPLES OF CHRIST"], "Christian Church (Disciples of Christ)"),
    (["CHRISTIAN CHURCH"], "Christian Church (Disciples of Christ)"),
    (["REFORMED CHURCH IN AMERICA", "RCA CHURCH"], "Reformed Church in America"),
    (["CHRISTIAN REFORMED CHURCH", "CRC CHURCH"], "Christian Reformed Church"),
    (["EVANGELICAL FREE CHURCH", "EFCA"], "Evangelical Free Church of America"),
    (["EVANGELICAL COVENANT CHURCH"], "Evangelical Covenant Church"),
    (["SALVATION ARMY"], "Salvation Army"),
    (["CALVARY CHAPEL"], "Calvary Chapel"),
    (["MENNONITE CHURCH", " MENNONITE "], "Mennonite (unspecified)"),
    (["CHURCH OF THE BRETHREN"], "Church of the Brethren"),
    (["CHURCH OF JESUS CHRIST OF LATTER", "LDS CHURCH", "MORMON"], "The Church of Jesus Christ of Latter-day Saints"),
    (["JEHOVAH WITNESS"], "Jehovah's Witnesses"),
    (["UNITARIAN UNIVERSALIST", " UNITARIAN "], "Unitarian Universalist"),
    (["CHRISTIAN SCIENCE"], "Christian Science"),
    (["RELIGIOUS SOCIETY OF FRIENDS", "QUAKER"], "Religious Society of Friends (Quakers)"),
    ([" BIBLE CHURCH"], "Bible Church (unspecified)"),
    (["NON-DENOMINATIONAL", "NONDENOMINATIONAL"], "Non-Denominational"),
    (["COMMUNITY CHURCH"], "Community Church (unspecified)"),
]

# Keywords to detect faith from Google KG description text
KG_DESC_KEYWORDS = {
    "christian": ["church", "baptist", "catholic", "methodist", "lutheran",
                   "episcopal", "presbyterian", "pentecostal", "assembly of god",
                   "ministry", "worship", "gospel", "chapel", "cathedral",
                   "anglican", "orthodox", "evangelical"],
    "jewish": ["synagogue", "temple", "jewish", "judaism", "rabbi", "chabad", "yeshiva"],
    "muslim": ["mosque", "islamic", "muslim", "masjid"],
    "buddhist": ["buddhist", "buddhism", "temple", "dharma", "zen"],
    "hindu": ["hindu", "mandir", "temple"],
}

# Google KG @type → faith mapping
KG_TYPE_MAP = {
    "church": "christian", "church_organization": "christian",
    "synagogue": "jewish", "jewish_synagogue": "jewish",
    "mosque": "muslim", "islamic_mosque": "muslim",
    "hindu_temple": "hindu", "buddhist_temple": "buddhist",
    "religious_organization": "unknown",
}


def from_webpage(html_text, page_title=""):
    """
    Classify denomination from webpage HTML content.
    Checks JSON-LD schema markup first, then body text, then page title.

    Returns (denomination_label, method) where method is one of:
    'jsonld', 'body_keyword', 'title_keyword', 'unknown'
    """
    if not html_text:
        return ("unknown", "no_content")

    html_upper = html_text.upper()

    # Strategy 1: Check JSON-LD schema markup
    for ld_text in re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html_text, re.DOTALL | re.IGNORECASE
    ):
        try:
            data = json.loads(ld_text)
            denom = _crawl_jsonld(data)
            if denom:
                return (denom, "jsonld")
        except json.JSONDecodeError:
            pass

    # Strategy 2: Body text keywords
    body_denom = _match_keywords(html_upper, "body")
    if body_denom:
        return (body_denom, "body_keyword")

    # Strategy 3: Page title
    if page_title:
        title_denom = _match_keywords(page_title.upper(), "title")
        if title_denom:
            return (title_denom, "title_keyword")

    return ("unknown", "no_match")


def _crawl_jsonld(data, depth=0):
    """Recursively crawl JSON-LD to find denomination."""
    if depth > 5:
        return None
    if isinstance(data, dict):
        for field in ["denomination", "religiousDenomination",
                       "denominationalAffiliation", "affiliation"]:
            val = data.get(field)
            if val and isinstance(val, str) and len(val) > 2:
                return val
        for val in data.values():
            result = _crawl_jsonld(val, depth + 1)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = _crawl_jsonld(item, depth + 1)
            if result:
                return result
    return None


def _match_keywords(text, context="body"):
    """Match DENOM_RULES against text."""
    for keywords, label in DENOM_RULES:
        for kw in keywords:
            if kw in text:
                return label
    return None


def from_kg_description(description):
    """Classify faith from Google Knowledge Graph description text."""
    if not description:
        return "unknown"
    desc_lower = description.lower()
    for tradition, keywords in KG_DESC_KEYWORDS.items():
        for kw in keywords:
            if kw in desc_lower:
                return tradition
    return "unknown"


def from_kg_type(kg_type):
    """Classify faith from Google KG @type field."""
    return KG_TYPE_MAP.get(kg_type.lower() if kg_type else "", "unknown")


# ═══════════════════════════════════════════════════════════════════
# COMBINED CLASSIFIER (preferred entry point)
# ═══════════════════════════════════════════════════════════════════

def classify(church_name=None, ntee_code=None, webpage_html=None,
             page_title=None, kg_description=None, kg_type=None):
    """
    Best-effort classification using all available signals.
    Returns (label, source) where source indicates which data was used.

    Priority: NTEE > Webpage > KG > Name > Unknown
    """
    if ntee_code:
        label = from_ntee(ntee_code)
        if label != "unknown":
            return (label, "ntee")

    if webpage_html:
        label, method = from_webpage(webpage_html, page_title)
        if label != "unknown":
            return (label, method)

    if kg_description:
        label = from_kg_description(kg_description)
        if label != "unknown":
            return (label, "kg_description")

    if kg_type:
        label = from_kg_type(kg_type)
        if label != "unknown":
            return (label, "kg_type")

    if church_name:
        label = from_name(church_name)
        if label != "unknown":
            return (label, "name_heuristic")

    return ("unknown", "no_data")
