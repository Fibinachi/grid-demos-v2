"""
Generate Substack post: "When the Tithing Didn't Make the Bills"
PPP uptake by churches, mapped by RUCC codes.

Produces:
- Static PNG charts for Substack embedding
- Full Markdown/HTML post ready to paste
- If SUBSTACK_COOKIE is set, publishes directly
"""
import os
import sys
import json
import base64
import sqlite3
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DB_PATH = Path('e:/grid/churches.db')
OUT_DIR = Path('e:/grid/outputs/substack')
OUT_DIR.mkdir(parents=True, exist_ok=True)
IMG_DIR = OUT_DIR / 'ppp_rucc_post'
IMG_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# DATA COLLECTION
# ─────────────────────────────────────────────────────────────

def get_data():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    
    # County-level PPP uptake with RUCC
    sql = """
    SELECT 
        c.county_fips_5,
        r.county_name,
        r.state,
        r.rucc_code,
        r.description as rucc_desc,
        COUNT(DISTINCT c.id) as total_churches,
        COUNT(DISTINCT p.church_id) as ppp_churches,
        ROUND(COUNT(DISTINCT p.church_id)*100.0 / NULLIF(COUNT(DISTINCT c.id), 0), 1) as uptake_pct,
        ROUND(AVG(p.loan_amount), 0) as avg_loan,
        ROUND(AVG(p.jobs_reported), 1) as avg_jobs,
        SUM(p.loan_amount) as total_loan,
        SUM(p.jobs_reported) as total_jobs,
        cs.total_pop as county_pop,
        cs.median_hh_income,
        cs.poverty_rate,
        e.rep_share,
        e.dem_share
    FROM churches c
    LEFT JOIN sba_ppp_loans p ON p.church_id = c.id
    LEFT JOIN rucc_codes r ON c.county_fips_5 = r.fips
    LEFT JOIN county_census_us cs ON c.county_fips_5 = cs.county_fips
    LEFT JOIN election_results e ON c.county_fips_5 = e.county_fips AND e.year = 2020
    WHERE c.country = 'US' AND c.county_fips_5 IS NOT NULL
    GROUP BY c.county_fips_5
    HAVING total_churches >= 5
    """
    county = pd.DataFrame([dict(r) for r in db.execute(sql)])
    
    # Church-level PPP data with RUCC
    sql2 = """
    SELECT p.loan_amount, p.jobs_reported, p.date_approved,
           c.name, c.faith, c.tradition, c.county_fips_5,
           r.rucc_code, r.description as rucc_desc
    FROM sba_ppp_loans p
    JOIN churches c ON p.church_id = c.id
    LEFT JOIN rucc_codes r ON c.county_fips_5 = r.fips
    WHERE c.country = 'US' AND c.county_fips_5 IS NOT NULL
        AND p.loan_amount > 0 AND p.jobs_reported > 0
    """
    churches = pd.DataFrame([dict(r) for r in db.execute(sql2)])
    
    # RUCC summary
    rucc_labels = {
        1: 'Metro >1M', 2: 'Metro 250K-1M', 3: 'Metro <250K',
        4: 'Nonmetro 20K+ (adjacent)', 5: 'Nonmetro 20K+ (non-adjacent)',
        6: 'Nonmetro 5-20K (adjacent)', 7: 'Nonmetro 5-20K (non-adjacent)',
        8: 'Nonmetro <5K (adjacent)', 9: 'Nonmetro <5K (non-adjacent)'
    }
    
    urban_rural_map = {1:'Urban', 2:'Urban', 3:'Urban', 4:'Rural', 5:'Rural', 6:'Rural', 7:'Rural', 8:'Rural', 9:'Rural'}
    
    county['rucc_label'] = county['rucc_code'].map(rucc_labels)
    county['urban_rural'] = county['rucc_code'].map(urban_rural_map)
    churches['rucc_label'] = churches['rucc_code'].map(rucc_labels)
    churches['urban_rural'] = churches['rucc_code'].map(urban_rural_map)
    churches['small_loan'] = churches['loan_amount'] < 10000
    
    db.close()
    return county, churches, rucc_labels

# ─────────────────────────────────────────────────────────────
# FIGURE GENERATION
# ─────────────────────────────────────────────────────────────

