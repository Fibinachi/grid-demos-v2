#!/usr/bin/env python3
"""
Generate a comprehensive report of the 25 neediest SBC churches
for presentation to the Southern Baptist Convention.

Outputs:
  - data/sbc_neediest_report.md   — Professional Markdown report
  - data/sbc_neediest_report.csv  — Full data CSV
  - data/sbc_neediest_report.txt  — Plain text summary

Composite need score factors:
  - Poverty rate (3x weight)
  - Unemployment rate (2x weight)
  - Low median income
  - Elderly population (median age above 30)
  - Food desert / low food access
"""
import sqlite3, csv, os
from datetime import datetime

DB = r'E:\grid\churches.db'
OUT_DIR = r'E:\grid\data'

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

os.makedirs(OUT_DIR, exist_ok=True)

# ── Query: Top 25 by composite need score ──────────────────────────
TOP_N = 25
query = """
SELECT 
    id, name, city, state, address, zip, ein, source,
    website, phone, email,
    pastor_name, attendance_est, staff_count, campus_count,
    latitude, longitude,
    denomination, family, org_type,
    district, association,
    -- ACS tract-level data
    acs_poverty_rate, acs_poverty_count, acs_poverty_universe,
    acs_median_income, acs_median_age,
    acs_unemployment_rate, acs_unemployed, acs_employed,
    acs_median_home_value, acs_total_pop,
    acs_bachelors_count, acs_masters_count, acs_doctorate_count,
    acs_white_pop, acs_black_pop, acs_hispanic_pop, acs_asian_pop,
    -- Census tract data (richer)
    census_poverty_rate, census_poverty_total, census_median_hh_income,
    census_median_age, census_pct_65plus, census_pct_bachelors,
    census_unemployed_pct, census_snap_pct, census_disability_pct,
    census_uninsured_pct, census_single_parent_pct, census_veteran_pct,
    census_owner_pct, census_renter_pct, census_vacancy_pct,
    census_med_home_val, census_mean_commute_min,
    census_married_pct, census_female_hh_pct,
    -- Food desert data
    food_desert_low_inc_low_access_1_10,
    food_desert_low_inc_low_access_1_20,
    food_desert_low_inc_low_access_half_10,
    food_desert_low_inc_low_access_vehicle,
    food_desert_poverty_rate, food_desert_seniors_pop,
    food_desert_snap_hh, food_desert_no_vehicle_hh,
    food_desert_population, food_desert_urban,
    tract_fips,
    -- Ministry indicators
    has_food_pantry, has_youth, has_children, has_seniors,
    has_recovery, has_missions, has_counseling, has_sports,
    has_daycare, has_preschool, has_esl,
    online_giving_link, livestream_link,
    facebook_url, instagram_url, youtube_url,
    service_times, languages, worship_style, doctrinal_alignment,
    spanish_language, primary_language,
    -- Geocode quality
    geocode_source, geocode_confidence,
    -- Website data
    website_last_updated, cms_type,
    -- Church health
    is_church_plant, is_closed, is_broadcast_ministry,
    -- Composite need score
    ROUND(
        COALESCE(acs_poverty_rate, 0) * 100.0 * 3.0
        + COALESCE((100.0 - acs_median_income / 1000.0) / 10.0, 0)
        + COALESCE(acs_unemployment_rate * 100.0 * 2.0, 0)
        + COALESCE((acs_median_age - 30.0) / 5.0, 0)
        + CASE WHEN tract_fips IS NOT NULL AND tract_fips != '' THEN 2.0 ELSE 0 END
    , 1) as need_score
FROM churches
WHERE denomination = 'Southern Baptist Convention'
    AND acs_poverty_rate IS NOT NULL
    AND acs_median_income IS NOT NULL
    AND (is_closed IS NULL OR is_closed = 0)
ORDER BY need_score DESC
LIMIT ?
"""

