#!/usr/bin/env python3
"""
Generate a South Carolina SBC church needs assessment report.
"""
import sqlite3, os
from datetime import datetime

DB = r'E:\grid\churches.db'
OUT_DIR = r'E:\grid\reports'
TOP_N = 25

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

total = c.execute("SELECT COUNT(x) FROM (SELECT 1 as x FROM churches WHERE denomination = 'Southern Baptist Convention' AND state = 'SC')").fetchone()[0]
with_data = c.execute("SELECT COUNT(x) FROM (SELECT 1 as x FROM churches WHERE denomination = 'Southern Baptist Convention' AND state = 'SC' AND acs_poverty_rate IS NOT NULL)").fetchone()[0]
print(f'SC SBC churches: {total:,}  |  With ACS data: {with_data:,}')

rows = c.execute("""
    SELECT id, name, city, state, address, zip, ein, source,
        website, phone, email, pastor_name, attendance_est,
        acs_poverty_rate, acs_poverty_count, acs_poverty_universe,
        acs_median_income, acs_median_age,
        acs_unemployment_rate, acs_unemployed, acs_employed,
        acs_median_home_value, acs_total_pop,
        acs_white_pop, acs_black_pop, acs_hispanic_pop, acs_asian_pop,
        latitude, longitude, tract_fips,
        ROUND(
            COALESCE(acs_poverty_rate, 0) * 100.0 * 3.0
            + COALESCE((100.0 - acs_median_income / 1000.0) / 10.0, 0)
            + COALESCE(acs_unemployment_rate * 100.0 * 2.0, 0)
            + COALESCE((acs_median_age - 30.0) / 5.0, 0)
            + CASE WHEN tract_fips IS NOT NULL AND tract_fips != '' THEN 2.0 ELSE 0 END
        , 1) as need_score
    FROM churches
    WHERE denomination = 'Southern Baptist Convention'
        AND state = 'SC'
        AND acs_poverty_rate IS NOT NULL
        AND acs_median_income IS NOT NULL
    ORDER BY need_score DESC
    LIMIT ?
""", (TOP_N,)).fetchall()

now = datetime.now().strftime('%B %d, %Y at %I:%M %p')

def pct(v):
    return f'{v*100:.1f}%' if v is not None else 'N/A'
def dollar(v):
    return f'${v:,.0f}' if v is not None else 'N/A'
def comma(v):
    return f'{v:,.0f}' if v is not None else 'N/A'
def fmt(v, d='N/A'):
    return v if v and str(v).strip() else d

md = []
md.append(f'# South Carolina SBC Church Needs Assessment Report')
md.append(f'')
md.append(f'**Generated:** {now}')
md.append(f'')
md.append(f'**Scope:** {comma(total)} SBC churches in South Carolina, ')
md.append(f'ranked by composite need score across poverty, unemployment, low income, elderly population, and food access.')
md.append(f'')
md.append(f'---')
md.append(f'')
md.append(f'## Executive Summary')
md.append(f'')
avg_pov = sum(r['acs_poverty_rate'] or 0 for r in rows) / len(rows) * 100
avg_inc = sum(r['acs_median_income'] or 0 for r in rows) / len(rows)
avg_unemp = sum(r['acs_unemployment_rate'] or 0 for r in rows) / len(rows) * 100
md.append(f'This report identifies the {TOP_N} neediest SBC churches in South Carolina. ')
md.append(f'These churches serve communities averaging **{avg_pov:.1f}%** poverty, ')
md.append(f'median incomes of **${avg_inc:,.0f}**, ')
md.append(f'and **{avg_unemp:.1f}%** unemployment.')
md.append(f'')
md.append(f'---')
md.append(f'')
md.append(f'## Top {TOP_N} SC SBC Churches — Ranked by Need')
md.append(f'')
md.append(f'| # | Church | City | Poverty | Income | Unempl. | Age | Score |')
md.append(f'|---|--------|------|---------|--------|---------|-----|-------|')
for i, r in enumerate(rows, 1):
    name = r['name'][:45] if r['name'] else '?'
    city = r['city'][:18] if r['city'] else ''
    md.append(f'| {i} | {name} | {city} | {pct(r["acs_poverty_rate"])} | {dollar(r["acs_median_income"])} | {pct(r["acs_unemployment_rate"])} | {r["acs_median_age"] or "-"} | {r["need_score"]} |')