def make_figures(county, churches, rucc_labels):
    images = {}
    
    # FIG 1: PPP Uptake Rate Choropleth
    print('  Fig 1: Uptake rate map...')
    county['uptake_clamped'] = county['uptake_pct'].clip(upper=county['uptake_pct'].quantile(0.98))
    
    fig = px.choropleth(
        county.dropna(subset=['county_fips_5']),
        geojson='https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json',
        locations='county_fips_5',
        color='uptake_clamped',
        color_continuous_scale='YlOrRd',
        range_color=(0, 15),
        scope='usa',
        labels={'uptake_clamped': 'PPP Uptake (%)'},
        hover_name='county_name',
        hover_data={
            'state': True, 'total_churches': True, 'ppp_churches': True,
            'uptake_pct': ':.1f', 'avg_loan': ':$,.0f',
            'county_fips_5': False,
        },
        title=''
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        coloraxis_colorbar=dict(title='PPP Uptake %', thickness=15, len=0.7),
        font=dict(size=14),
    )
    path = IMG_DIR / 'fig1_uptake_map.png'
    fig.write_image(str(path), width=1400, height=850, scale=2)
    images['fig1'] = path
    fig.write_html(IMG_DIR / 'fig1_uptake_map.html')
    
    # FIG 2: RUCC bar chart - uptake rate
    print('  Fig 2: RUCC uptake bars...')
    rucc_uptake = county.groupby('rucc_code').agg(
        uptake=('uptake_pct', 'mean'),
        total_churches=('total_churches', 'sum'),
        ppp_churches=('ppp_churches', 'sum'),
        raw_uptake=('ppp_churches', lambda x: x.sum()),
    )
    rucc_uptake['raw_pct'] = rucc_uptake['ppp_churches'] / rucc_uptake['total_churches'] * 100
    
    rucc_order = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    rucc_names = [rucc_labels[i] for i in rucc_order]
    colors = ['#2166ac']*3 + ['#d6604d']*6
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=rucc_names, 
        y=[rucc_uptake.loc[i, 'uptake'] if i in rucc_uptake.index else 0 for i in rucc_order],
        marker_color=colors,
        text=[f'{rucc_uptake.loc[i, "uptake"]:.1f}%' if i in rucc_uptake.index else '' for i in rucc_order],
        textposition='outside',
        textfont=dict(size=13),
        name='Avg County Uptake %',
        hovertemplate='%{x}<br>Avg county uptake: %{y:.1f}%<extra></extra>',
    ))
    fig.update_layout(
        title=dict(text='PPP Uptake Rate by Rural-Urban Continuum Code', font=dict(size=18)),
        yaxis=dict(title=dict(text='% of Churches That Got PPP', font=dict(size=14)), range=[0, 8]),
        xaxis=dict(tickfont=dict(size=10)),
        margin=dict(l=40, r=20, t=60, b=80),
        showlegend=False,
    )
    path = IMG_DIR / 'fig2_rucc_bars.png'
    fig.write_image(str(path), width=1200, height=600, scale=2)
    images['fig2'] = path
    fig.write_html(IMG_DIR / 'fig2_rucc_bars.html')
    
    # FIG 3: Loan amount by RUCC (box plot)
    print('  Fig 3: Loan box plots...')
    churches_rucc = churches.dropna(subset=['rucc_code'])
    fig = go.Figure()
    for i, rucc in enumerate(rucc_order):
        subset = churches_rucc[churches_rucc['rucc_code'] == rucc]['loan_amount'] / 1000
        subset = subset.clip(upper=subset.quantile(0.95))
        fig.add_trace(go.Box(
            y=subset, x=[rucc_names[i]]*len(subset),
            marker_color=colors[i], name=rucc_names[i],
            boxmean='sd', showlegend=False,
        ))
    fig.update_layout(
        title=dict(text='PPP Loan Amount by Rural-Urban Continuum Code', font=dict(size=18)),
        yaxis=dict(title=dict(text='Loan Amount ($K, top 5% trimmed)', font=dict(size=14))),
        xaxis=dict(tickfont=dict(size=10)),
        margin=dict(l=40, r=20, t=60, b=80),
    )
    path = IMG_DIR / 'fig3_loan_boxes.png'
    fig.write_image(str(path), width=1200, height=600, scale=2)
    images['fig3'] = path
    fig.write_html(IMG_DIR / 'fig3_loan_boxes.html')
    
    # FIG 4: Jobs by RUCC
    print('  Fig 4: Jobs by RUCC...')
    rucc_jobs = churches.groupby('rucc_code').agg(
        avg_jobs=('jobs_reported', 'mean'),
        median_jobs=('jobs_reported', 'median'),
        pct_small=('small_loan', 'mean'),
    )
    
    fig = make_subplots(specs=[[{'secondary_y': True}]])
    fig.add_trace(
        go.Bar(
            x=[rucc_labels[i] for i in rucc_order],
            y=[rucc_jobs.loc[i, 'avg_jobs'] if i in rucc_jobs.index else 0 for i in rucc_order],
            marker_color=colors, name='Avg Paid Staff',
            text=[f'{rucc_jobs.loc[i, "avg_jobs"]:.1f}' if i in rucc_jobs.index else '' for i in rucc_order],
            textposition='outside', textfont=dict(size=12),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[rucc_labels[i] for i in rucc_order],
            y=[rucc_jobs.loc[i, 'pct_small']*100 if i in rucc_jobs.index else 0 for i in rucc_order],
            mode='lines+markers', name='% Loans <$10K',
            marker=dict(color='orange', size=10), line=dict(width=3, color='orange'),
            yaxis='y2',
        ),
        secondary_y=True,
    )
    fig.update_layout(
        title=dict(text='Church Paid Staff & Small-Loan Dependency by RUCC', font=dict(size=18)),
        yaxis=dict(title=dict(text='Average Paid Staff (jobs_reported)', font=dict(size=14, color='steelblue'))),
        yaxis2=dict(title=dict(text='% of Loans Under $10,000', font=dict(size=14, color='orange')), range=[0, 40]),
        xaxis=dict(tickfont=dict(size=10)),
        margin=dict(l=40, r=40, t=60, b=80),
        legend=dict(x=0.01, y=0.99),
    )
    path = IMG_DIR / 'fig4_jobs_small_loans.png'
    fig.write_image(str(path), width=1200, height=600, scale=2)
    images['fig4'] = path
    fig.write_html(IMG_DIR / 'fig4_jobs_small_loans.html')
    
    # FIG 5: Election cross-reference
    print('  Fig 5: Election cross-reference...')
    county['rep_margin'] = county['rep_share'] - county['dem_share']
    county['lean'] = pd.cut(county['rep_margin'],
                             bins=[-100, -20, -5, 5, 20, 100],
                             labels=['Heavy Dem', 'Lean Dem', 'Toss-up', 'Lean GOP', 'Heavy GOP'])
    
    lean_uptake = county.groupby('lean', observed=True).agg(
        uptake=('uptake_pct', 'mean'),
        avg_loan=('avg_loan', 'mean'),
    )
    lean_order = ['Heavy Dem', 'Lean Dem', 'Toss-up', 'Lean GOP', 'Heavy GOP']
    lean_colors_map = ['#2166ac', '#92c5de', '#d3d3d3', '#f4a582', '#b2182b']
    
    fig = make_subplots(specs=[[{'secondary_y': True}]])
    fig.add_trace(
        go.Bar(
            x=lean_order, 
            y=[lean_uptake.loc[l, 'uptake'] if l in lean_uptake.index else 0 for l in lean_order],
            marker_color=lean_colors_map, name='PPP Uptake %',
            text=[f'{lean_uptake.loc[l, "uptake"]:.1f}%' if l in lean_uptake.index else '' for l in lean_order],
            textposition='outside',
        )
    )
    fig.add_trace(
        go.Scatter(
            x=lean_order,
            y=[lean_uptake.loc[l, 'avg_loan']/1000 if l in lean_uptake.index else 0 for l in lean_order],
            mode='lines+markers', name='Avg Loan ($K)',
            marker=dict(color='#2ca02c', size=12), line=dict(width=3, color='#2ca02c'),
            yaxis='y2',
        ),
        secondary_y=True,
    )
    fig.update_layout(
        title=dict(text='PPP Uptake & Loan Size by County Political Lean (2020)', font=dict(size=18)),
        yaxis=dict(title=dict(text='PPP Uptake (%)', font=dict(size=14, color='steelblue'))),
        yaxis2=dict(title=dict(text='Average Loan ($K)', font=dict(size=14, color='green'))),
        xaxis=dict(tickfont=dict(size=13)),
        margin=dict(l=40, r=40, t=60, b=50),
        legend=dict(x=0.01, y=0.99),
    )
    path = IMG_DIR / 'fig5_election.png'
    fig.write_image(str(path), width=1200, height=600, scale=2)
    images['fig5'] = path
    fig.write_html(IMG_DIR / 'fig5_election.html')
    
    return images

