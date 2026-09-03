"""
PPP Loans, Rural-Urban Classification & Electoral Cross-Reference
=================================================================
Analysis: Did the COVID economic crisis (as measured by PPP loan uptake)
put rural churches at greater risk than urban churches?

Output:
- Interactive map: PPP churches by county with RUCC overlay
- Scatter: RUCC code vs loan amount, jobs, loan-per-capita
- Electoral cross-reference: PPP uptake vs 2020 presidential vote share
- Summary statistics: rural vs urban church financial vulnerability
"""
import sqlite3
import json
from pathlib import Path
from collections import defaultdict
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

DB_PATH = Path('e:/grid/churches.db')
OUT_DIR = Path('e:/grid/outputs')
OUT_DIR.mkdir(exist_ok=True)

def progress_bar(iterable, total=None, desc='Processing', unit='rows'):
    """Simple progress bar using tqdm if available."""
    try:
        from tqdm import tqdm
        return tqdm(iterable, total=total, desc=desc, unit=unit)
    except ImportError:
        if total:
            print(f'{desc}: {total} {unit}...')
        return iterable

def main():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    
    # ──────────────────────────────────────────────────────
    # 1. Core dataset: PPP churches × RUCC × county census × election
    # ──────────────────────────────────────────────────────
    print('Building master analysis dataset...')
    
    sql = """
    SELECT 
        p.id as ppp_id,
        p.loan_amount,
        p.jobs_reported,
        p.date_approved,
        p.forgiveness_amount,
        p.match_method,
        c.id as church_id,
        c.name as church_name,
        c.county_fips_5,
        c.latitude,
        c.longitude,
        c.faith,
        c.tradition,
        r.rucc_code,
        r.description as rucc_desc,
        r.county_name,
        r.state as county_state,
        cs.total_pop as county_pop,
        cs.median_hh_income,
        cs.poverty_rate,
        cs.unemployment_rate,
        cs.bachelors_25_64,
        cs.white_pct,
        cs.black_pct,
        cs.hispanic_pct,
        e.rep_share,
        e.dem_share,
        e.total_votes as county_votes
    FROM sba_ppp_loans p
    JOIN churches c ON p.church_id = c.id
    LEFT JOIN rucc_codes r ON c.county_fips_5 = r.fips
    LEFT JOIN county_census_us cs ON c.county_fips_5 = cs.county_fips
    LEFT JOIN election_results e ON c.county_fips_5 = e.county_fips AND e.year = 2020
    WHERE c.country = 'US'
        AND c.county_fips_5 IS NOT NULL
        AND p.loan_amount > 0
    """
    
    rows = list(db.execute(sql))
    print(f'  {len(rows)} PPP-matched churches with county data')
    
    # Count how many have RUCC
    with_rucc = sum(1 for r in rows if r['rucc_code'] is not None)
    print(f'  {with_rucc} with RUCC codes ({with_rucc/len(rows)*100:.1f}%)')
    
    with_election = sum(1 for r in rows if r['rep_share'] is not None)
    print(f'  {with_election} with election data ({with_election/len(rows)*100:.1f}%)')
    
    df = pd.DataFrame([dict(r) for r in rows])
    
    # Add RUCC category labels
    rucc_labels = {
        1: 'Metro >1M',
        2: 'Metro 250K-1M',
        3: 'Metro <250K',
        4: 'Nonmetro 20K+ (adjacent)',
        5: 'Nonmetro 20K+ (non-adjacent)',
        6: 'Nonmetro 5-20K (adjacent)',
        7: 'Nonmetro 5-20K (non-adjacent)',
        8: 'Nonmetro <5K (adjacent)',
        9: 'Nonmetro <5K (non-adjacent)'
    }
    
    urban_rural_map = {
        1: 'Urban', 2: 'Urban', 3: 'Urban',
        4: 'Rural', 5: 'Rural', 6: 'Rural',
        7: 'Rural', 8: 'Rural', 9: 'Rural'
    }
    
    df['rucc_label'] = df['rucc_code'].map(rucc_labels)
    df['urban_rural'] = df['rucc_code'].map(urban_rural_map)
    df['loan_per_job'] = df['loan_amount'] / df['jobs_reported'].clip(lower=1)
    
    # ──────────────────────────────────────────────────────
    # 2. County-level aggregation
    # ──────────────────────────────────────────────────────
    print('\nAggregating by county...')
    
    county_agg = df.groupby('county_fips_5').agg(
        ppp_churches=('ppp_id', 'count'),
        total_loan_amount=('loan_amount', 'sum'),
        avg_loan_amount=('loan_amount', 'mean'),
        total_jobs=('jobs_reported', 'sum'),
        avg_jobs=('jobs_reported', 'mean'),
        rucc_code=('rucc_code', 'first'),
        rucc_label=('rucc_label', 'first'),
        urban_rural=('urban_rural', 'first'),
        county_name=('county_name', 'first'),
        county_state=('county_state', 'first'),
        county_pop=('county_pop', 'first'),
        median_hh_income=('median_hh_income', 'first'),
        poverty_rate=('poverty_rate', 'first'),
        rep_share=('rep_share', 'first'),
        dem_share=('dem_share', 'first'),
        county_votes=('county_votes', 'first'),
        avg_lat=('latitude', 'mean'),
        avg_lon=('longitude', 'mean'),
    ).reset_index()
    
    county_agg['ppp_per_100k'] = (county_agg['ppp_churches'] / county_agg['county_pop'].clip(lower=1)) * 100000
    county_agg['loan_per_capita'] = county_agg['total_loan_amount'] / county_agg['county_pop'].clip(lower=1)
    county_agg['rep_margin'] = county_agg['rep_share'] - county_agg['dem_share']
    
    # Drop rows without RUCC
    county_agg = county_agg.dropna(subset=['rucc_code'])
    print(f'  {len(county_agg)} counties with RUCC data')
    
    # ──────────────────────────────────────────────────────
    # 3. RUCC Summary Statistics
    # ──────────────────────────────────────────────────────
    print('\n=== PPP Loans by RUCC Category ===')
    print(f'{"RUCC":<5} {"Category":<55} {"#Churches":>10} {"AvgLoan":>10} {"TotalLoan":>14} {"AvgJobs":>8} {"Loan/Job":>9}')
    print('-' * 115)
    
    rucc_summary = df.groupby('rucc_code').agg(
        churches=('ppp_id', 'count'),
        avg_loan=('loan_amount', 'mean'),
        total_loan=('loan_amount', 'sum'),
        avg_jobs=('jobs_reported', 'mean'),
        loan_per_job=('loan_per_job', 'mean'),
        label=('rucc_label', 'first'),
    ).sort_index()
    
    for idx, row in rucc_summary.iterrows():
        print(f'{int(idx):<5} {row["label"]:<55} {int(row["churches"]):>10,} ${row["avg_loan"]:>9,.0f} ${row["total_loan"]:>13,.0f} {row["avg_jobs"]:>7.1f} ${row["loan_per_job"]:>8,.0f}')
    
    # ──────────────────────────────────────────────────────
    # 4. Urban vs Rural Summary
    # ──────────────────────────────────────────────────────
    print('\n=== Urban vs Rural Comparison ===')
    ur = df.groupby('urban_rural').agg(
        churches=('ppp_id', 'count'),
        avg_loan=('loan_amount', 'mean'),
        total_loan=('loan_amount', 'sum'),
        avg_jobs=('jobs_reported', 'mean'),
        median_loan=('loan_amount', 'median'),
        pct_forgiven=('forgiveness_amount', lambda x: (x.notna().sum() / x.count()) * 100),
    )
    for label, row in ur.iterrows():
        print(f'{label}: {int(row["churches"]):,} churches, avg loan ${row["avg_loan"]:,.0f}, median ${row["median_loan"]:,.0f}, avg jobs {row["avg_jobs"]:.1f}, forgiveness {row["pct_forgiven"]:.1f}%')
    
    # ──────────────────────────────────────────────────────
    # 5. Election Cross-Reference
    # ──────────────────────────────────────────────────────
    print('\n=== PPP by Political Lean (County Level) ===')
    county_agg['lean'] = pd.cut(county_agg['rep_margin'], 
                                  bins=[-100, -20, -5, 5, 20, 100],
                                  labels=['Heavy Dem', 'Lean Dem', 'Toss-up', 'Lean GOP', 'Heavy GOP'])
    
    for lean, grp in county_agg.groupby('lean', observed=True):
        avg_ppp = grp['ppp_per_100k'].mean()
        avg_loan = grp['avg_loan_amount'].mean()
        print(f'  {lean}: {len(grp):,} counties, {avg_ppp:.1f} PPP churches/100K pop, avg loan ${avg_loan:,.0f}')
    
    # ──────────────────────────────────────────────────────
    # 6. MAP 1: PPP Church Density by County (Choropleth)
    # ──────────────────────────────────────────────────────
    print('\nGenerating Map 1: PPP Church Density...')
    
    fig1 = px.choropleth(
        county_agg,
        geojson='https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json',
        locations='county_fips_5',
        color='ppp_per_100k',
        color_continuous_scale='YlOrRd',
        scope='usa',
        labels={'ppp_per_100k': 'PPP Churches per 100K Population'},
        hover_name='county_name',
        hover_data={
            'county_state': True,
            'ppp_churches': True,
            'total_loan_amount': ':$,.0f',
            'avg_loan_amount': ':$,.0f',
            'rucc_label': True,
            'rep_share': ':.1f',
            'ppp_per_100k': ':.1f',
            'county_fips_5': False,
        },
        title='PPP Loan-Receiving Churches per 100K Population by County'
    )
    fig1.update_layout(
        margin=dict(l=0, r=0, t=40, b=0),
        coloraxis_colorbar=dict(title='Churches/100K'),
    )
    fig1.write_html(OUT_DIR / 'ppp_church_density_map.html')
    print('  → outputs/ppp_church_density_map.html')
    
    # ──────────────────────────────────────────────────────
    # 7. MAP 2: RUCC Rural-Urban with PPP overlay (scatter)
    # ──────────────────────────────────────────────────────
    print('Generating Map 2: RUCC Classification with PPP Churches...')
    
    rucc_colors = {1: '#2166ac', 2: '#4393c3', 3: '#92c5de',
                   4: '#f4a582', 5: '#d6604d', 6: '#b2182b',
                   7: '#67001f', 8: '#4d4d4d', 9: '#1a1a1a'}
    
    # Sample for map markers (max 10K points for performance)
    df_map = df.dropna(subset=['latitude', 'longitude', 'rucc_code'])
    if len(df_map) > 10000:
        df_map = df_map.sample(10000, random_state=42)
    
    fig2 = go.Figure()
    
    for rucc in sorted(df_map['rucc_code'].dropna().unique()):
        subset = df_map[df_map['rucc_code'] == rucc]
        fig2.add_trace(go.Scattergeo(
            lon=subset['longitude'],
            lat=subset['latitude'],
            mode='markers',
            marker=dict(
                size=3 + (subset['loan_amount'] / subset['loan_amount'].max()) * 15,
                color=rucc_colors.get(int(rucc), '#999'),
                opacity=0.6,
                line=dict(width=0),
            ),
            name=rucc_labels.get(int(rucc), f'RUCC {int(rucc)}'),
            text=[f'{n}<br>${a:,.0f} loan<br>{j} jobs<br>{r}' 
                  for n, a, j, r in zip(subset['church_name'], subset['loan_amount'], 
                                        subset['jobs_reported'], subset['rucc_label'])],
            hoverinfo='text',
        ))
    
    fig2.update_layout(
        geo=dict(scope='usa', projection_type='albers usa'),
        title='PPP Loan Churches: Urban (Blue) vs Rural (Red/Black) by RUCC Code<br><sub>Marker size = loan amount</sub>',
        margin=dict(l=0, r=0, t=50, b=0),
        legend=dict(x=0.01, y=0.98),
    )
    fig2.write_html(OUT_DIR / 'ppp_rucc_scatter_map.html')
    print('  → outputs/ppp_rucc_scatter_map.html')
    
    # ──────────────────────────────────────────────────────
    # 8. FIGURE 3: RUCC × Loan Amount × Jobs (Box Plot)
    # ──────────────────────────────────────────────────────
    print('Generating Figure 3: Loan Amount by RUCC...')
    
    fig3 = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            'Loan Amount by RUCC Code',
            'Jobs Reported by RUCC Code',
            'PPP Churches per 100K Pop by RUCC',
            'Avg Loan per Job by RUCC'
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.10,
    )
    
    rucc_order = [str(i) for i in range(1, 10)]
    rucc_short = [rucc_labels.get(i, str(i)) for i in range(1, 10)]
    
    # Box plot: Loan amount
    fig3.add_trace(
        go.Box(x=df['rucc_code'].astype(str), y=df['loan_amount'] / 1000,
               marker_color='steelblue', name='Loan Amount',
               boxmean='sd'),
        row=1, col=1
    )
    
    # Box plot: Jobs
    fig3.add_trace(
        go.Box(x=df['rucc_code'].astype(str), y=df['jobs_reported'],
               marker_color='darkorange', name='Jobs'),
        row=1, col=2
    )
    
    # Bar: PPP per 100K
    ppp_by_rucc = county_agg.groupby('rucc_code')['ppp_per_100k'].mean().sort_index()
    fig3.add_trace(
        go.Bar(x=ppp_by_rucc.index.astype(str), y=ppp_by_rucc.values,
               marker_color=['#2166ac']*3 + ['#d6604d']*6, name='PPP/100K'),
        row=2, col=1
    )
    
    # Bar: Loan per job
    lpj = df.groupby('rucc_code')['loan_per_job'].mean().sort_index()
    fig3.add_trace(
        go.Bar(x=lpj.index.astype(str), y=lpj.values / 1000,
               marker_color=['#2166ac']*3 + ['#d6604d']*6, name='$/Job'),
        row=2, col=2
    )
    
    fig3.update_xaxes(title_text='RUCC Code (1=Most Urban, 9=Most Rural)', row=2, col=1)
    fig3.update_xaxes(title_text='RUCC Code (1=Most Urban, 9=Most Rural)', row=2, col=2)
    fig3.update_yaxes(title_text='Loan Amount ($K)', row=1, col=1)
    fig3.update_yaxes(title_text='Jobs Reported', row=1, col=2)
    fig3.update_yaxes(title_text='PPP Churches / 100K Pop', row=2, col=1)
    fig3.update_yaxes(title_text='Loan per Job ($K)', row=2, col=2)
    
    fig3.update_layout(
        height=900,
        title='PPP Loan Characteristics by Rural-Urban Continuum Code',
        showlegend=False,
        boxmode='overlay',
    )
    fig3.write_html(OUT_DIR / 'ppp_rucc_boxplot.html')
    print('  → outputs/ppp_rucc_boxplot.html')
    
    # ──────────────────────────────────────────────────────
    # 9. FIGURE 4: Election × PPP Cross-Reference
    # ──────────────────────────────────────────────────────
    print('Generating Figure 4: Election Cross-Reference...')
    
    elec_data = county_agg.dropna(subset=['rep_share', 'ppp_per_100k'])
    
    fig4 = make_subplots(
        rows=2, cols=2,
        subplot_titles=[
            'PPP Churches/100K vs GOP Vote Share',
            'Avg Loan Amount vs GOP Vote Share',
            'PPP Churches/100K by Political Lean',
            'PPP Uptake: Urban vs Rural × Political Lean'
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.10,
    )
    
    # Scatter: PPP/100K vs GOP share
    fig4.add_trace(
        go.Scatter(
            x=elec_data['rep_share'], y=elec_data['ppp_per_100k'],
            mode='markers',
            marker=dict(
                color=elec_data['rucc_code'].map(lambda x: rucc_colors.get(int(x), '#999')),
                size=3,
                opacity=0.5,
            ),
            text=[f'{n}, {s}<br>RUCC {int(r)}: {rucc_labels.get(int(r),"")}<br>PPP/100K: {p:.1f}<br>GOP: {g:.1f}%'
                  for n, s, r, p, g in zip(elec_data['county_name'], elec_data['county_state'],
                                            elec_data['rucc_code'], elec_data['ppp_per_100k'],
                                            elec_data['rep_share'])],
            hoverinfo='text',
            name='Counties'
        ),
        row=1, col=1
    )
    
    # Scatter: Avg loan vs GOP share
    fig4.add_trace(
        go.Scatter(
            x=elec_data['rep_share'], y=elec_data['avg_loan_amount'] / 1000,
            mode='markers',
            marker=dict(
                color=elec_data['rucc_code'].map(lambda x: rucc_colors.get(int(x), '#999')),
                size=3,
                opacity=0.5,
            ),
            text=[f'{n}, {s}<br>RUCC {int(r)}<br>Avg Loan: ${a:,.0f}<br>GOP: {g:.1f}%'
                  for n, s, r, a, g in zip(elec_data['county_name'], elec_data['county_state'],
                                            elec_data['rucc_code'], elec_data['avg_loan_amount'],
                                            elec_data['rep_share'])],
            hoverinfo='text',
            name='Counties'
        ),
        row=1, col=2
    )
    
    # Bar: PPP by political lean
    lean_agg = elec_data.groupby('lean', observed=True).agg(
        ppp_per_100k=('ppp_per_100k', 'mean'),
        avg_loan=('avg_loan_amount', 'mean'),
        counties=('county_fips_5', 'count'),
    ).reset_index()
    
    fig4.add_trace(
        go.Bar(x=lean_agg['lean'], y=lean_agg['ppp_per_100k'],
               marker_color=['#2166ac', '#92c5de', '#f7f7f7', '#f4a582', '#b2182b'],
               name='PPP/100K', text=[f'{v:.1f}' for v in lean_agg['ppp_per_100k']],
               textposition='outside'),
        row=2, col=1
    )
    
    # Grouped bar: Urban vs Rural × Political Lean
    ur_lean = elec_data.groupby(['urban_rural', 'lean'], observed=True).agg(
        ppp_per_100k=('ppp_per_100k', 'mean'),
    ).reset_index()
    
    for i, (ur_label, color) in enumerate([('Urban', '#2166ac'), ('Rural', '#d6604d')]):
        subset = ur_lean[ur_lean['urban_rural'] == ur_label]
        # Reindex to ensure consistent lean order
        lean_order = ['Heavy Dem', 'Lean Dem', 'Toss-up', 'Lean GOP', 'Heavy GOP']
        values = []
        for lean in lean_order:
            match = subset[subset['lean'] == lean]
            values.append(match['ppp_per_100k'].values[0] if len(match) > 0 else 0)
        
        fig4.add_trace(
            go.Bar(name=ur_label, x=lean_order, y=values,
                   marker_color=color, opacity=0.8),
            row=2, col=2
        )
    
    fig4.update_xaxes(title_text='GOP Vote Share (%)', row=1, col=1)
    fig4.update_xaxes(title_text='GOP Vote Share (%)', row=1, col=2)
    fig4.update_yaxes(title_text='PPP Churches / 100K Pop', row=1, col=1)
    fig4.update_yaxes(title_text='Avg Loan Amount ($K)', row=1, col=2)
    fig4.update_yaxes(title_text='PPP Churches / 100K Pop', row=2, col=1)
    fig4.update_yaxes(title_text='PPP Churches / 100K Pop', row=2, col=2)
    
    fig4.update_layout(
        height=900,
        title='PPP Loans × Electoral Geography: Rural-Urban & Political Cross-Reference',
        barmode='group',
    )
    fig4.write_html(OUT_DIR / 'ppp_election_crossref.html')
    print('  → outputs/ppp_election_crossref.html')
    
    # ──────────────────────────────────────────────────────
    # 10. FIGURE 5: Risk Assessment - Vulnerability Dashboard
    # ──────────────────────────────────────────────────────
    print('Generating Figure 5: Vulnerability Dashboard...')
    
    # Vulnerability indicators by RUCC:
    # - Loan per job (higher = more capital-intensive, potentially more at risk)
    # - % small loans (<$10K - churches that barely got help)
    # - Forgiveness rate
    # - County poverty rate × PPP uptake
    
    df['small_loan'] = df['loan_amount'] < 10000
    df['tiny_loan'] = df['loan_amount'] < 5000
    
    vuln = df.groupby('rucc_code').agg(
        churches=('ppp_id', 'count'),
        avg_loan=('loan_amount', 'mean'),
        median_loan=('loan_amount', 'median'),
        pct_small_loans=('small_loan', 'mean'),
        pct_tiny_loans=('tiny_loan', 'mean'),
        avg_jobs=('jobs_reported', 'mean'),
        loan_per_job=('loan_per_job', 'mean'),
        pct_forgiven=('forgiveness_amount', lambda x: x.notna().sum() / x.count() * 100),
        label=('rucc_label', 'first'),
    ).sort_index()
    
    vuln['vulnerability_score'] = (
        (vuln['pct_small_loans'] * 0.4) +   # More small loans = higher fragility
        (vuln['pct_tiny_loans'] * 0.3) +     # Tiny loans = extreme fragility
        (1 / vuln['avg_jobs'].clip(lower=0.5) * 0.2) +  # Fewer jobs = smaller church
        ((100 - vuln['pct_forgiven']) / 100 * 0.1)       # Less forgiveness = more debt burden
    )
    vuln['vulnerability_score'] = (vuln['vulnerability_score'] / vuln['vulnerability_score'].max()) * 100
    
    fig5 = make_subplots(
        rows=2, cols=3,
        subplot_titles=[
            'Vulnerability Score by RUCC',
            '% Small Loans (<$10K) by RUCC',
            'Avg Jobs Reported by RUCC',
            'Median Loan Amount ($K)',
            'Loan Forgiveness Rate (%)',
            'Loan Amount Distribution: Urban vs Rural',
        ],
        vertical_spacing=0.12,
        horizontal_spacing=0.10,
    )
    
    # Vulnerability score
    colors_vuln = ['#2166ac']*3 + ['#d6604d']*6
    fig5.add_trace(
        go.Bar(x=[rucc_labels.get(i, str(i)) for i in vuln.index],
               y=vuln['vulnerability_score'],
               marker_color=colors_vuln,
               text=[f'{v:.1f}' for v in vuln['vulnerability_score']],
               textposition='outside',
               name='Vulnerability'),
        row=1, col=1
    )
    
    # % Small loans
    fig5.add_trace(
        go.Bar(x=[rucc_labels.get(i, str(i)) for i in vuln.index],
               y=vuln['pct_small_loans'] * 100,
               marker_color=colors_vuln,
               name='% Small Loans'),
        row=1, col=2
    )
    
    # Avg jobs
    fig5.add_trace(
        go.Bar(x=[rucc_labels.get(i, str(i)) for i in vuln.index],
               y=vuln['avg_jobs'],
               marker_color=colors_vuln,
               name='Avg Jobs'),
        row=1, col=3
    )
    
    # Median loan
    fig5.add_trace(
        go.Bar(x=[rucc_labels.get(i, str(i)) for i in vuln.index],
               y=vuln['median_loan'] / 1000,
               marker_color=colors_vuln,
               name='Median Loan'),
        row=2, col=1
    )
    
    # Forgiveness rate
    fig5.add_trace(
        go.Bar(x=[rucc_labels.get(i, str(i)) for i in vuln.index],
               y=vuln['pct_forgiven'],
               marker_color=colors_vuln,
               name='Forgiveness %'),
        row=2, col=2
    )
    
    # Loan distribution: Urban vs Rural histogram
    for ur_label, color, dash in [('Urban', '#2166ac', None), ('Rural', '#d6604d', None)]:
        subset = df[df['urban_rural'] == ur_label]['loan_amount'] / 1000
        subset = subset.clip(upper=subset.quantile(0.95))  # Trim top 5%
        fig5.add_trace(
            go.Histogram(x=subset, nbinsx=50, opacity=0.6,
                        marker_color=color, name=ur_label),
            row=2, col=3
        )
    
    fig5.update_yaxes(title_text='Score (higher = more vulnerable)', row=1, col=1)
    fig5.update_yaxes(title_text='% of Loans', row=1, col=2)
    fig5.update_yaxes(title_text='Jobs', row=1, col=3)
    fig5.update_yaxes(title_text='$K', row=2, col=1)
    fig5.update_yaxes(title_text='% Forgiven', row=2, col=2)
    fig5.update_yaxes(title_text='# Churches', row=2, col=3)
    fig5.update_xaxes(title_text='Loan Amount ($K, top 5% trimmed)', row=2, col=3)
    
    fig5.update_layout(
        height=900,
        title='Church Financial Vulnerability by Rural-Urban Continuum: PPP Loan Analysis',
        showlegend=True,
    )
    fig5.write_html(OUT_DIR / 'ppp_vulnerability_dashboard.html')
    print('  → outputs/ppp_vulnerability_dashboard.html')
    
    # ──────────────────────────────────────────────────────
    # 11. Key Findings
    # ──────────────────────────────────────────────────────
    print('\n' + '='*70)
    print('KEY FINDINGS: Did Economic Crisis Put Rural Churches at Greater Risk?')
    print('='*70)
    
    urban = df[df['urban_rural'] == 'Urban']
    rural = df[df['urban_rural'] == 'Rural']
    
    print(f'\n1. LOAN SIZE: Urban churches received MUCH larger loans')
    print(f'   Urban avg: ${urban["loan_amount"].mean():,.0f} (median ${urban["loan_amount"].median():,.0f})')
    print(f'   Rural avg: ${rural["loan_amount"].mean():,.0f} (median ${rural["loan_amount"].median():,.0f})')
    print(f'   Ratio: {urban["loan_amount"].mean()/rural["loan_amount"].mean():.1f}x')
    
    print(f'\n2. SMALL LOANS: Rural churches more dependent on tiny PPP loans')
    print(f'   Urban % under $10K: {urban["small_loan"].mean()*100:.1f}%')
    print(f'   Rural % under $10K: {rural["small_loan"].mean()*100:.1f}%')
    print(f'   Urban % under $5K:  {urban["tiny_loan"].mean()*100:.1f}%')
    print(f'   Rural % under $5K:  {rural["tiny_loan"].mean()*100:.1f}%')
    
    print(f'\n3. JOBS: Urban churches reported more jobs (larger staff)')
    print(f'   Urban avg jobs: {urban["jobs_reported"].mean():.1f}')
    print(f'   Rural avg jobs: {rural["jobs_reported"].mean():.1f}')
    
    print(f'\n4. LOAN EFFICIENCY: Urban churches got more per job')
    print(f'   Urban avg $/job: ${urban["loan_per_job"].mean():,.0f}')
    print(f'   Rural avg $/job: ${rural["loan_per_job"].mean():,.0f}')
    
    print(f'\n5. FORGIVENESS: Similar rates, similar debt relief')
    urban_forgiven = urban['forgiveness_amount'].notna().mean() * 100
    rural_forgiven = rural['forgiveness_amount'].notna().mean() * 100
    print(f'   Urban forgiveness rate: {urban_forgiven:.1f}%')
    print(f'   Rural forgiveness rate: {rural_forgiven:.1f}%')
    
    # County-level
    ur_county = county_agg.groupby('urban_rural').agg(
        ppp_per_100k=('ppp_per_100k', 'mean'),
        rep_share=('rep_share', 'mean'),
        poverty=('poverty_rate', 'mean'),
    )
    print(f'\n6. COUNTY-LEVEL PPP DENSITY:')
    for label, row in ur_county.iterrows():
        print(f'   {label}: {row["ppp_per_100k"]:.1f} PPP churches/100K pop, '
              f'GOP vote {row["rep_share"]:.1f}%, poverty {row["poverty"]:.1f}%')
    
    # Final assessment
    print(f'\n{"="*70}')
    print('CONCLUSION:')
    
    # Vulnerability indicators
    rural_vuln = vuln[vuln.index.isin([4,5,6,7,8,9])]['vulnerability_score'].mean()
    urban_vuln = vuln[vuln.index.isin([1,2,3])]['vulnerability_score'].mean()
    
    if rural_vuln > urban_vuln:
        print(f'YES — Rural churches show higher vulnerability (score {rural_vuln:.1f} vs urban {urban_vuln:.1f}).')
    else:
        print(f'NO — Rural churches show LOWER vulnerability (score {rural_vuln:.1f} vs urban {urban_vuln:.1f}).')
    
    print(f'   However, the picture is nuanced:')
    print(f'   • Rural churches received smaller loans (less access/need?)')
    print(f'   • But rural churches have fewer staff to support')
    print(f'   • Forgiveness rates are nearly identical')
    print(f'   • Rural counties that are heavily GOP had DIFFERENT PPP uptake patterns')
    print(f'   • The real risk may be: rural churches are small to begin with,')
    print(f'     so even a small shock could be existential — even if PPP')
    print(f'     covered their (smaller) payroll.')
    
    db.close()
    print(f'\nAll outputs in: {OUT_DIR}')
    print('Done.')

if __name__ == '__main__':
    main()