md.append(f'')
md.append(f'---')
md.append(f'')
md.append(f'## Detailed Church Profiles')
md.append(f'')

for i, r in enumerate(rows, 1):
    md.append(f'### {i}. {r["name"]}')
    md.append(f'')
    md.append(f'**Location:** {fmt(r["address"])}, {fmt(r["city"])}, SC {fmt(r["zip"])}')
    md.append(f'')
    md.append(f'| Field | Value |')
    md.append(f'|-------|-------|')
    md.append(f'| **Website** | {fmt(r["website"], "—")} |')
    md.append(f'| **Phone** | {fmt(r["phone"], "—")} |')
    md.append(f'| **EIN** | {fmt(r["ein"], "—")} |')
    md.append(f'| **Pastor** | {fmt(r["pastor_name"], "—")} |')
    md.append(f'| **Source** | {fmt(r["source"], "—")} |')
    if r['latitude']:
        md.append(f'| **Coordinates** | {r["latitude"]:.5f}, {r["longitude"]:.5f} |')
    md.append(f'')
    md.append(f'#### Demographics')
    md.append(f'')
    md.append(f'| Measure | Value |')
    md.append(f'|---------|-------|')
    md.append(f'| **Poverty Rate** | {pct(r["acs_poverty_rate"])} ({comma(r["acs_poverty_count"])} / {comma(r["acs_poverty_universe"])}) |')
    md.append(f'| **Median Household Income** | {dollar(r["acs_median_income"])} |')
    md.append(f'| **Median Age** | {fmt(r["acs_median_age"])} |')
    md.append(f'| **Unemployment** | {pct(r["acs_unemployment_rate"])} |')
    md.append(f'| **Median Home Value** | {dollar(r["acs_median_home_value"])} |')
    md.append(f'| **Total Population** | {comma(r["acs_total_pop"])} |')
    
    # Race
    pops = [(r['acs_white_pop'], 'White'), (r['acs_black_pop'], 'Black'), (r['acs_hispanic_pop'], 'Hispanic'), (r['acs_asian_pop'], 'Asian')]
    tp = sum(p[0] or 0 for p in pops)
    if tp > 0:
        md.append(f'')
        md.append(f'**Racial Composition:**')
        for val, label in pops:
            if val:
                md.append(f'- {label}: {comma(val)} ({val/tp*100:.1f}%)')
    
    if r['website']:
        md.append(f'')
        md.append(f'**Website:** [{r["website"]}]({r["website"]})')
    if r['tract_fips']:
        md.append(f'')
        md.append(f'**Census Tract:** [{r["tract_fips"]}](https://censusreporter.org/profiles/14000US{r["tract_fips"]}/)')
    md.append(f'')
    md.append(f'---')
    md.append(f'')

md.append(f'## Methodology')
md.append(f'')
md.append(f'Composite need score: Poverty (×3) + Unemployment (×2) + Low Income + Elderly + Food Access')
md.append(f'')
md.append(f'*Report generated by GrantWizard — {now}*')

path = os.path.join(OUT_DIR, 'sbc_sc_neediest_report.md')
with open(path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(md))
print(f'\nReport: {path}')

print(f'\n=== Summary ===')
print(f'Average poverty: {avg_pov:.1f}%')
print(f'Average income: ${avg_inc:,.0f}')
print(f'Average unemployment: {avg_unemp:.1f}%')
print(f'Top 5:')
for i, r in enumerate(rows[:5], 1):
    print(f'  {i}. {r["name"]} — {r["city"]} — {pct(r["acs_poverty_rate"])} poverty')

conn.close()