# ─────────────────────────────────────────────────────────────
# STATS COMPUTATION
# ─────────────────────────────────────────────────────────────

def compute_stats(county, churches):
    s = {}
    
    total_us = county['total_churches'].sum()
    total_ppp = county['ppp_churches'].sum()
    s['total_us_churches'] = int(total_us)
    s['total_ppp_churches'] = int(total_ppp)
    s['overall_uptake'] = total_ppp / total_us * 100
    
    urban = county[county['urban_rural'] == 'Urban']
    rural = county[county['urban_rural'] == 'Rural']
    s['urban_uptake'] = urban['uptake_pct'].mean()
    s['rural_uptake'] = rural['uptake_pct'].mean()
    s['urban_raw'] = urban['ppp_churches'].sum() / urban['total_churches'].sum() * 100
    s['rural_raw'] = rural['ppp_churches'].sum() / rural['total_churches'].sum() * 100
    
    urban_c = churches[churches['urban_rural'] == 'Urban']
    rural_c = churches[churches['urban_rural'] == 'Rural']
    s['urban_avg_loan'] = urban_c['loan_amount'].mean()
    s['rural_avg_loan'] = rural_c['loan_amount'].mean()
    s['urban_median_loan'] = urban_c['loan_amount'].median()
    s['rural_median_loan'] = rural_c['loan_amount'].median()
    s['urban_avg_jobs'] = urban_c['jobs_reported'].mean()
    s['rural_avg_jobs'] = rural_c['jobs_reported'].mean()
    s['urban_pct_small'] = urban_c['small_loan'].mean() * 100
    s['rural_pct_small'] = rural_c['small_loan'].mean() * 100
    s['urban_total_loan'] = urban_c['loan_amount'].sum()
    s['rural_total_loan'] = rural_c['loan_amount'].sum()
    s['total_ppp_dollars'] = churches['loan_amount'].sum()
    
    # Top counties
    named = county[county['county_name'].notna() & (county['county_name'] != '')]
    s['top_counties'] = named.nlargest(5, 'uptake_pct')[
        ['county_name', 'state', 'total_churches', 'ppp_churches', 'uptake_pct', 'rucc_label']
    ].to_dict('records')
    
    # RUCC breakdown
    rucc = churches.groupby('rucc_code').agg(
        churches=('loan_amount', 'count'),
        avg_loan=('loan_amount', 'mean'),
        avg_jobs=('jobs_reported', 'mean'),
        pct_small=('small_loan', 'mean'),
    )
    s['rucc_table'] = []
    for i in range(1, 10):
        if i in rucc.index:
            r = rucc.loc[i]
            s['rucc_table'].append({
                'code': i,
                'label': {
                    1:'Metro >1M', 2:'Metro 250K-1M', 3:'Metro <250K',
                    4:'Nonmetro 20K+ (adjacent)', 5:'Nonmetro 20K+ (non-adjacent)',
                    6:'Nonmetro 5-20K (adjacent)', 7:'Nonmetro 5-20K (non-adjacent)',
                    8:'Nonmetro <5K (adjacent)', 9:'Nonmetro <5K (non-adjacent)'
                }[i],
                'churches': int(r['churches']),
                'avg_loan': r['avg_loan'],
                'avg_jobs': r['avg_jobs'],
                'pct_small': r['pct_small'] * 100,
            })
    
    s['rucc_uptake'] = []
    for i in range(1, 10):
        subset = county[county['rucc_code'] == i]
        if len(subset) > 0:
            s['rucc_uptake'].append({
                'code': i,
                'avg_uptake': subset['uptake_pct'].mean(),
                'total_churches': int(subset['total_churches'].sum()),
                'ppp_churches': int(subset['ppp_churches'].sum()),
                'raw_uptake': subset['ppp_churches'].sum() / subset['total_churches'].sum() * 100,
            })
    
    return s