rows = c.execute(query, (TOP_N,)).fetchall()
total_sbc = c.execute("SELECT COUNT(x) FROM (SELECT 1 as x FROM churches WHERE denomination = 'Southern Baptist Convention')").fetchone()[0]

# ── Compute report date/time ───────────────────────────────────────
now = datetime.now().strftime('%B %d, %Y at %I:%M %p')

# ── HELPER: format a value ─────────────────────────────────────────
def fmt(val, suffix='', default='N/A'):
    if val is None or val == '':
        return default
    return f'{val}{suffix}'

def pct(val, default='N/A'):
    if val is None:
        return default
    return f'{val*100:.1f}%'

def dollar(val, default='N/A'):
    if val is None:
        return default
    return f'${val:,.0f}'

def comma(val, default='N/A'):
    if val is None:
        return default
    return f'{val:,.0f}'

def yesno(val):
    if val and val != 0 and val != '':
        return '✅ Yes'
    return '—'

def tract_link(fips):
    if fips:
        return f'https://censusreporter.org/profiles/14000US{fips}/'
    return ''

# ── Build Markdown Report ──────────────────────────────────────────
md = []
md.append(f'# SBC Church Needs Assessment Report')
md.append(f'')
md.append(f'**Generated:** {now}')
md.append(f'')
md.append(f'**Scope:** {comma(total_sbc)} Southern Baptist Convention churches in database, ')
md.append(f'ranked by composite need score across poverty, unemployment, low income, ')
md.append(f'elderly population, and food access risk.')
md.append(f'')
md.append(f'---')
md.append(f'')
md.append(f'## Executive Summary')
md.append(f'')
md.append(f'This report identifies the {TOP_N} SBC churches serving communities with the highest ')
md.append(f'concentrated need based on ACS (American Community Survey) tract-level data. ')
md.append(f'These churches are in areas with poverty rates averaging **{sum(r["acs_poverty_rate"] or 0 for r in rows)/len(rows)*100:.1f}%**, ')
md.append(f'median household incomes under **${sum(r["acs_median_income"] or 0 for r in rows)/len(rows):,.0f}**, ')
md.append(f'and unemployment rates averaging **{sum(r["acs_unemployment_rate"] or 0 for r in rows)/len(rows)*100:.1f}%**.')
md.append(f'')
md.append(f'Each entry below includes the church\'s contact information, demographic context, ')
md.append(f'ministry indicators, and tract-level Census data to inform strategic support decisions.')
md.append(f'')
md.append(f'---')
md.append(f'')

# Add summary table
md.append(f'## Top {TOP_N} SBC Churches — Ranked by Need')
md.append(f'')
md.append(f'| # | Church | City | ST | Poverty | Med. Income | Unempl. | Age | Score |')
md.append(f'|---|--------|------|----|---------|-------------|---------|-----|-------|')
for i, r in enumerate(rows, 1):
    name = r['name'][:50] if r['name'] else 'Unknown'
    city = r['city'][:20] if r['city'] else ''
    pov = f'{r["acs_poverty_rate"]*100:.1f}%' if r['acs_poverty_rate'] is not None else '-'
    inc = f'${r["acs_median_income"]:,.0f}' if r['acs_median_income'] else '-'
    unemp = f'{r["acs_unemployment_rate"]*100:.1f}%' if r['acs_unemployment_rate'] is not None else '-'
    age = f'{r["acs_median_age"]:.1f}' if r['acs_median_age'] else '-'
    md.append(f'| {i} | {name} | {city} | {r["state"]} | {pov} | {inc} | {unemp} | {age} | {r["need_score"]} |')

md.append(f'')
md.append(f'---')
md.append(f'')

# Detailed profiles
md.append(f'## Detailed Church Profiles')
md.append(f'')

