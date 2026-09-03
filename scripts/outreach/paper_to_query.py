#!/usr/bin/env python3
"""
GrantWizard — Paper-to-Query Engine
====================================
Parses academic paper titles/abstracts and maps them to tailored SQL queries
against the churches database. Extracts three dimensions:

  1. FAITH TRADITION  → filters on family, faith_tradition, denomination
  2. GEOGRAPHY        → filters on state, region, urban/rural, metro area
  3. RESEARCH TOPIC   → selects enrichment columns, adds WHERE conditions

Returns a structured QuerySpec that the pipeline uses to generate samples.

Usage:
  from paper_to_query import extract_research_dimensions, build_query

  dims = extract_research_dimensions(title, abstract)
  query = build_query(dims, limit=12)
"""

import re
from dataclasses import dataclass, field
from typing import Optional

# ═══════════════════════════════════════════════════════════════════════════════
# FAITH TRADITION MAPPINGS
# ═══════════════════════════════════════════════════════════════════════════════

FAITH_PATTERNS = [
    # (regex, sql_where, label, priority)
    # Higher priority = checked first, wins on tie

    # ── Christian sub-families ──
    (r"\b(baptists?|southern baptist|sbc|black church(es)?|african american church(es)?|national baptist)\b",
     "c.family IN ('Baptist Churches')", "Baptist", 10),
    (r"\b(catholic|parish(es)?|diocese|archdiocese|roman catholic|vatican)\b",
     "c.family = 'Catholic Churches'", "Catholic", 11),
    (r"\b(pentecostal|charismatic|assemblies of god|a\/g|church of god in christ|cogic|foursquare)\b",
     "c.family IN ('Pentecostal Churches')", "Pentecostal", 10),
    (r"\b(methodist|united methodist|umc|wesleyan|ame|african methodist)\b",
     "c.family IN ('Methodist Churches')", "Methodist", 10),
    (r"\b(presbyterian|pcusa|pca|reformed)\b",
     "c.family IN ('Presbyterian Churches')", "Presbyterian", 10),
    (r"\b(lutheran|elca|lcms|missouri synod|wisconsin synod)\b",
     "c.family IN ('Lutheran Churches')", "Lutheran", 10),
    (r"\b(episcopal|anglican|ecusa|tec|anglo-catholic)\b",
     "c.family IN ('Episcopal and Anglican Churches')", "Episcopal/Anglican", 10),
    (r"\b(orthodox|greek orthodox|russian orthodox|oc[a-z]*|antiochian)\b",
     "c.family IN ('Orthodox Churches')", "Orthodox", 10),
    (r"\b(church of christ|churches of christ|restoration movement)\b",
     "c.family IN ('Churches of Christ')", "Churches of Christ", 10),
    (r"\b(nondenominational|non-denominational|independent christian)\b",
     "c.family IN ('Nondenominational Churches')", "Nondenominational", 10),
    (r"\b(evangelical|evangelicalism)\b",
     "c.family IN ('Baptist Churches','Pentecostal Churches','Nondenominational Churches','Evangelical Churches','Churches of Christ')",
     "Evangelical (broad)", 5),
    (r"\b(mainline|mainline protestant)\b",
     "c.family IN ('Methodist Churches','Presbyterian Churches','Episcopal and Anglican Churches','Lutheran Churches','United Church of Christ','Disciples of Christ')",
     "Mainline Protestant", 5),
    (r"\b(mormon|lds|latter.day saint)\b",
     "c.family IN ('Latter-day Saints')", "LDS/Mormon", 10),
    (r"\b(jehovah'?s witness|watchtower|watch ?tower)\b",
     "c.family IN ('Jehovah\\'s Witnesses')", "Jehovah's Witness", 10),
    (r"\b(seventh.day adventist|sda|adventist)\b",
     "c.family IN ('Seventh-day Adventist Churches')", "Adventist", 10),
    (r"\b(christian|christianity|church(es)?|congregation(al)?)\b",
     "c.faith_tradition = 'christian'", "Christian (generic)", 2),

    # ── Non-Christian faiths ──
    (r"\b(muslim|mosque|islam|islamic|sunni|shi[ia']|sufi|qur'?an)\b",
     "c.faith_tradition = 'muslim'", "Muslim", 12),
    (r"\b(jewish|synagogue|judaism|jew|orthodox jew|reform jew|conservative jew|chabad|hasidic)\b",
     "c.faith_tradition = 'jewish'", "Jewish", 12),
    (r"\b(buddhist|buddhism|temple|zen|theravada|mahayana|vajrayana)\b",
     "c.faith_tradition = 'buddhist'", "Buddhist", 11),
    (r"\b(hindu|hinduism|mandir|vaishnav|shaiv|vedic)\b",
     "c.faith_tradition = 'hindu'", "Hindu", 11),
    (r"\b(sikh|sikhism|gurdwara)\b",
     "c.faith_tradition = 'sikh'", "Sikh", 11),
    (r"\b(baha'?i|bahai)\b",
     "c.faith_tradition = 'bahai'", "Baha'i", 11),

    # ── Special org types ──
    (r"\b(seminar(y|ies)|theological school|divinity school|bible college)\b",
     "c.org_type = 'seminary'", "Seminaries", 8),
    (r"\b(foundation|grant-making|grantmaking|philanthrop)\b",
     "c.org_type = 'foundation'", "Foundations", 7),
    (r"\b(religious school|parochial school|catholic school|christian school|yeshiva|madrasa)\b",
     "c.org_type = 'school'", "Religious Schools", 7),

    # ── Multi-faith / interfaith ──
    (r"\b(multi.faith|interfaith|religious diversity|religious pluralism|religious landscape)\b",
     None, "Multi-faith (all)", 3),
]