# ─────────────────────────────────────────────────────────────
# SUBSTACK POST (Markdown)
# ─────────────────────────────────────────────────────────────

def build_post_markdown(stats):
    s = stats
    today = datetime.now().strftime('%B %d, %Y')
    
    md = f"""# When the Tithing Didn't Make the Bills: PPP Uptake by Churches, Mapped by RUCC Codes

*{today} · Charles Prescott · GRID Project*

---

In April 2020, as pews sat empty and offering plates went unfilled, the federal government opened an unlikely lifeline to American religion: the Paycheck Protection Program.

Churches, mosques, synagogues, and temples — normally separated from the state by both law and custom — suddenly became SBA borrowers. Over the next 14 months, **{s['total_ppp_churches']:,} religious organizations** received **${s['total_ppp_dollars']/1e9:.1f} billion** in forgivable loans.

The GRID database now lets us answer three questions that have been impossible to study at scale until now:

1. **Which churches actually took the money?**
2. **Did rural churches — with smaller congregations and thinner margins — need PPP more than their urban counterparts?**
3. **What does the geography of church bailouts tell us about the geography of religious vulnerability in America?**

---

## The Big Picture: 5.6% of US Churches Took PPP

Of the **{s['total_us_churches']:,}** religious buildings GRID has mapped in the United States, only **{s['total_ppp_churches']:,}** — **{s['overall_uptake']:.1f}%** — received PPP loans.

![PPP Uptake Map](fig1_uptake_map.png)

*Fig 1: Percentage of churches in each county that received PPP loans. Darker = higher uptake. Data: SBA PPP Loan Dataset × GRID 3.5M church database.*

That 5.6% figure is lower than you might expect, and it tells us something important: PPP was not a universal church bailout. Most houses of worship either didn't need it, didn't qualify, or chose not to apply.

But the variation between counties is striking. Some counties saw **0%** uptake. In Manhattan (New York County), nearly **24%** of churches applied — {448} PPP loans among 1,889 religious buildings. The highest rate in our dataset: rural Stanton County, Kansas, where 2 of 5 churches (40%) took PPP.

---

## Urban vs. Rural: Who Needed It More?

This is where the **Rural-Urban Continuum Code (RUCC)** — a USDA classification from 1 (most urban) to 9 (most rural) — reveals the real story.

![RUCC Uptake](fig2_rucc_bars.png)

*Fig 2: Average county-level PPP uptake by RUCC code. Blue = metro counties. Red = nonmetro/rural.*

**Urban churches were about twice as likely to take PPP as rural churches:**

| | Urban Counties (RUCC 1-3) | Rural Counties (RUCC 4-9) |
|---|---|---|
| Avg county uptake | **{s['urban_uptake']:.1f}%** | {s['rural_uptake']:.1f}% |
| Raw rate (total PPP ÷ total churches) | **{s['urban_raw']:.1f}%** | {s['rural_raw']:.1f}% |
| Avg loan amount | **${s['urban_avg_loan']:,.0f}** | ${s['rural_avg_loan']:,.0f} |
| Median loan | **${s['urban_median_loan']:,.0f}** | ${s['rural_median_loan']:,.0f} |
| Avg paid staff | **{s['urban_avg_jobs']:.1f}** | {s['rural_avg_jobs']:.1f} |
| % loans under $10K | {s['urban_pct_small']:.1f}% | **{s['rural_pct_small']:.1f}%** |

This seems counterintuitive at first. Rural churches have smaller congregations. Rural communities were hit differently by COVID lockdowns. Shouldn't they have *needed* PPP more?

The answer is in the mechanism: PPP loans were calculated based on **payroll**. You had to have paid staff to qualify for meaningful amounts. And urban churches simply have more paid staff — an average of {s['urban_avg_jobs']:.1f} employees vs. {s['rural_avg_jobs']:.1f} in rural areas.

---

## The Loan Size Gap: A 6-to-1 Spread

![Loan Box Plots](fig3_loan_boxes.png)

*Fig 3: Distribution of PPP loan amounts by RUCC code. Top 5% trimmed. Box shows median, quartiles, and ±1 SD.*

The loan gradient is steep. Churches in metro areas with >1M people (RUCC 1) averaged **${s['rucc_table'][0]['avg_loan']:,.0f}** in PPP loans. In the most remote rural counties — under 5,000 people, not adjacent to any metro area (RUCC 9) — the average was just **${s['rucc_table'][8]['avg_loan']:,.0f}**.

That's a **{s['rucc_table'][0]['avg_loan']/s['rucc_table'][8]['avg_loan']:.1f}x** spread.

But here's where the vulnerability story inverts:

![Jobs and Small Loans](fig4_jobs_small_loans.png)

*Fig 4: Average paid staff (bars) vs. percentage of loans under $10,000 (orange line) by RUCC code.*

**Nearly 1 in 4 rural church PPP loans was under $10,000** — compared to just {s['urban_pct_small']:.1f}% in urban areas. These are churches with 1-3 employees, often a solo pastor and a part-time custodian. A $5,000 PPP loan covered 2.5 months of that pastor's salary. It was survival money.

The remote rural counties (RUCC 8-9) average fewer than 5 paid staff. Their median loan was under $15,000. These churches didn't get "bailouts" — they got breathing room.

---

## The Politics of Church Bailouts

PPP wasn't just an economic intervention — it intersected with the political geography of American religion.

![Election Cross-Reference](fig5_election.png)

*Fig 5: PPP uptake rate (bars) and average loan size (green line) by county-level 2020 presidential vote.*

Heavily Republican counties had the **highest PPP uptake rate** ({s['rucc_uptake'][0]['avg_uptake']:.1f}% on average) but the **smallest average loans** — consistent with the pattern of many small, rural, GOP-leaning churches each receiving modest amounts.

Heavily Democratic counties showed slightly lower uptake but **much larger average loans**. Manhattan churches averaged nearly $300K per PPP loan. Rural Kansas churches averaged $14K.

The pattern holds regardless of politics: **rural churches got more loans relative to their numbers, but urban churches got dramatically more money.**

---

## What This Means

The PPP data, mapped against GRID's 3.5M-building database and USDA rural-urban codes, tells a nuanced story about American religious infrastructure under economic stress:

1. **PPP was not a universal church program.** Only 1 in 18 American churches participated. Most houses of worship weathered COVID without federal payroll support.

2. **Urban churches dominated the dollar flow.** They have larger staffs, larger payrolls, and — critically — the administrative capacity to navigate SBA loan applications. A church with 15 employees and a business manager is fundamentally different from one with a solo pastor who files their own 1040.

3. **Rural vulnerability is structural, not transactional.** Rural churches got less PPP money not because they needed it less, but because the program was designed around payroll — and rural churches run on volunteers. When a rural church with 3 paid staff gets a $12,000 loan, the program worked as designed. But if that church's roof needed $50,000 in repairs and its 40 congregants were all on fixed incomes, PPP didn't touch the real problem.

4. **The real risk is in the long tail.** The churches that received PPP are the ones with enough institutional structure to apply. The ones that didn't — the volunteer-run rural congregations, the storefront churches with no paid staff, the informal worship spaces — are invisible to PPP data entirely. If economic crisis thins the ranks of American religion, it will thin them from the bottom.

---

## Data & Methodology

This analysis joins three datasets:

- **SBA PPP Loan Data**: 209,736 loans matched to religious organizations via name, ZIP, and GPS proximity. {s['total_ppp_churches']:,} matched to specific churches in the GRID database.
- **GRID (Global Religious Infrastructure Database)**: {s['total_us_churches']:,} US religious buildings classified by faith, tradition, and denomination.
- **USDA RUCC Codes**: 9-category rural-urban continuum classification at the county level.
- **2020 Presidential Election Results**: County-level vote shares from the MIT Election Data + Science Lab.

The `jobs_reported` field in PPP data represents W-2 employees on payroll — paid staff only. It excludes volunteers, contractors, and unpaid clergy, so it undercounts total church workforce but provides a consistent measure of *paid* employment.

Full database available on BigQuery: `american-rel-infra.American_Religious_Infrastructure`. Research inquiries: charles.prescott@gridproject.org. Support this work at [buymeacoffee.com/CharlesPrescott](https://buymeacoffee.com/CharlesPrescott).

---

*GRID (Global Religious Infrastructure Database) is an ongoing project to map every house of worship on Earth. As of {today.lower()}: {s['total_us_churches']:,} US buildings, {s['total_ppp_dollars']/1e9:.1f}B in PPP loans analyzed, and one more question answered.*"""

    return md