for i, r in enumerate(rows, 1):
    pov_pct = f'{r["acs_poverty_rate"]*100:.1f}%' if r['acs_poverty_rate'] is not None else 'N/A'
    unemp_pct = f'{r["acs_unemployment_rate"]*100:.1f}%' if r['acs_unemployment_rate'] is not None else 'N/A'
    
    md.append(f'### {i}. {r["name"]}')
    md.append(f'')
    md.append(f'**Location:** {fmt(r["address"])}, {fmt(r["city"])}, {r["state"]} {fmt(r["zip"])}')
    md.append(f'')
    md.append(f'| Field | Value |')
    md.append(f'|-------|-------|')
    
    # Contact info
    md.append(f'| **Website** | {fmt(r["website"], default="—")} |')
    md.append(f'| **Phone** | {fmt(r["phone"], default="—")} |')
    md.append(f'| **Email** | {fmt(r["email"], default="—")} |')
    md.append(f'| **EIN** | {fmt(r["ein"], default="—")} |')
    
    # Pastoral / congregation
    md.append(f'| **Pastor** | {fmt(r["pastor_name"], default="—")} |')
    md.append(f'| **Est. Attendance** | {comma(r["attendance_est"])} |')
    md.append(f'| **Staff Count** | {fmt(r["staff_count"], default="—")} |')
    md.append(f'| **Campuses** | {fmt(r["campus_count"], default="1")} |')
    
    # Location
    if r['latitude']:
        md.append(f'| **Coordinates** | {r["latitude"]:.5f}, {r["longitude"]:.5f} |')
    md.append(f'| **Association** | {fmt(r["association"], default="—")} |')
    md.append(f'| **Source** | {fmt(r["source"], default="—")} |')
    md.append(f'| **Tract FIPS** | {fmt(r["tract_fips"], default="—")} |')
    if r['tract_fips']:
        md.append(f'| **Census Reporter** | [View tract](https://censusreporter.org/profiles/14000US{r["tract_fips"]}/) |')
    
    md.append(f'')
    md.append(f'#### Demographic Context')
    md.append(f'')
    md.append(f'| Measure | Value |')
    md.append(f'|---------|-------|')
    
    # ACS tract data
    md.append(f'| **Poverty Rate** | {pov_pct} ({comma(r["acs_poverty_count"])} / {comma(r["acs_poverty_universe"])}) |')
    md.append(f'| **Median Household Income** | {dollar(r["acs_median_income"])} |')
    md.append(f'| **Median Age** | {fmt(r["acs_median_age"], default="—")} |')
    md.append(f'| **Unemployment Rate** | {unemp_pct} ({comma(r["acs_unemployed"])} / {comma(r["acs_employed"] + r["acs_unemployed"]) if r["acs_employed"] else "—"}) |')
    md.append(f'| **Median Home Value** | {dollar(r["acs_median_home_value"])} |')
    md.append(f'| **Total Population** | {comma(r["acs_total_pop"])} |')
    
    # Census tract data (richer if available)
    if r['census_poverty_rate'] is not None:
        md.append(f'| **Census Poverty Rate** | {pct(r["census_poverty_rate"])} |')
    if r['census_median_hh_income'] is not None:
        md.append(f'| **Census Median HH Income** | {dollar(r["census_median_hh_income"])} |')
    if r['census_pct_65plus'] is not None:
        md.append(f'| **Population 65+** | {pct(r["census_pct_65plus"])} |')
    if r['census_pct_bachelors'] is not None:
        md.append(f'| **Bachelor\'s Degree+** | {pct(r["census_pct_bachelors"])} |')
    if r['census_snap_pct'] is not None:
        md.append(f'| **SNAP Benefits** | {pct(r["census_snap_pct"])} |')
    if r['census_disability_pct'] is not None:
        md.append(f'| **Disability** | {pct(r["census_disability_pct"])} |')
    if r['census_uninsured_pct'] is not None:
        md.append(f'| **Uninsured** | {pct(r["census_uninsured_pct"])} |')
    if r['census_single_parent_pct'] is not None:
        md.append(f'| **Single Parent HH** | {pct(r["census_single_parent_pct"])} |')
    if r['census_veteran_pct'] is not None:
        md.append(f'| **Veteran** | {pct(r["census_veteran_pct"])} |')
    if r['census_owner_pct'] is not None:
        md.append(f'| **Homeowner** | {pct(r["census_owner_pct"])} |')
    if r['census_vacancy_pct'] is not None:
        md.append(f'| **Vacancy Rate** | {pct(r["census_vacancy_pct"])} |')
    if r['census_married_pct'] is not None:
        md.append(f'| **Married** | {pct(r["census_married_pct"])} |')
    
    # Racial/ethnic composition
    if any([r['acs_white_pop'], r['acs_black_pop'], r['acs_hispanic_pop'], r['acs_asian_pop']]):
        md.append(f'')
        md.append(f'#### Racial/Ethnic Composition')
        md.append(f'')
        total_pop = (r['acs_white_pop'] or 0) + (r['acs_black_pop'] or 0) + (r['acs_hispanic_pop'] or 0) + (r['acs_asian_pop'] or 0)
        if total_pop > 0:
            md.append(f'| Group | Population | Percentage |')
            md.append(f'|-------|-----------|------------|')
            if r['acs_white_pop']:
                md.append(f'| White | {comma(r["acs_white_pop"])} | {r["acs_white_pop"]/total_pop*100:.1f}% |')
            if r['acs_black_pop']:
                md.append(f'| Black | {comma(r["acs_black_pop"])} | {r["acs_black_pop"]/total_pop*100:.1f}% |')
            if r['acs_hispanic_pop']:
                md.append(f'| Hispanic | {comma(r["acs_hispanic_pop"])} | {r["acs_hispanic_pop"]/total_pop*100:.1f}% |')
            if r['acs_asian_pop']:
                md.append(f'| Asian | {comma(r["acs_asian_pop"])} | {r["acs_asian_pop"]/total_pop*100:.1f}% |')
    
    # Food desert data
    fd = r['food_desert_low_inc_low_access_1_10']
    if fd is not None:
        md.append(f'')
        md.append(f'#### Food Access')
        md.append(f'')
        md.append(f'| Measure | Value |')
        md.append(f'|---------|-------|')
        md.append(f'| **Low Income + Low Access (1mi/10mi)** | {yesno(fd)} |')
        if r['food_desert_low_inc_low_access_1_20'] is not None:
            md.append(f'| **Low Income + Low Access (½mi/20mi)** | {yesno(r["food_desert_low_inc_low_access_1_20"])} |')
        if r['food_desert_poverty_rate'] is not None:
            md.append(f'| **Food Desert Poverty Rate** | {r["food_desert_poverty_rate"]:.1f}% |')
        if r['food_desert_seniors_pop'] is not None:
            md.append(f'| **Senior Population** | {comma(r["food_desert_seniors_pop"])} |')
        if r['food_desert_snap_hh'] is not None:
            md.append(f'| **SNAP Households** | {comma(r["food_desert_snap_hh"])} |')
        if r['food_desert_no_vehicle_hh'] is not None:
            md.append(f'| **No Vehicle HH** | {comma(r["food_desert_no_vehicle_hh"])} |')
    
    # Ministry indicators
    ministries = []
    for label, col in [('Food Pantry', 'has_food_pantry'), ('Youth Ministry', 'has_youth'),
                        ('Children Ministry', 'has_children'), ('Senior Ministry', 'has_seniors'),
                        ('Recovery Ministry', 'has_recovery'), ('Missions Program', 'has_missions'),
                        ('Counseling', 'has_counseling'), ('Sports', 'has_sports'),
                        ('Daycare', 'has_daycare'), ('Preschool', 'has_preschool'),
                        ('ESL', 'has_esl')]:
        if r[col] and r[col] != 0:
            ministries.append(label)
    
    if ministries:
        md.append(f'')
        md.append(f'#### Ministry Indicators')
        md.append(f'')
        for m in ministries:
            md.append(f'- ✅ {m}')
    
    # Online presence
    online = []
    if r['website']:
        online.append(f'🌐 [{r["website"]}]({r["website"]})')
    if r['facebook_url']:
        online.append(f'📘 [Facebook]({r["facebook_url"]})')
    if r['instagram_url']:
        online.append(f'📸 [Instagram]({r["instagram_url"]})')
    if r['youtube_url']:
        online.append(f'▶️ [YouTube]({r["youtube_url"]})')
    if r['online_giving_link']:
        online.append(f'💰 [Online Giving]({r["online_giving_link"]})')
    if r['livestream_link']:
        online.append(f'📺 [Livestream]({r["livestream_link"]})')
    
    if online:
        md.append(f'')
        md.append(f'#### Online Presence')
        md.append(f'')
        for o in online:
            md.append(f'- {o}')
    
    md.append(f'')
    md.append(f'---')
    md.append(f'')

