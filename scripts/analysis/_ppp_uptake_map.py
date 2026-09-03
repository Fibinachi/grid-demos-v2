"""
PPP Uptake Rate Map: % of churches in each county that received PPP loans.
Darker = higher proportion of churches that needed COVID payroll relief.
"""
import sqlite3
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path

DB_PATH = Path('e:/grid/churches.db')
OUT_DIR = Path('e:/grid/outputs')
OUT_DIR.mkdir(exist_ok=True)

def main():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    
    print('Computing county-level PPP uptake rates...')
    
    # Per county: total churches vs PPP churches
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
    
    rows = list(db.execute(sql))
    df = pd.DataFrame([dict(r) for r in rows])
    print(f'  {len(df)} counties (with >=5 churches)')
    
    # Overall stats
    total_churches = df['total_churches'].sum()
    total_ppp = df['ppp_churches'].sum()
    print(f'  Total churches: {total_churches:,}')
    print(f'  PPP churches: {total_ppp:,}')
    print(f'  Overall uptake: {total_ppp/total_churches*100:.1f}%')
    
    # Urban/rural labels
    urban_rural_map = {1:'Urban', 2:'Urban', 3:'Urban', 4:'Rural', 5:'Rural', 6:'Rural', 7:'Rural', 8:'Rural', 9:'Rural'}
    df['urban_rural'] = df['rucc_code'].map(urban_rural_map)
    
    # Distribution of uptake rates
    print(f'\n=== Uptake Rate Distribution ===')
    print(f'  Min:    {df["uptake_pct"].min():.1f}%')
    print(f'  P10:    {df["uptake_pct"].quantile(0.10):.1f}%')
    print(f'  P25:    {df["uptake_pct"].quantile(0.25):.1f}%')
    print(f'  Median: {df["uptake_pct"].median():.1f}%')
    print(f'  P75:    {df["uptake_pct"].quantile(0.75):.1f}%')
    print(f'  P90:    {df["uptake_pct"].quantile(0.90):.1f}%')
    print(f'  Max:    {df["uptake_pct"].max():.1f}%')
    
    # Top/Bottom counties
    # Top/Bottom counties - filter to those with names
    named = df[df['county_name'].notna() & (df['county_name'] != '')]
    
    print(f'\n=== Top 10 PPP Uptake Counties ===')
    top = named.nlargest(10, 'uptake_pct')
    for _, r in top.iterrows():
        rucc = f'RUCC {int(r["rucc_code"])}' if pd.notna(r['rucc_code']) else 'RUCC N/A'
        print(f'  {r["county_name"]}, {r["state"]}: {int(r["ppp_churches"])}/{int(r["total_churches"])} = {r["uptake_pct"]:.1f}% | {rucc} | ${r["avg_loan"]:,.0f} avg loan')
    
    print(f'\n=== Bottom 10 PPP Uptake Counties ===')
    bottom = named.nsmallest(10, 'uptake_pct')
    for _, r in bottom.iterrows():
        rucc = f'RUCC {int(r["rucc_code"])}' if pd.notna(r['rucc_code']) else 'RUCC N/A'
        print(f'  {r["county_name"]}, {r["state"]}: {int(r["ppp_churches"])}/{int(r["total_churches"])} = {r["uptake_pct"]:.1f}% | {rucc}')
    
    # By RUCC
    print(f'\n=== PPP Uptake by RUCC ===')
    for rucc in sorted(df['rucc_code'].dropna().unique()):
        subset = df[df['rucc_code'] == rucc]
        avg_up = subset['uptake_pct'].mean()
        tot_c = subset['total_churches'].sum()
        tot_p = subset['ppp_churches'].sum()
        print(f'  RUCC {int(rucc)}: {avg_up:.1f}% avg uptake ({tot_p:,}/{tot_c:,} churches)')
    
    # Urban vs Rural summary
    print(f'\n=== Urban vs Rural Uptake ===')
    for label in ['Urban', 'Rural']:
        subset = df[df['urban_rural'] == label]
        avg_up = subset['uptake_pct'].mean()
        tot_c = subset['total_churches'].sum()
        tot_p = subset['ppp_churches'].sum()
        print(f'  {label}: {avg_up:.1f}% avg county uptake ({tot_p:,}/{tot_c:,} churches = {tot_p/tot_c*100:.1f}% raw)')
    
    # ──────────────────────────────────────────────
    # MAP 1: PPP Uptake Rate Choropleth
    # ──────────────────────────────────────────────
    print('\nGenerating MAP 1: PPP Uptake Rate...')
    
    # Clamp outliers for better color spread
    df['uptake_clamped'] = df['uptake_pct'].clip(upper=df['uptake_pct'].quantile(0.98))
    
    fig1 = px.choropleth(
        df,
        geojson='https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json',
        locations='county_fips_5',
        color='uptake_clamped',
        color_continuous_scale='YlOrRd',
        range_color=(0, df['uptake_clamped'].max()),
        scope='usa',
        labels={'uptake_clamped': 'PPP Uptake (%)'},
        hover_name='county_name',
        hover_data={
            'state': True,
            'total_churches': True,
            'ppp_churches': True,
            'uptake_pct': ':.1f',
            'avg_loan': ':$,.0f',
            'avg_jobs': ':.1f',
            'rucc_desc': True,
            'county_fips_5': False,
        },
        title='% of Churches That Received PPP Loans by County<br><sub>Darker = higher proportion of churches needed COVID payroll relief</sub>'
    )
    fig1.update_layout(
        margin=dict(l=0, r=0, t=60, b=0),
        coloraxis_colorbar=dict(title='PPP Uptake %'),
    )
    fig1.write_html(OUT_DIR / 'ppp_uptake_rate_map.html')
    print('  -> outputs/ppp_uptake_rate_map.html')
    
    # ──────────────────────────────────────────────
    # MAP 2: Side-by-side comparison
    # ──────────────────────────────────────────────
    print('Generating MAP 2: Uptake vs Density comparison...')
    
    df['ppp_per_100k_pop'] = (df['ppp_churches'] / df['county_pop'].clip(lower=1)) * 100000
    df['ppp_per_100k_pop'] = df['ppp_per_100k_pop'].clip(upper=df['ppp_per_100k_pop'].quantile(0.98))
    
    fig2 = make_subplots(
        rows=1, cols=2,
        subplot_titles=[
            'PPP Uptake Rate (% of churches)',
            'PPP Density (churches per 100K population)'
        ],
        specs=[[{'type': 'choropleth'}, {'type': 'choropleth'}]],
    )
    
    fig2.add_trace(
        go.Choropleth(
            geojson='https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json',
            locations=df['county_fips_5'],
            z=df['uptake_clamped'],
            colorscale='YlOrRd',
            zmin=0, zmax=df['uptake_clamped'].max(),
            marker_line_width=0,
            colorbar=dict(title='Uptake %', x=0.44),
            hovertext=[f'{n}, {s}<br>{t} churches, {p} PPP ({u:.1f}%)'
                       for n,s,t,p,u in zip(df['county_name'], df['state'], 
                                            df['total_churches'], df['ppp_churches'], df['uptake_pct'])],
            hoverinfo='text',
        ),
        row=1, col=1
    )
    
    fig2.add_trace(
        go.Choropleth(
            geojson='https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json',
            locations=df['county_fips_5'],
            z=df['ppp_per_100k_pop'],
            colorscale='YlOrRd',
            zmin=0, zmax=df['ppp_per_100k_pop'].max(),
            marker_line_width=0,
            colorbar=dict(title='Per 100K Pop', x=1.0),
            hovertext=[f'{n}, {s}<br>{p} PPP churches<br>{ppp:.1f} per 100K pop'
                       for n,s,p,ppp in zip(df['county_name'], df['state'],
                                            df['ppp_churches'], df['ppp_per_100k_pop'])],
            hoverinfo='text',
        ),
        row=1, col=2
    )
    
    fig2.update_layout(
        geo=dict(scope='usa'),
        geo2=dict(scope='usa'),
        title='PPP Church Uptake Rate vs Population Density<br><sub>Left: what % of churches got PPP | Right: PPP churches per capita</sub>',
        margin=dict(l=0, r=0, t=60, b=0),
    )
    fig2.write_html(OUT_DIR / 'ppp_uptake_vs_density.html')
    print('  -> outputs/ppp_uptake_vs_density.html')
    
    # ──────────────────────────────────────────────
    # FIGURE 3: Uptake by RUCC + Election lean
    # ──────────────────────────────────────────────
    print('Generating FIGURE 3: Uptake by RUCC & Politics...')
    
    df['rep_margin'] = df['rep_share'] - df['dem_share']
    df['lean'] = pd.cut(df['rep_margin'],
                         bins=[-100, -20, -5, 5, 20, 100],
                         labels=['Heavy Dem', 'Lean Dem', 'Toss-up', 'Lean GOP', 'Heavy GOP'])
    
    fig3 = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            'PPP Uptake by RUCC Code',
            'PPP Uptake by Political Lean',
            'Urban vs Rural: Uptake Distribution',
            'Uptake vs GOP Vote Share (county scatter)'
        ],
        vertical_spacing=0.14,
        horizontal_spacing=0.12,
    )
    
    rucc_labels = {
        1:'Metro >1M', 2:'Metro 250K-1M', 3:'Metro <250K',
        4:'Nonmetro 20K+\n(adjacent)', 5:'Nonmetro 20K+\n(non-adj)',
        6:'Nonmetro 5-20K\n(adjacent)', 7:'Nonmetro 5-20K\n(non-adj)',
        8:'Nonmetro <5K\n(adjacent)', 9:'Nonmetro <5K\n(non-adj)'
    }
    
    # Bar: uptake by RUCC
    rucc_uptake = df.groupby('rucc_code')['uptake_pct'].mean()
    rucc_order = [int(i) for i in sorted(df['rucc_code'].dropna().unique())]
    rucc_names = [rucc_labels.get(i, str(i)) for i in rucc_order]
    colors_rucc = ['#2166ac']*3 + ['#d6604d']*6
    
    fig3.add_trace(
        go.Bar(x=rucc_names, y=[rucc_uptake.get(i, 0) for i in rucc_order],
               marker_color=colors_rucc,
               text=[f'{rucc_uptake.get(i,0):.1f}%' for i in rucc_order],
               textposition='outside', name='Uptake %'),
        row=1, col=1
    )
    
    # Bar: uptake by political lean
    lean_uptake = df.groupby('lean', observed=True)['uptake_pct'].mean()
    lean_order = ['Heavy Dem', 'Lean Dem', 'Toss-up', 'Lean GOP', 'Heavy GOP']
    lean_colors = ['#2166ac', '#92c5de', '#f7f7f7', '#f4a582', '#b2182b']
    fig3.add_trace(
        go.Bar(x=lean_order, y=[lean_uptake.get(l, 0) for l in lean_order],
               marker_color=lean_colors,
               text=[f'{lean_uptake.get(l,0):.1f}%' for l in lean_order],
               textposition='outside', name='Uptake %'),
        row=1, col=2
    )
    
    # Histogram: urban vs rural uptake distribution
    for label, color in [('Urban', '#2166ac'), ('Rural', '#d6604d')]:
        subset = df[df['urban_rural'] == label]['uptake_pct']
        fig3.add_trace(
            go.Histogram(x=subset, nbinsx=40, opacity=0.6,
                        marker_color=color, name=label),
            row=2, col=1
        )
    
    # Scatter: uptake vs GOP share
    scatter_df = df.dropna(subset=['rep_share', 'uptake_pct'])
    fig3.add_trace(
        go.Scatter(
            x=scatter_df['rep_share'], y=scatter_df['uptake_pct'],
            mode='markers',
            marker=dict(
                color=scatter_df['rucc_code'].map(lambda x: '#2166ac' if x in [1,2,3] else '#d6604d'),
                size=4, opacity=0.5,
            ),
            text=[f'{n}, {s}<br>RUCC {int(r)}<br>Uptake: {u:.1f}%<br>{t} churches, {p} PPP<br>GOP: {g:.1f}%'
                  for n,s,r,u,t,p,g in zip(scatter_df['county_name'], scatter_df['state'],
                                           scatter_df['rucc_code'], scatter_df['uptake_pct'],
                                           scatter_df['total_churches'], scatter_df['ppp_churches'],
                                           scatter_df['rep_share'])],
            hoverinfo='text', name='Counties',
        ),
        row=2, col=2
    )
    
    fig3.update_yaxes(title_text='PPP Uptake (%)', row=1, col=1)
    fig3.update_yaxes(title_text='PPP Uptake (%)', row=1, col=2)
    fig3.update_yaxes(title_text='# Counties', row=2, col=1)
    fig3.update_yaxes(title_text='PPP Uptake (%)', row=2, col=2)
    fig3.update_xaxes(title_text='GOP Vote Share 2020 (%)', row=2, col=2)
    
    fig3.update_layout(
        height=850,
        title='PPP Church Uptake Rate: Rural-Urban & Political Patterns',
        showlegend=True,
    )
    fig3.write_html(OUT_DIR / 'ppp_uptake_rucc_politics.html')
    print('  -> outputs/ppp_uptake_rucc_politics.html')
    
    # ──────────────────────────────────────────────
    # FINAL SUMMARY
    # ──────────────────────────────────────────────
    urban = df[df['urban_rural'] == 'Urban']
    rural = df[df['urban_rural'] == 'Rural']
    
    print('\n' + '='*65)
    print('PPP UPTAKE RATE: KEY FINDINGS')
    print('='*65)
    print(f'\nOverall: {total_ppp/total_churches*100:.1f}% of US churches got PPP loans')
    print(f'\nUrban counties: {urban["uptake_pct"].mean():.1f}% avg uptake')
    print(f'  ({urban["ppp_churches"].sum():,}/{urban["total_churches"].sum():,} churches)')
    print(f'\nRural counties: {rural["uptake_pct"].mean():.1f}% avg uptake')
    print(f'  ({rural["ppp_churches"].sum():,}/{rural["total_churches"].sum():,} churches)')
    
    if rural['uptake_pct'].mean() > urban['uptake_pct'].mean():
        print('\n** Rural churches were MORE likely to need PPP than urban churches **')
    else:
        print('\n** Urban churches were MORE likely to need PPP than rural churches **')
    
    db.close()
    print(f'\nOutputs: {OUT_DIR}')
    print('Done.')

if __name__ == '__main__':
    main()