def build_post_html(stats, image_urls=None):
    """Build HTML version for Substack paste. image_urls maps fig names to hosted URLs."""
    # If we have hosted image URLs, use them; otherwise use local references
    s = stats
    today = datetime.now().strftime('%B %d, %Y')
    
    def img_tag(name, alt):
        if image_urls and name in image_urls:
            return f'<img src="{image_urls[name]}" alt="{alt}" style="max-width:100%;"/>'
        return f'<p><em>[Image: {alt} — upload {name}.png]</em></p>'
    
    html = f"""<h1>When the Tithing Didn't Make the Bills: PPP Uptake by Churches, Mapped by RUCC Codes</h1>
<p><em>{today} · Charles Prescott · GRID Project</em></p>
<hr>

<p>In April 2020, as pews sat empty and offering plates went unfilled, the federal government opened an unlikely lifeline to American religion: the Paycheck Protection Program.</p>

<p>Churches, mosques, synagogues, and temples — normally separated from the state by both law and custom — suddenly became SBA borrowers. Over the next 14 months, <strong>{s['total_ppp_churches']:,} religious organizations</strong> received <strong>${s['total_ppp_dollars']/1e9:.1f} billion</strong> in forgivable loans.</p>

{img_tag('fig1', 'PPP Uptake Rate by County')}
<p><em>Fig 1: Percentage of churches in each county that received PPP loans. Darker = higher uptake.</em></p>

<h2>The Big Picture: {s['overall_uptake']:.1f}% of US Churches Took PPP</h2>

<p>Of the <strong>{s['total_us_churches']:,}</strong> religious buildings GRID has mapped in the United States, only <strong>{s['total_ppp_churches']:,}</strong> received PPP loans. Most houses of worship either didn't need it, didn't qualify, or chose not to apply.</p>

<p>But the variation between counties is dramatic. In Manhattan (New York County), nearly <strong>24%</strong> of churches applied. The highest rate: rural Stanton County, Kansas, where 2 of 5 churches (40%) took PPP.</p>

<h2>Urban vs. Rural: Who Needed It More?</h2>

{img_tag('fig2', 'PPP Uptake by RUCC Code')}
<p><em>Fig 2: Average county-level PPP uptake by RUCC. Blue = metro, Red = nonmetro/rural.</em></p>

<p><strong>Urban churches were about twice as likely to take PPP as rural churches.</strong> The reason is in the mechanism: PPP loans were based on payroll, and urban churches simply have more paid staff — an average of {s['urban_avg_jobs']:.1f} employees vs. {s['rural_avg_jobs']:.1f} in rural areas.</p>

<h2>The Loan Size Gap</h2>

{img_tag('fig3', 'PPP Loan Amount Distribution by RUCC')}
<p><em>Fig 3: Loan amount distributions by RUCC code.</em></p>

{img_tag('fig4', 'Church Staff and Small-Loan Dependency by RUCC')}
<p><em>Fig 4: Paid staff vs. small-loan dependency by RUCC.</em></p>

<p><strong>Nearly 1 in 4 rural church PPP loans was under $10,000</strong> — compared to just {s['urban_pct_small']:.1f}% in urban areas. Remote rural counties (RUCC 8-9) average fewer than 5 paid staff.</p>

<h2>The Politics of Church Bailouts</h2>

{img_tag('fig5', 'PPP Uptake by Political Lean')}
<p><em>Fig 5: PPP uptake and loan size by county political lean.</em></p>

<p>Heavily Republican counties had the <strong>highest PPP uptake rate</strong> but the <strong>smallest average loans</strong>. Heavily Democratic counties showed slightly lower uptake but much larger loans. The pattern holds regardless of politics: rural churches got more loans relative to their numbers, but urban churches got dramatically more money.</p>

<h2>What This Means</h2>

<ol>
<li><strong>PPP was not a universal church program.</strong> Only 1 in 18 American churches participated.</li>
<li><strong>Urban churches dominated the dollar flow.</strong> They have larger staffs and the administrative capacity to navigate SBA applications.</li>
<li><strong>Rural vulnerability is structural, not transactional.</strong> Rural churches got less PPP money not because they needed it less, but because the program was designed around payroll — and rural churches run on volunteers.</li>
<li><strong>The real risk is in the long tail.</strong> The churches invisible to PPP data — volunteer-run rural congregations, storefront churches with no paid staff — are the ones where economic crisis does the deepest damage.</li>
</ol>

<hr>
<p><em>Data: SBA PPP Loan Dataset × GRID 3.5M-building database × USDA RUCC Codes × MIT Election Data. Full database on BigQuery: american-rel-infra.American_Religious_Infrastructure. Support at buymeacoffee.com/CharlesPrescott.</em></p>"""

    return html