# Methodology appendix
md.append(f'## Methodology')
md.append(f'')
md.append(f'### Composite Need Score')
md.append(f'')
md.append(f'The composite need score weights four factors from ACS tract-level data:')
md.append(f'')
md.append(f'1. **Poverty Rate** (×3) — Proportion of population below poverty line')
md.append(f'2. **Unemployment Rate** (×2) — Proportion of labor force unemployed')
md.append(f'3. **Low Income** — Inverted median household income (lower = higher score)')
md.append(f'4. **Elderly Population** — Median age above 30 (higher = more elderly)')
md.append(f'5. **Food Access** — Tract flagged as low-income + low food access')
md.append(f'')
md.append(f'### Data Sources')
md.append(f'')
md.append(f'- **SBC Directory:** churches.sbc.net — 23,380 churches with contact info')
md.append(f'- **SBC Scrape:** sbc.net/scbeach — 6,949 additional churches')
md.append(f'- **IRS EO BMF:** 5,985 SBC churches from IRS classification data')
md.append(f'- **ACS 5-Year Estimates:** Tract-level poverty, income, age, employment')
md.append(f'- **USDA Food Access Research Atlas:** Low-income + low-access tracts')
md.append(f'- **Census Bureau:** Tract-level demographics')
md.append(f'')
md.append(f'---')
md.append(f'')
md.append(f'*Report generated by GrantWizard — {now}*')