# ═══════════════════════════════════════════════════════════════════════════════
# GEOGRAPHY MAPPINGS
# ═══════════════════════════════════════════════════════════════════════════════

GEO_PATTERNS = [
    # (regex, sql_where, label)

    # ── Regions ──
    (r"\b(south|southern|bible belt|deep south|sun belt|sunbelt)\b",
     "c.state IN ('AL','AR','FL','GA','KY','LA','MS','NC','OK','SC','TN','TX','VA','WV')",
     "South"),
    (r"\b(midwest|midwestern|rust belt|great lakes|upper midwest)\b",
     "c.state IN ('IL','IN','IA','KS','MI','MN','MO','NE','ND','OH','SD','WI')",
     "Midwest"),
    (r"\b(northeast|northeastern|new england|mid.atlantic|atlantic coast)\b",
     "c.state IN ('CT','ME','MA','NH','NJ','NY','PA','RI','VT','DE','MD','DC')",
     "Northeast"),
    (r"\b(west|western|mountain west|pacific coast|west coast|pacific northwest)\b",
     "c.state IN ('AK','AZ','CA','CO','HI','ID','MT','NV','NM','OR','UT','WA','WY')",
     "West"),

    # ── Urban / rural ──
    (r"\b(urban|city|cities|metropolitan|metro|inner.city|downtown|central city)\b",
     None,  # applied via population density filter
     "Urban"),
    (r"\b(suburban|suburbs|suburbia|commuter|exurban|exurb)\b",
     None,  # applied via population density filter
     "Suburban"),
    (r"\b(rural|small town|nonmetro|non.metro|countryside|remote)\b",
     None,  # applied via population density filter
     "Rural"),

    # ── Specific states (common in research) ──
    # Use more restrictive patterns: require state name or uppercase abbreviation in context
    # Pattern: match full state name OR 2-letter abbreviation with a comma or "state" nearby
    (r"\b(alabama)\b", "c.state = 'AL'", "Alabama"),
    (r"\b(alaska)\b", "c.state = 'AK'", "Alaska"),
    (r"\b(arizona)\b", "c.state = 'AZ'", "Arizona"),
    (r"\b(arkansas)\b", "c.state = 'AR'", "Arkansas"),
    (r"\b(california|calif\.?)\b", "c.state = 'CA'", "California"),
    (r"\b(colorado|colo\.?)\b", "c.state = 'CO'", "Colorado"),
    (r"\b(florida|fla\.?)\b", "c.state = 'FL'", "Florida"),
    (r"\b(georgia)\b", "c.state = 'GA'", "Georgia"),
    (r"\b(illinois|ill\.?)\b", "c.state = 'IL'", "Illinois"),
    (r"\b(indiana|ind\.?)\b", "c.state = 'IN'", "Indiana"),
    (r"\b(iowa)\b", "c.state = 'IA'", "Iowa"),
    (r"\b(kentucky)\b", "c.state = 'KY'", "Kentucky"),
    (r"\b(louisiana)\b", "c.state = 'LA'", "Louisiana"),
    (r"\b(michigan|mich\.?)\b", "c.state = 'MI'", "Michigan"),
    (r"\b(minnesota|minn\.?)\b", "c.state = 'MN'", "Minnesota"),
    (r"\b(mississippi|miss\.?)\b", "c.state = 'MS'", "Mississippi"),
    (r"\b(missouri)\b", "c.state = 'MO'", "Missouri"),
    (r"\b(new york)\b", "c.state = 'NY'", "New York"),
    (r"\b(north carolina)\b", "c.state = 'NC'", "North Carolina"),
    (r"\b(ohio)\b", "c.state = 'OH'", "Ohio"),
    (r"\b(pennsylvania|penna\.?)\b", "c.state = 'PA'", "Pennsylvania"),
    (r"\b(tennessee|tenn\.?)\b", "c.state = 'TN'", "Tennessee"),
    (r"\b(texas|tex\.?)\b", "c.state = 'TX'", "Texas"),
    (r"\b(virginia)\b", "c.state = 'VA'", "Virginia"),
    (r"\b(washington)\b", "c.state = 'WA'", "Washington"),
    (r"\b(wisconsin|wisc\.?)\b", "c.state = 'WI'", "Wisconsin"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# RESEARCH TOPIC MAPPINGS → enrichment columns to SELECT + extra WHERE
# ═══════════════════════════════════════════════════════════════════════════════

TOPIC_PATTERNS = [
    # (regex, extra_where, select_columns, label)

    # ── Demographics / ACS (zip-level via census_zip_data) ──
    (r"\b(poverty|low.income|economic disadvantage|impoverished|poor)\b",
     None,
     ["cz.poverty_rate AS acs_poverty_rate",
      "cz.median_hh_income AS acs_median_income",
      "cz.snap_pct AS acs_snap_pct"],
     "Poverty & income"),
    (r"\b(income|wealth|affluence|socioeconomic|ses|class)\b",
     None,
     ["cz.median_hh_income AS acs_median_income",
      "cz.median_home_value AS acs_median_home_value",
      "cz.poverty_rate AS acs_poverty_rate",
      "cz.gini_index AS acs_gini"],
     "Income & wealth"),
    (r"\b(race|racial|ethnicity|ethnic|segregation|diversity index|entropy)\b",
     None,
     ["cz.white_pct AS acs_white_pct",
      "cz.black_pct AS acs_black_pct",
      "cz.hisp_pct AS acs_hispanic_pct",
      "cz.asian_pct AS acs_asian_pct"],
     "Race & ethnicity"),
    (r"\b(education|educational attainment|college degree|high school)\b",
     None,
     ["cz.pct_bachelors AS acs_bachelors_pct",
      "cz.pct_graduate AS acs_grad_degree_pct",
      "cz.pct_some_college AS acs_some_college_pct"],
     "Education"),
    (r"\b(immigrant|immigration|foreign.born|nativity|migrant|refugee)\b",
     None,
     ["cz.hisp_pct AS acs_hispanic_pct",
      "cz.asian_pct AS acs_asian_pct",
      "cz.poverty_rate AS acs_poverty_rate"],
     "Immigration"),
    (r"\b(age|aging|elderly|senior|youth|children|median age|age structure)\b",
     None,
     ["cz.median_age AS acs_median_age",
      "cz.pct_18_34 AS acs_pct_18_34",
      "cz.pct_65plus AS acs_pct_65plus"],
     "Age distribution"),
    (r"\b(housing|homeownership|rent|vacancy|home value|mortgage)\b",
     None,
     ["cz.median_home_value AS acs_median_home_value",
      "cz.owner_pct AS acs_owner_occ_pct",
      "cz.vacancy_pct AS acs_vacant_pct"],
     "Housing"),
    (r"\b(commute|transportation|transit|car ownership|vehicle)\b",
     None,
     ["cz.mean_commute_min AS acs_commute_min",
      "cz.median_hh_income AS acs_median_income"],
     "Transportation"),
    (r"\b(veteran|military|disability)\b",
     None,
     ["cz.veteran_pct AS acs_veteran_pct",
      "cz.disability_pct AS acs_disability_pct",
      "cz.median_hh_income AS acs_median_income"],
     "Veterans & disability"),

    # ── Church-level ACS (more precise, fewer rows enriched) ──
    (r"\b(church.level demographic|congregation.acs|tract.level)\b",
     None,
     ["ca.acs_total_pop AS tract_pop",
      "ca.acs_median_income AS tract_income",
      "ca.acs_poverty_rate AS tract_poverty_rate",
      "ca.acs_unemployment_rate AS tract_unemployment"],
     "Church-level ACS"),

    # ── Food deserts (via church_food_desert table) ──
    (r"\b(food desert|food access|food insecurity|food swamp|grocery|supermarket)\b",
     "fd.food_desert_low_inc_low_access_1_10 = 1",
     ["fd.food_desert_low_inc_low_access_1_10 AS food_desert",
      "fd.food_desert_poverty_rate AS fd_poverty_rate",
      "fd.food_desert_median_family_income AS fd_median_income",
      "fd.food_desert_population AS fd_population",
      "cz.poverty_rate AS acs_poverty_rate",
      "cz.median_hh_income AS acs_median_income"],
     "Food deserts"),
    (r"\b(health|healthcare|hospital|uninsured|mortality|life expectancy)\b",
     None,
     ["cz.uninsured_pct AS acs_uninsured_pct",
      "cz.poverty_rate AS acs_poverty_rate",
      "cz.median_hh_income AS acs_median_income"],
     "Health"),

    # ── Politics / voting (via election_results) ──
    (r"\b(voting|election|turnout|political|partisan|partisanship|democrat|republican|gop|vote share|electoral)\b",
     None,
     ["er.dem_share AS dem_vote_share",
      "er.rep_share AS gop_vote_share",
      "er.total_votes AS turnout_total",
      "er.turnout_est AS turnout_estimate"],
     "Voting & elections"),
    (r"\b(polarization|political polarization|affective polarization|sorting)\b",
     None,
     ["er.dem_share AS dem_vote_share",
      "er.rep_share AS gop_vote_share",
      "er.total_votes AS turnout_total"],
     "Polarization"),

    # ── Crime (via fbi_ucr_crime) ──
    (r"\b(crime|violent crime|homicide|murder|robbery|burglary|property crime|public safety)\b",
     None,
     ["fbi.violent_rate AS fbi_violent_rate",
      "fbi.murder_rate AS fbi_murder_rate",
      "fbi.property_rate AS fbi_property_rate",
      "fbi.burglary_rate AS fbi_burglary_rate"],
     "Crime"),

    # ── Spatial / GIS ──
    (r"\b(spatial|gis|geographic|geography|mapping|geospatial|hot spot|cluster|proximity|distance)\b",
     None,
     ["cz.total_pop AS acs_total_pop",
      "cz.median_hh_income AS acs_median_income"],
     "Spatial/GIS"),

    # ── Congregational studies ──
    (r"\b(congregation(al)? ecology|church planting|church growth|religious vitality|attendance|membership)\b",
     None,
     ["cz.total_pop AS acs_total_pop",
      "cz.median_hh_income AS acs_median_income",
      "cz.poverty_rate AS acs_poverty_rate"],
     "Congregational ecology"),

    # ── Population change ──
    (r"\b(population (change|decline|growth|loss)|shrinking|growing|demographic change|migration)\b",
     None,
     ["cz.total_pop AS acs_total_pop",
      "cz.median_hh_income AS acs_median_income",
      "cz.poverty_rate AS acs_poverty_rate"],
     "Population change"),

    # ── Social capital / civil society ──
    (r"\b(social capital|civil society|civic engagement|community organiz|voluntary association|putnam)\b",
     None,
     ["cz.total_pop AS acs_total_pop",
      "cz.median_hh_income AS acs_median_income",
      "cz.poverty_rate AS acs_poverty_rate"],
     "Social capital"),

    # ── Urban planning ──
    (r"\b(urban planning|land use|zoning|built environment|neighborhood (change|effect|decline|revitalization)|gentrification)\b",
     None,
     ["cz.median_home_value AS acs_median_home_value",
      "cz.median_hh_income AS acs_median_income",
      "cz.poverty_rate AS acs_poverty_rate",
      "cz.total_pop AS acs_total_pop"],
     "Urban planning"),

    # ── Inequality ──
    (r"\b(inequality|income inequality|gini|wealth gap|racial gap|disparity|stratification)\b",
     None,
     ["cz.gini_index AS acs_gini",
      "cz.median_hh_income AS acs_median_income",
      "cz.poverty_rate AS acs_poverty_rate",
      "cz.white_pct AS acs_white_pct",
      "cz.black_pct AS acs_black_pct",
      "cz.hisp_pct AS acs_hispanic_pct"],
     "Inequality"),

    # ── Religious adherence (ARDA) ──
    (r"\b(religious adherence|adherence rate|arda|religious landscape|religious composition)\b",
     None,
     ["arda.adherence_rate AS arda_adherence_rate",
      "arda.evangelical_pct AS arda_evangelical_pct",
      "arda.catholic_pct AS arda_catholic_pct",
      "arda.total_adherents AS arda_total_adherents"],
     "Religious adherence"),
]


# ═══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ResearchDimensions:
    """Extracted research dimensions from a paper."""
    faith_where: Optional[str] = None
    faith_label: str = "All faiths"
    geo_where: list = field(default_factory=list)
    geo_label: str = "National"
    urban_rural: Optional[str] = None  # 'urban', 'suburban', 'rural', or None
    topic_wheres: list = field(default_factory=list)
    topic_columns: list = field(default_factory=list)
    topic_labels: list = field(default_factory=list)


@dataclass
class QuerySpec:
    """A complete SQL query specification ready to execute."""
    select_columns: list
    where_clauses: list
    join_clauses: list
    order_by: str
    limit: int
    # Metadata for the email
    faith_label: str
    geo_label: str
    topic_labels: list


# ═══════════════════════════════════════════════════════════════════════════════
# EXTRACTION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _match_faith_patterns(text: str) -> list:
    """Match faith tradition patterns. Returns [(where_clause, label, priority)]."""
    matches = []
    for regex, where_clause, label, priority in FAITH_PATTERNS:
        if re.search(regex, text, re.IGNORECASE):
            matches.append((where_clause, label, priority))
    matches.sort(key=lambda x: x[2], reverse=True)
    return matches


def _match_geo_patterns(text: str) -> list:
    """Match geography patterns. Returns [(where_clause, label)]."""
    matches = []
    for regex, where_clause, label in GEO_PATTERNS:
        if re.search(regex, text, re.IGNORECASE):
            matches.append((where_clause, label))
    return matches


def _match_topic_patterns(text: str) -> list:
    """Match research topic patterns. Returns [(extra_where, select_columns, label)]."""
    matches = []
    for regex, extra_where, select_columns, label in TOPIC_PATTERNS:
        if re.search(regex, text, re.IGNORECASE):
            matches.append((extra_where, select_columns, label))
    return matches


def extract_research_dimensions(title: str, abstract: str = "") -> ResearchDimensions:
    """
    Parse a paper's title and abstract to extract research dimensions.
    
    Args:
        title: Paper title
        abstract: Paper abstract (optional, improves accuracy)
    
    Returns:
        ResearchDimensions with extracted faith, geo, and topic info
    """
    combined = f"{title}\n{abstract}" if abstract else title
    dims = ResearchDimensions()

    # ── Extract faith tradition ──
    faith_matches = _match_faith_patterns(combined)
    if faith_matches:
        top = faith_matches[0]
        if top[0] is not None:  # None means "all faiths" (multi-faith)
            dims.faith_where = top[0]
        dims.faith_label = top[1]

    # ── Extract geography ──
    geo_matches = _match_geo_patterns(combined)
    urban_rural_labels = {"Urban", "Suburban", "Rural"}
    for where_clause, label in geo_matches:
        if label in urban_rural_labels:
            if dims.urban_rural is None:
                dims.urban_rural = label.lower()
        elif where_clause is not None and where_clause not in dims.geo_where:
            dims.geo_where.append(where_clause)

    geo_labels = [m[1] for m in geo_matches if m[1] not in urban_rural_labels]
    if dims.urban_rural:
        geo_labels.append(dims.urban_rural.title())
    dims.geo_label = ", ".join(geo_labels[:3]) if geo_labels else "National"

    # ── Extract research topics ──
    topic_matches = _match_topic_patterns(combined)
    col_seen = set()
    seen_labels = set()
    for extra_where, select_columns, label in topic_matches:
        if extra_where:
            dims.topic_wheres.append(extra_where)
        if label not in seen_labels:
            seen_labels.add(label)
            dims.topic_labels.append(label)
        for col in select_columns:
            if col not in col_seen:
                col_seen.add(col)
                dims.topic_columns.append(col)

    return dims


# ═══════════════════════════════════════════════════════════════════════════════
# QUERY BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

# Base SELECT columns always included
BASE_COLUMNS = [
    "c.id",
    "c.name",
    "c.city",
    "c.state",
    "c.zip",
    "c.faith_tradition",
    "c.family AS denomination_family",
    "c.denomination",
    "c.org_type",
    "c.latitude AS lat",
    "c.longitude AS lng",
    "c.website",
    "c.ein",
]

# Tables we may need to JOIN based on topic columns
# Column prefix pattern → (join_clause, needs_table_alias)
JOIN_DEPENDENCIES = {
    "cz.": ("LEFT JOIN census_zip_data cz ON cz.zip5 = c.zip AND cz.year = 2022", True),
    "er.": ("LEFT JOIN election_results er ON er.county_fips = c.county_fips AND er.year = 2024", True),
    "fbi.": ("LEFT JOIN fbi_ucr_crime fbi ON fbi.county_fips = c.county_fips", True),
    "arda.": ("LEFT JOIN arda_county_data arda ON arda.county_fips = c.county_fips", True),
    "fd.": ("LEFT JOIN church_food_desert fd ON fd.church_id = c.id", True),
    "ca.": ("LEFT JOIN church_census_us ca ON ca.church_id = c.id", True),
    "cha.": ("LEFT JOIN church_arda cha ON cha.church_id = c.id", True),
}


def build_query(dims: ResearchDimensions, limit: int = 12) -> QuerySpec:
    """
    Build a complete SQL query from extracted research dimensions.
    
    Args:
        dims: Extracted ResearchDimensions
        limit: Max number of sample rows
    
    Returns:
        QuerySpec ready to execute
    """
    select_cols = list(BASE_COLUMNS)
    where_clauses = []
    join_clauses = set()

    # ── Apply faith filter ──
    if dims.faith_where:
        where_clauses.append(dims.faith_where)

    # ── Apply geo filters ──
    for geo_w in dims.geo_where:
        where_clauses.append(geo_w)

    # ── Apply urban/rural filter ──
    if dims.urban_rural == "urban":
        where_clauses.append("cz.total_pop > 30000")
        join_clauses.add(JOIN_DEPENDENCIES["cz."][0])
    elif dims.urban_rural == "suburban":
        where_clauses.append("cz.total_pop BETWEEN 8000 AND 30000")
        join_clauses.add(JOIN_DEPENDENCIES["cz."][0])
    elif dims.urban_rural == "rural":
        where_clauses.append("cz.total_pop < 8000")
        join_clauses.add(JOIN_DEPENDENCIES["cz."][0])

    # ── Apply topic WHERE clauses ──
    for tw in dims.topic_wheres:
        where_clauses.append(tw)

    # ── Add topic SELECT columns & their required JOINs ──
    for col in dims.topic_columns:
        if col not in select_cols:
            select_cols.append(col)
        # Determine which JOINs are needed
        for prefix, (join_sql, _) in JOIN_DEPENDENCIES.items():
            if prefix in col:
                join_clauses.add(join_sql)
                break

    # ── Ensure census_zip_data is joined if not already (needed for population filters) ──
    if dims.urban_rural or any("cz." in c for c in select_cols):
        join_clauses.add(JOIN_DEPENDENCIES["cz."][0])

    # ── Add quality filters ──
    where_clauses.append("c.name IS NOT NULL AND c.name != ''")
    where_clauses.append("c.state IS NOT NULL AND c.state != ''")

    # ── Build ORDER BY ──
    order_by = "RANDOM()"  # Diverse sample — not alphabetical bias

    query = QuerySpec(
        select_columns=select_cols,
        where_clauses=where_clauses,
        join_clauses=sorted(join_clauses),
        order_by=order_by,
        limit=limit,
        faith_label=dims.faith_label,
        geo_label=dims.geo_label or "National",
        topic_labels=dims.topic_labels,
    )
    return query


def query_to_sql(qs: QuerySpec) -> str:
    """Convert a QuerySpec to executable SQL."""
    selects = ",\n         ".join(qs.select_columns)
    wheres = "\n    AND ".join(qs.where_clauses)
    joins = "\n  ".join(qs.join_clauses)

    sql = f"""SELECT {selects}
  FROM churches c
  {joins}
  WHERE {wheres}
  ORDER BY {qs.order_by}
  LIMIT {qs.limit}"""
    return sql


def describe_dimensions(dims: ResearchDimensions) -> str:
    """Human-readable summary of extracted dimensions."""
    parts = []
    parts.append(f"Faith: {dims.faith_label}")
    parts.append(f"Geography: {dims.geo_label}")
    if dims.urban_rural:
        parts.append(f"Setting: {dims.urban_rural.title()}")
    if dims.topic_labels:
        parts.append(f"Topics: {', '.join(dims.topic_labels)}")
    return " | ".join(parts)


# ═══════════════════════════════════════════════════════════════════════════════
# SAMPLE FORMATTER
# ═══════════════════════════════════════════════════════════════════════════════

def format_sample_row(row: dict, dims: ResearchDimensions) -> str:
    """Format a single sample row for email display."""
    name = (row.get('name') or 'Unknown')[:50]
    city = (row.get('city') or '')[:20]
    state = (row.get('state') or '')[:4]
    ft = (row.get('faith_tradition') or row.get('denomination_family') or '?').title()[:15]
    org = (row.get('org_type') or '')[:15]
    lat = row.get('lat')
    lng = row.get('lng')
    coord = f"({lat:.2f}, {lng:.2f})" if lat and lng else ""

    # Pick the most interesting enrichment values
    enrich = []
    for key, val in sorted(row.items()):
        if key.startswith(('acs_', 'gop_', 'dem_', 'fbi_', 'turnout_', 'food_')):
            if val is not None:
                if isinstance(val, float):
                    if 'rate' in key or 'pct' in key:
                        enrich.append(f"{key.replace('acs_','').replace('_',' ')}={val:.1f}%")
                    elif 'income' in key or 'value' in key:
                        enrich.append(f"{key.replace('acs_','')}=${val:,.0f}")
                    else:
                        enrich.append(f"{key}={val:,.1f}")
                else:
                    enrich.append(f"{key}={val}")

    enrich_str = " | ".join(enrich[:5]) if enrich else ""

    return f"  {name[:45]:45s} | {city:18s} {state:4s} | {ft:15s} | {org:15s} | {coord} | {enrich_str}"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN (for testing)
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    # Quick self-test
    test_papers = [
        ("Mosques as Community Anchors: Spatial Analysis of Muslim Institutions in Post-Industrial Midwestern Cities",
         "This study examines the spatial distribution of mosques in declining Midwestern urban centers..."),
        ("Food Deserts and the Black Church: Faith-Based Responses to Nutritional Inequality in the Rural South",
         "We analyze the relationship between African American church locations and USDA food desert tracts..."),
        ("Evangelical Church Density and Republican Vote Share: County-Level Analysis 2000-2024",
         ""),
        ("Catholic Parish Closures and Neighborhood Decline in Rust Belt Cities",
         ""),
        ("Religious Diversity and Social Capital in Multi-Ethnic Urban Neighborhoods",
         ""),
    ]

    for title, abstract in test_papers:
        print(f"\n{'='*80}")
        print(f"PAPER: {title[:90]}")
        dims = extract_research_dimensions(title, abstract)
        print(f"  {describe_dimensions(dims)}")
        qs = build_query(dims, limit=8)
        print(f"  Faith filter: {dims.faith_where}")
        print(f"  Geo filters: {dims.geo_where}")
        print(f"  Topic WHEREs: {dims.topic_wheres}")
        print(f"  Topic cols: {len(dims.topic_columns)}")
        print(f"  JOINs: {len(qs.join_clauses)}")
        print(f"\n{query_to_sql(qs)}")