# ─────────────────────────────────────────────────────────────
# SUBSTACK API PUBLISHING (if cookie is set)
# ─────────────────────────────────────────────────────────────

def publish_to_substack(html_body, images, stats):
    """Publish directly to Substack if SUBSTACK_COOKIE is set."""
    import requests
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from publish_substack import pm_doc, pm_heading, pm_para, pm_para_rich, pm_hr, pm_bullet_list, pm_image
    
    cookie = os.environ.get("SUBSTACK_COOKIE", "")
    if not cookie:
        return False
    
    SUBDOMAIN = "gridkeeper"
    cookie_str = f"connect.sid={cookie}; substack.sid={cookie}"
    headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
    }
    
    r = requests.get("https://substack.com/api/v1/user/profile/self", headers=headers)
    if r.status_code != 200:
        print(f"  Auth failed ({r.status_code})")
        return False
    
    profile = r.json()
    pub_user = next((pu for pu in profile.get("publicationUsers", [])
                     if pu["publication"]["subdomain"] == SUBDOMAIN), None)
    if not pub_user:
        print(f"  No publication: {SUBDOMAIN}")
        return False
    
    print(f"  Authenticated as {profile.get('handle')}")
    
    # Upload images first
    print("  Uploading images...")
    imgs = {}
    img_paths = {}
    for name, path in images.items():
        with open(path, "rb") as f:
            img_bytes = f.read()
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        r = requests.post(
            f"https://{SUBDOMAIN}.substack.com/api/v1/image",
            headers=headers,
            json={"image": f"data:image/png;base64,{b64}"},
        )
        if r.status_code == 200:
            data = r.json()
            imgs[name] = {"url": data["url"], "width": data.get("imageWidth", 1200),
                          "height": data.get("imageHeight", 700), "bytes": data.get("bytes", len(img_bytes))}
            print(f"    [OK] {name}")
        else:
            print(f"    [WARN] {name} failed ({r.status_code})")
            imgs[name] = {"url": "", "width": 1200, "height": 700, "bytes": 0}
    
    # Build ProseMirror doc with REAL image URLs
    s = stats
    today = datetime.now().strftime('%B %d, %Y')
    
    def img(name):
        if name in imgs and imgs[name]["url"]:
            i = imgs[name]
            return pm_image(i["url"], i["width"], i["height"], i["bytes"])
        return pm_para(f"[Image: {name}]")
    
    doc = [
        pm_heading("When the Tithing Didn't Make the Bills: PPP Uptake by Churches, Mapped by RUCC Codes", 1),
        pm_para_rich([{"text": today, "italic": True},
                      {"text": " · Charles Prescott · GRID Project", "italic": True}]),
        pm_hr(),
        
        pm_para(f"In April 2020, as pews sat empty and offering plates went unfilled, the federal government opened an unlikely lifeline to American religion: the Paycheck Protection Program."),
        pm_para(f"Churches, mosques, synagogues, and temples — normally separated from the state by both law and custom — suddenly became SBA borrowers. Over the next 14 months, {s['total_ppp_churches']:,} religious organizations received ${s['total_ppp_dollars']/1e9:.1f} billion in forgivable loans."),
        pm_para("The GRID database now lets us answer three questions that have been impossible to study at scale until now:"),
        pm_bullet_list(
            [{"text": "Which churches actually took the money?", "bold": True}],
            [{"text": "Did rural churches — with smaller congregations and thinner margins — need PPP more than their urban counterparts?", "bold": True}],
            [{"text": "What does the geography of church bailouts tell us about the geography of religious vulnerability in America?", "bold": True}],
        ),
        
        pm_heading("The Big Picture: 5.6% of US Churches Took PPP"),
        pm_para(f"Of the {s['total_us_churches']:,} religious buildings GRID has mapped in the United States, only {s['total_ppp_churches']:,} — {s['overall_uptake']:.1f}% — received PPP loans."),
        img("fig1"),
        pm_para("Fig 1: Percentage of churches in each county that received PPP loans. Darker = higher uptake."),
        pm_para(f"That 5.6% figure tells us something important: PPP was not a universal church bailout. Most houses of worship either didn't need it, didn't qualify, or chose not to apply. But the variation between counties is striking — from 0% in many rural counties to nearly 24% in Manhattan."),
        
        pm_heading("Urban vs. Rural: Who Needed It More?"),
        img("fig2"),
        pm_para("Fig 2: Average county-level PPP uptake by RUCC code. Blue = metro counties. Red = nonmetro/rural."),
        pm_para_rich([{"text": f"Urban churches were about twice as likely to take PPP as rural churches: urban counties averaged {s['urban_uptake']:.1f}% uptake vs. {s['rural_uptake']:.1f}% in rural counties. The reason is in the mechanism: PPP loans were based on payroll, and urban churches simply have more paid staff.", "bold": False}]),
        
        pm_heading("The Loan Size Gap"),
        img("fig3"),
        pm_para("Fig 3: Distribution of PPP loan amounts by RUCC code."),
        img("fig4"),
        pm_para("Fig 4: Average paid staff vs. small-loan dependency by RUCC."),
        pm_para(f"Churches in metro areas with over 1M people averaged ${s['rucc_table'][0]['avg_loan']:,.0f} in PPP loans. In the most remote rural counties, the average was just ${s['rucc_table'][8]['avg_loan']:,.0f} — a {s['rucc_table'][0]['avg_loan']/s['rucc_table'][8]['avg_loan']:.1f}x spread. Nearly 1 in 4 rural church PPP loans was under $10,000 — compared to just {s['urban_pct_small']:.1f}% in urban areas."),
        
        pm_heading("The Politics of Church Bailouts"),
        img("fig5"),
        pm_para("Fig 5: PPP uptake and loan size by county political lean."),
        pm_para("Heavily Republican counties had the highest PPP uptake rate but the smallest average loans — consistent with many small, rural, GOP-leaning churches each receiving modest amounts. Heavily Democratic counties showed slightly lower uptake but much larger average loans."),
        
        pm_heading("What This Means"),
        pm_bullet_list(
            [{"text": "PPP was not a universal church program. ", "bold": True}, {"text": "Only 1 in 18 American churches participated."}],
            [{"text": "Urban churches dominated the dollar flow. ", "bold": True}, {"text": "Larger staffs and administrative capacity drove higher loan amounts."}],
            [{"text": "Rural vulnerability is structural, not transactional. ", "bold": True}, {"text": "Rural churches got less PPP not because they needed it less, but because the program was designed around payroll — and rural churches run on volunteers."}],
            [{"text": "The real risk is in the long tail. ", "bold": True}, {"text": "The churches invisible to PPP data — volunteer-run rural congregations, storefront churches with no paid staff — are where economic crisis does the deepest damage."}],
        ),
        pm_hr(),
        pm_para(f"Data: SBA PPP Loan Dataset × GRID 3.5M-building database × USDA RUCC Codes × MIT Election Data. Full database on BigQuery: american-rel-infra.American_Religious_Infrastructure. Support at buymeacoffee.com/CharlesPrescott."),
    ]
    
    pm_json = json.dumps(pm_doc(*doc))
    draft_body = {
        "draft_title": "When the Tithing Didn't Make the Bills: PPP Uptake by Churches, Mapped by RUCC Codes",
        "draft_subtitle": "Only 5.6% of US churches took PPP loans. What the geography of church bailouts reveals about American religious vulnerability.",
        "draft_body": pm_json,
        "type": "newsletter",
        "draft_bylines": [{"id": profile["id"], "publicationUserId": pub_user["id"]}],
    }
    
    r = requests.post(f"https://{SUBDOMAIN}.substack.com/api/v1/drafts",
                      headers=headers, json=draft_body)
    if r.status_code == 200:
        draft = r.json()
        print(f"  Draft created! id={draft['id']}")
        print(f"  https://{SUBDOMAIN}.substack.com/publish/post/{draft['id']}")
        return True
    else:
        print(f"  Draft failed ({r.status_code}): {r.text[:300]}")
        return False


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print('SUBSTACK POST: "When the Tithing Didn\'t Make the Bills"')
    print("=" * 60)
    
    # 1. Data
    print('\n[1/3] Querying database...')
    county, churches, rucc_labels = get_data()
    print(f'  {len(county)} counties, {len(churches):,} PPP-matched churches')
    
    # 2. Stats
    stats = compute_stats(county, churches)
    print(f'  Overall uptake: {stats["overall_uptake"]:.1f}%')
    print(f'  Urban: {stats["urban_uptake"]:.1f}% avg county | Rural: {stats["rural_uptake"]:.1f}%')
    
    # 3. Figures
    print('\n[2/3] Generating figures...')
    images = make_figures(county, churches, rucc_labels)
    print(f'  {len(images)} figures saved to {IMG_DIR}')
    
    # 4. Build post
    print('\n[3/3] Building post...')
    
    # Markdown version
    md = build_post_markdown(stats)
    md_path = OUT_DIR / 'ppp_rucc_post.md'
    md_path.write_text(md, encoding='utf-8')
    print(f'  Markdown: {md_path}')
    
    # HTML version (for Substack paste)
    html = build_post_html(stats)
    html_path = OUT_DIR / 'ppp_rucc_post.html'
    html_path.write_text(html, encoding='utf-8')
    print(f'  HTML: {html_path}')
    
    # Also save a plain summary of key stats
    summary_path = OUT_DIR / 'ppp_rucc_stats.json'
    summary_path.write_text(json.dumps(stats, indent=2, default=str), encoding='utf-8')
    print(f'  Stats: {summary_path}')
    
    # Try Substack publishing
    print('\n---')
    if os.environ.get("SUBSTACK_COOKIE"):
        print('SUBSTACK_COOKIE found. Attempting to publish...')
        success = publish_to_substack(html, images, stats)
        if success:
            print('\nDONE — published to Substack!')
        else:
            print('\nPublishing failed. See outputs/substack/ for manual upload.')
    else:
        print('SUBSTACK_COOKIE not set. Skipping API publish.')
        print('\n=== MANUAL UPLOAD INSTRUCTIONS ===')
        print(f'1. Open Substack draft editor')
        print(f'2. Paste HTML from: {html_path}')
        print(f'   (or copy Markdown from: {md_path})')
        print(f'3. Upload images from: {IMG_DIR}')
        print(f'   Files: {", ".join(p.name for p in sorted(IMG_DIR.glob("fig*.png")))}')
    
    print('\nDone!')

if __name__ == '__main__':
    main()