report_md = '\n'.join(md)

# ── Write Markdown Report ───────────────────────────────────────────
md_path = os.path.join(OUT_DIR, 'sbc_neediest_report.md')
with open(md_path, 'w', encoding='utf-8') as f:
    f.write(report_md)
print(f'✅ Markdown report: {md_path}')

# ── Write CSV ───────────────────────────────────────────────────────
csv_path = os.path.join(OUT_DIR, 'sbc_neediest_report.csv')
fieldnames = ['rank', 'need_score', 'name', 'city', 'state', 'address', 'zip', 'ein',
              'website', 'phone', 'email', 'pastor_name', 'attendance_est',
              'poverty_rate_pct', 'poverty_count', 'poverty_universe',
              'median_income', 'median_age', 'unemployment_rate_pct',
              'median_home_value', 'total_population',
              'tract_fips', 'food_desert_flag',
              'has_food_pantry', 'has_youth', 'has_children', 'has_seniors',
              'has_recovery', 'has_missions', 'latitude', 'longitude',
              'source', 'association', 'staff_count', 'campus_count',
              'spanish_language', 'primary_language']

with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
    w.writeheader()
    for i, r in enumerate(rows, 1):
        w.writerow({
            'rank': i,
            'need_score': r['need_score'],
            'name': r['name'],
            'city': r['city'],
            'state': r['state'],
            'address': r['address'],
            'zip': r['zip'],
            'ein': r['ein'],
            'website': r['website'],
            'phone': r['phone'],
            'email': r['email'],
            'pastor_name': r['pastor_name'],
            'attendance_est': r['attendance_est'],
            'poverty_rate_pct': round((r['acs_poverty_rate'] or 0) * 100, 1),
            'poverty_count': r['acs_poverty_count'],
            'poverty_universe': r['acs_poverty_universe'],
            'median_income': r['acs_median_income'],
            'median_age': r['acs_median_age'],
            'unemployment_rate_pct': round((r['acs_unemployment_rate'] or 0) * 100, 1),
            'median_home_value': r['acs_median_home_value'],
            'total_population': r['acs_total_pop'],
            'tract_fips': r['tract_fips'],
            'food_desert_flag': r['food_desert_low_inc_low_access_1_10'],
            'has_food_pantry': r['has_food_pantry'],
            'has_youth': r['has_youth'],
            'has_children': r['has_children'],
            'has_seniors': r['has_seniors'],
            'has_recovery': r['has_recovery'],
            'has_missions': r['has_missions'],
            'latitude': r['latitude'],
            'longitude': r['longitude'],
            'source': r['source'],
            'association': r['association'],
            'staff_count': r['staff_count'],
            'campus_count': r['campus_count'],
            'spanish_language': r['spanish_language'],
            'primary_language': r['primary_language'],
        })
print(f'✅ CSV data: {csv_path}')

# ── Write Plain Text Summary ────────────────────────────────────────
txt_path = os.path.join(OUT_DIR, 'sbc_neediest_report.txt')
with open(txt_path, 'w', encoding='utf-8') as f:
    f.write(f'SBC CHURCH NEEDS ASSESSMENT — Top {TOP_N}\n')
    f.write(f'Generated: {now}\n')
    f.write(f'Database: {comma(total_sbc)} SBC churches\n')
    f.write('=' * 80 + '\n\n')
    
    for i, r in enumerate(rows, 1):
        f.write(f'--- #{i} (Score: {r["need_score"]}) ---\n')
        f.write(f'  Church:     {r["name"]}\n')
        f.write(f'  Location:   {fmt(r["address"])}, {fmt(r["city"])}, {r["state"]} {fmt(r["zip"])}\n')
        f.write(f'  Website:    {fmt(r["website"], default="—")}\n')
        f.write(f'  Phone:      {fmt(r["phone"], default="—")}\n')
        f.write(f'  Email:      {fmt(r["email"], default="—")}\n')
        f.write(f'  Pastor:     {fmt(r["pastor_name"], default="—")}\n')
        f.write(f'  Attendance: {comma(r["attendance_est"])}\n')
        f.write(f'  Poverty:    {pct(r["acs_poverty_rate"])}\n')
        f.write(f'  Income:     {dollar(r["acs_median_income"])}\n')
        f.write(f'  Age:        {fmt(r["acs_median_age"])}\n')
        f.write(f'  Unempl:     {pct(r["acs_unemployment_rate"])}\n')
        f.write(f'  Home Val:   {dollar(r["acs_median_home_value"])}\n')
        if r['food_desert_low_inc_low_access_1_10']:
            f.write(f'  FOOD DESERT: Yes\n')
        f.write('\n')

print(f'✅ Text summary: {txt_path}')

# ── Summary stats ───────────────────────────────────────────────────
print(f'\n=== Summary ===')
pov_avg = sum(r['acs_poverty_rate'] or 0 for r in rows) / len(rows) * 100
inc_avg = sum(r['acs_median_income'] or 0 for r in rows) / len(rows)
unemp_avg = sum(r['acs_unemployment_rate'] or 0 for r in rows) / len(rows) * 100
print(f'Average poverty rate: {pov_avg:.1f}%')
print(f'Average median income: ${inc_avg:,.0f}')
print(f'Average unemployment: {unemp_avg:.1f}%')
print(f'With food desert flag: {sum(1 for r in rows if r["food_desert_low_inc_low_access_1_10"])}')
print(f'With website: {sum(1 for r in rows if r["website"])}')
print(f'With phone: {sum(1 for r in rows if r["phone"])}')
print(f'With pastor name: {sum(1 for r in rows if r["pastor_name"])}')

conn.close()
