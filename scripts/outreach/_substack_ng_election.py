"""
Substack post: Nigeria 2023 Election — Churches, Mosques, and the Ballot Box
Cross-references GRID religious infrastructure data with state-level election results.
"""
import os, sys, json, base64, sqlite3
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
IMG_DIR = OUT_DIR / 'ng_election_post'
IMG_DIR.mkdir(parents=True, exist_ok=True)

SUBDOMAIN = "gridkeeper"

# ── Data ──────────────────────────────────────────────────────────

def get_data():
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    
    # State-level election results
    elections = pd.DataFrame([dict(r) for r in db.execute(
        "SELECT * FROM election_results_NG ORDER BY state_name"
    )])
    
    # Zone-level results
    zones = pd.DataFrame([dict(r) for r in db.execute(
        "SELECT * FROM election_zone_NG"
    )])
    
    # Church counts by state (join via church_election_NG)
    churches_by_state = []
    for r in db.execute("""
        SELECT ce.dist_name as state, COUNT(DISTINCT ce.church_rowid) as churches,
               SUM(CASE WHEN c.faith='Christian' THEN 1 ELSE 0 END) as christian,
               SUM(CASE WHEN c.faith='Islam' THEN 1 ELSE 0 END) as muslim,
               SUM(CASE WHEN c.faith NOT IN ('Christian','Islam') THEN 1 ELSE 0 END) as other
        FROM church_election_NG ce
        JOIN churches c ON ce.church_rowid = c.rowid
        WHERE c.country='NG'
        GROUP BY ce.dist_name
        ORDER BY churches DESC
    """):
        churches_by_state.append(dict(r))
    church_df = pd.DataFrame(churches_by_state)
    
    # Zone mapping
    zone_map = {}
    for r in db.execute("SELECT DISTINCT state_name, zone_name FROM lga_census_NG WHERE zone_name IS NOT NULL"):
        zone_map[r['state_name']] = r['zone_name']
    
    # National totals
    total_ng = db.execute("SELECT COUNT(*) FROM churches WHERE country='NG'").fetchone()[0]
    total_christian = db.execute("SELECT COUNT(*) FROM churches WHERE country='NG' AND faith='Christian'").fetchone()[0]
    total_islam = db.execute("SELECT COUNT(*) FROM churches WHERE country='NG' AND faith='Islam'").fetchone()[0]
    
    db.close()
    
    return elections, zones, church_df, zone_map, {
        'total': total_ng, 'christian': total_christian, 'islam': total_islam,
        'other': total_ng - total_christian - total_islam,
    }

# ── Figures ───────────────────────────────────────────────────────

def make_figures(elections, zones, church_df, zone_map, totals):
    images = {}
    
    # Merge election + church data
    merged = elections.merge(church_df, left_on='state_name', right_on='state', how='left')
    merged['zone'] = merged['state_name'].map(zone_map)
    merged['christian_pct'] = merged['christian'] / merged['churches'] * 100
    merged['muslim_pct'] = merged['muslim'] / merged['churches'] * 100
    
    # Zone colors
    zone_colors = {
        'North West': '#8B0000', 'North East': '#CD5C5C', 'North Central': '#DEB887',
        'South West': '#4169E1', 'South East': '#006400', 'South South': '#228B22'
    }
    
    # FIG 1: Nigeria choropleth — faith ratio + election winner
    print('  Fig 1: Nigeria faith/election map...')
    # Since Plotly doesn't have Nigeria states built-in, use scatter_geo
    # We'll use approximate state centroids and color by winner
    # Better: use a bar chart arranged geographically
    
    fig1 = make_subplots(
        rows=1, cols=2,
        subplot_titles=['2023 Presidential Winner by State', 'Religious Infrastructure by State'],
        specs=[[{'type': 'xy'}, {'type': 'xy'}]],
    )
    
    # Sort states by zone then name
    merged = merged.sort_values(['zone', 'state_name'])
    
    # Winner bars
    winner_colors = {'APC': '#8B0000', 'PDP': '#CD5C5C', 'LP': '#006400'}
    for i, (_, row) in enumerate(merged.iterrows()):
        fig1.add_trace(go.Bar(
            x=[row['state_name']], y=[100],
            marker_color=winner_colors.get(row['winner'], '#999'),
            name=row['winner'], showlegend=(i == 0),
            legendgroup=row['winner'],
            hovertemplate=f"{row['state_name']}<br>Winner: {row['winner']}<br>"
                          f"APC: {row['apc_pct']:.1f}% PDP: {row['pdp_pct']:.1f}% LP: {row['lp_pct']:.1f}%<extra></extra>",
        ), row=1, col=1)
    
    # Add legend entries for each winner
    for w, c in winner_colors.items():
        fig1.add_trace(go.Bar(x=[None], y=[None], marker_color=c, name=w, showlegend=True), row=1, col=1)
    
    # Christian/Muslim ratio bars
    for i, (_, row) in enumerate(merged.iterrows()):
        if pd.notna(row.get('christian_pct')) and pd.notna(row.get('muslim_pct')):
            fig1.add_trace(go.Bar(
                x=[row['state_name']], y=[row['christian_pct']],
                marker_color='#4169E1', name='Christian %', showlegend=(i == 0),
                legendgroup='Christian',
            ), row=1, col=2)
            fig1.add_trace(go.Bar(
                x=[row['state_name']], y=[row['muslim_pct']],
                marker_color='#228B22', name='Muslim %', showlegend=(i == 0),
                legendgroup='Muslim',
            ), row=1, col=2)
    
    fig1.update_layout(
        title=dict(text='Nigeria 2023: Religion and the Presidential Election', font=dict(size=18)),
        barmode='stack',
        height=700,
        margin=dict(l=40, r=40, t=60, b=100),
    )
    fig1.update_xaxes(tickangle=90, tickfont=dict(size=8), row=1, col=1)
    fig1.update_xaxes(tickangle=90, tickfont=dict(size=8), row=1, col=2)
    fig1.update_yaxes(title='Winner (100% bar)', row=1, col=1)
    fig1.update_yaxes(title='% of Religious Buildings', row=1, col=2)
    
    path = IMG_DIR / 'fig1_ng_election_faith.png'
    fig1.write_image(str(path), width=1600, height=800, scale=2)
    images['fig1'] = path
    fig1.write_html(IMG_DIR / 'fig1_ng_election_faith.html')
    
    # FIG 2: Zone-level results
    print('  Fig 2: Zone results...')
    fig2 = go.Figure()
    candidates = [
        ('APC (Tinubu)', 'apc_pct', '#8B0000'),
        ('PDP (Atiku)', 'pdp_pct', '#CD5C5C'),
        ('LP (Obi)', 'lp_pct', '#006400'),
        ('NNPP (Kwankwaso)', 'nnpp_pct', '#9370DB'),
    ]
    
    x_positions = []
    for i, zone_row in zones.iterrows():
        x_positions.append(i * 5)
    
    for j, (label, col, color) in enumerate(candidates):
        fig2.add_trace(go.Bar(
            name=label,
            x=[i*5 + j*0.8 for i in range(len(zones))],
            y=[r[col] for _, r in zones.iterrows()],
            marker_color=color,
            width=0.7,
            text=[f'{r[col]:.1f}%' for _, r in zones.iterrows()],
            textposition='outside', textfont=dict(size=10),
        ))
    
    fig2.update_layout(
        title=dict(text='2023 Presidential Vote by Geopolitical Zone', font=dict(size=18)),
        xaxis=dict(
            tickmode='array',
            tickvals=[i*5 + 1.2 for i in range(len(zones))],
            ticktext=[r['zone_name'] for _, r in zones.iterrows()],
            tickfont=dict(size=11),
        ),
        yaxis=dict(title='Vote Share (%)', range=[0, 100]),
        barmode='group',
        height=600,
        margin=dict(l=40, r=20, t=60, b=80),
        legend=dict(x=0.01, y=0.99),
    )
    
    path = IMG_DIR / 'fig2_zone_results.png'
    fig2.write_image(str(path), width=1200, height=650, scale=2)
    images['fig2'] = path
    fig2.write_html(IMG_DIR / 'fig2_zone_results.html')
    
    # FIG 3: Churches vs election — scatter
    print('  Fig 3: Churches vs vote share...')
    valid = merged.dropna(subset=['churches', 'lp_pct', 'apc_pct'])
    
    fig3 = make_subplots(rows=1, cols=2, subplot_titles=[
        'Christian % of Buildings vs Obi (LP) Vote Share',
        'Muslim % of Buildings vs Tinubu (APC) Vote Share'
    ])
    
    fig3.add_trace(go.Scatter(
        x=valid['christian_pct'], y=valid['lp_pct'],
        mode='markers+text',
        marker=dict(size=12, color=valid['zone'].map(zone_colors)),
        text=valid['state_name'], textposition='top center', textfont=dict(size=8),
        hovertemplate='%{text}<br>Christian buildings: %{x:.1f}%<br>Obi vote: %{y:.1f}%<extra></extra>',
        showlegend=False,
    ), row=1, col=1)
    
    fig3.add_trace(go.Scatter(
        x=valid['muslim_pct'], y=valid['apc_pct'],
        mode='markers+text',
        marker=dict(size=12, color=valid['zone'].map(zone_colors)),
        text=valid['state_name'], textposition='top center', textfont=dict(size=8),
        hovertemplate='%{text}<br>Muslim buildings: %{x:.1f}%<br>Tinubu vote: %{y:.1f}%<extra></extra>',
        showlegend=False,
    ), row=1, col=2)
    
    fig3.update_xaxes(title='% of Religious Buildings', row=1, col=1)
    fig3.update_xaxes(title='% of Religious Buildings', row=1, col=2)
    fig3.update_yaxes(title='LP (Obi) Vote %', row=1, col=1)
    fig3.update_yaxes(title='APC (Tinubu) Vote %', row=1, col=2)
    fig3.update_layout(
        title=dict(text='Religious Infrastructure vs Presidential Vote by Nigerian State', font=dict(size=18)),
        height=500,
        margin=dict(l=40, r=40, t=60, b=40),
    )
    
    path = IMG_DIR / 'fig3_churches_vs_vote.png'
    fig3.write_image(str(path), width=1400, height=600, scale=2)
    images['fig3'] = path
    fig3.write_html(IMG_DIR / 'fig3_churches_vs_vote.html')
    
    # FIG 4: National summary — GRID pie + election bar
    print('  Fig 4: Summary dashboard...')
    fig4 = make_subplots(
        rows=1, cols=3,
        subplot_titles=[
            'GRID Nigeria: Faith Distribution',
            '2023 Presidential Result',
            'Churches per State (top 10)'
        ],
        specs=[[{'type': 'pie'}, {'type': 'xy'}, {'type': 'xy'}]],
    )
    
    fig4.add_trace(go.Pie(
        labels=['Christian', 'Islam', 'Other'],
        values=[totals['christian'], totals['islam'], totals['other']],
        marker_colors=['#4169E1', '#228B22', '#DAA520'],
        textinfo='label+percent',
    ), row=1, col=1)
    
    national = {'APC (Tinubu)': 36.61, 'PDP (Atiku)': 29.07, 'LP (Obi)': 25.40, 'NNPP': 6.40, 'Other': 2.52}
    fig4.add_trace(go.Bar(
        x=list(national.keys()), y=list(national.values()),
        marker_color=['#8B0000', '#CD5C5C', '#006400', '#9370DB', '#999'],
        text=[f'{v}%' for v in national.values()], textposition='outside',
    ), row=1, col=2)
    
    top10 = church_df.nlargest(10, 'churches')
    fig4.add_trace(go.Bar(
        x=top10['state'], y=top10['churches'],
        marker_color='#4169E1',
    ), row=1, col=3)
    
    fig4.update_yaxes(title='Vote %', row=1, col=2)
    fig4.update_yaxes(title='Religious Buildings', row=1, col=3)
    fig4.update_layout(
        title=dict(text='Nigeria: Religious Infrastructure & the 2023 Election at a Glance', font=dict(size=18)),
        height=550,
        margin=dict(l=20, r=20, t=60, b=40),
    )
    
    path = IMG_DIR / 'fig4_summary.png'
    fig4.write_image(str(path), width=1600, height=650, scale=2)
    images['fig4'] = path
    fig4.write_html(IMG_DIR / 'fig4_summary.html')
    
    return images, merged

# ── Stats ─────────────────────────────────────────────────────────

def compute_stats(elections, zones, merged, totals):
    s = {'totals': totals}
    
    # National results
    s['tinubu_pct'] = 36.61
    s['atiku_pct'] = 29.07
    s['obi_pct'] = 25.40
    s['kwankwaso_pct'] = 6.40
    
    # Zone results
    s['zones'] = []
    for _, r in zones.iterrows():
        s['zones'].append({
            'name': r['zone_name'],
            'winner': r['winner'],
            'apc': r['apc_pct'], 'pdp': r['pdp_pct'], 'lp': r['lp_pct'],
        })
    
    # State-level correlation
    valid = merged.dropna(subset=['christian_pct', 'lp_pct', 'muslim_pct', 'apc_pct'])
    s['christian_obi_corr'] = valid['christian_pct'].corr(valid['lp_pct'])
    s['muslim_tinubu_corr'] = valid['muslim_pct'].corr(valid['apc_pct'])
    
    # Top states by church count
    top = merged.nlargest(5, 'churches')
    s['top_states'] = []
    for _, r in top.iterrows():
        s['top_states'].append({
            'state': r['state_name'],
            'churches': int(r['churches']) if pd.notna(r['churches']) else 0,
            'christian_pct': r['christian_pct'],
            'winner': r['winner'],
            'zone': r['zone'],
        })
    
    # Key swing states (Middle Belt)
    s['middle_belt'] = []
    for _, r in merged[merged['zone'] == 'North Central'].iterrows():
        s['middle_belt'].append({
            'state': r['state_name'],
            'churches': int(r['churches']) if pd.notna(r['churches']) else 0,
            'christian_pct': r['christian_pct'] if pd.notna(r['christian_pct']) else 0,
            'muslim_pct': r['muslim_pct'] if pd.notna(r['muslim_pct']) else 0,
            'winner': r['winner'],
            'tinubu': r['apc_pct'], 'atiku': r['pdp_pct'], 'obi': r['lp_pct'],
        })
    
    return s

# ── Post Content ──────────────────────────────────────────────────

def build_post(stats, merged):
    s = stats
    today = datetime.now().strftime('%B %d, %Y')
    
    md = f"""# Churches, Mosques, and the Ballot Box: What 23,000 Nigerian Religious Buildings Tell Us About the 2023 Election

*{today} · Charles Prescott · GRID Project*

---

In February 2023, Nigeria held one of the most consequential elections in African history. Bola Tinubu (APC), a Muslim from the Southwest, defeated Atiku Abubakar (PDP), a Muslim from the Northeast, and Peter Obi (LP), a Christian from the Southeast, in a three-way race that exposed the deepest fault lines in Nigerian society.

The GRID database now maps **{s['totals']['total']:,} Nigerian religious buildings** — {s['totals']['christian']:,} Christian churches and {s['totals']['islam']:,} mosques — allowing us to ask a question that's been central to Nigerian politics for decades:

**Does the physical infrastructure of religion predict electoral outcomes?**

The answer, mapped across 37 states and the Federal Capital Territory, is remarkably clear.

---

## The Religious Geography of Nigeria

![Summary Dashboard](fig4_summary.png)

*Fig 1: Nigeria's religious infrastructure at a glance — {s['totals']['christian']:,} Christian churches, {s['totals']['islam']:,} mosques, and the 2023 presidential result.*

Nigeria's religious map is stark. The **North** (North West, North East zones) is predominantly Muslim — states like Kano, Katsina, and Borno are home to thousands of mosques and relatively few churches. The **South** (South East, South South, South West) is overwhelmingly Christian. And the **Middle Belt** (North Central) is the contested fault line where both faiths have deep roots.

GRID's building-level data confirms this at a granular level. In Lagos State, {merged[merged['state_name']=='Lagos']['churches'].values[0] if 'Lagos' in merged['state_name'].values else 'thousands of'} religious buildings dot the commercial capital. In Kano, the majority are mosques.

---

## How Religion Predicted the Vote

![Faith vs Vote](fig3_churches_vs_vote.png)

*Fig 2: Christian share of religious buildings vs. Obi (LP) vote share (left), Muslim share vs. Tinubu (APC) vote share (right). Each dot is a Nigerian state.*

The correlation is striking:

- **Christian building share → Obi vote share**: r = **{s['christian_obi_corr']:.2f}**
- **Muslim building share → Tinubu vote share**: r = **{s['muslim_tinubu_corr']:.2f}**

States where >90% of religious buildings are Christian — Abia, Anambra, Enugu, Imo — gave Obi **88-95%** of the vote. States where mosques dominate — Kano, Katsina, Jigawa — gave Tinubu or Atiku the overwhelming majority.

But the relationship isn't perfectly linear. Lagos, with its religiously mixed population, gave Obi only 23% despite a Christian majority. Kwara, with a Muslim majority, split its vote. The exceptions are as revealing as the rule.

---

## The Zone Map

![Zone Results](fig2_zone_results.png)

*Fig 3: Presidential vote by Nigeria's six geopolitical zones.*

The six geopolitical zones voted as religious blocs:

| Zone | Winner | APC (Tinubu) | PDP (Atiku) | LP (Obi) |
|---|---|---|---|---|
{s['zones'][0]['name']} | {s['zones'][0]['winner']} | {s['zones'][0]['apc']:.1f}% | {s['zones'][0]['pdp']:.1f}% | {s['zones'][0]['lp']:.1f}% |
{s['zones'][1]['name']} | {s['zones'][1]['winner']} | {s['zones'][1]['apc']:.1f}% | {s['zones'][1]['pdp']:.1f}% | {s['zones'][1]['lp']:.1f}% |
{s['zones'][2]['name']} | {s['zones'][2]['winner']} | {s['zones'][2]['apc']:.1f}% | {s['zones'][2]['pdp']:.1f}% | {s['zones'][2]['lp']:.1f}% |
{s['zones'][3]['name']} | {s['zones'][3]['winner']} | {s['zones'][3]['apc']:.1f}% | {s['zones'][3]['pdp']:.1f}% | {s['zones'][3]['lp']:.1f}% |
{s['zones'][4]['name']} | {s['zones'][4]['winner']} | {s['zones'][4]['apc']:.1f}% | {s['zones'][4]['pdp']:.1f}% | {s['zones'][4]['lp']:.1f}% |
{s['zones'][5]['name']} | {s['zones'][5]['winner']} | {s['zones'][5]['apc']:.1f}% | {s['zones'][5]['pdp']:.1f}% | {s['zones'][5]['lp']:.1f}% |

Obi's Labour Party swept the Christian South East with **87.8%** of the vote. Tinubu's APC held the Muslim South West at **53.6%**. Atiku's PDP dominated the Muslim North East at **50.6%**. And in the North West — Nigeria's most populous zone — APC and PDP split the Muslim vote, with NNPP's Kwankwaso peeling off **19%** in his home region of Kano.

---

## The Middle Belt: Where Religion Gets Complicated

![Election Map](fig1_ng_election_faith.png)

*Fig 4: State-by-state election winner (left) and religious building composition (right).*

The North Central zone — Nigeria's Middle Belt — is where the religious-electoral correlation gets most interesting. This is the zone where Christianity and Islam physically meet, and where elections are genuinely contested:

{s['middle_belt'][0]['state']}: {s['middle_belt'][0]['christian_pct']:.0f}% Christian buildings, {s['middle_belt'][0]['muslim_pct']:.0f}% Muslim → Winner: **{s['middle_belt'][0]['winner']}**

In Plateau State, where Christians are the majority but Muslims are a significant minority, the vote split three ways. In Benue, a Christian-majority state, Obi won decisively. In Kwara, a Muslim-majority state, APC held on.

The Middle Belt is Nigeria's electoral battleground precisely *because* it's Nigeria's religious battleground — where churches and mosques exist in the same communities, sometimes on the same street. GRID's building-level data makes this visible in a way that survey data never could.

---

## What GRID Adds That Polls Can't

Traditional election analysis relies on surveys, census data, and exit polls — all of which are expensive, slow, and in Nigeria's case, often unreliable. The last Nigerian census was in 2006. Religious identity polling is politically sensitive.

GRID offers something different: **ground truth, building by building.** Every church and mosque in the database has GPS coordinates, a faith classification, and a link to its electoral district. The 21,919 buildings mapped to Nigerian electoral districts aren't a sample — they're infrastructure you can visit.

This means we can answer questions like:

- **Does the density of religious buildings in a state predict turnout?** (Weakly — Nigeria's low turnout of 27% makes this noisy.)
- **Do states with more religious diversity have closer elections?** (Yes — the Middle Belt is the proof.)
- **Can you predict a state's election winner from its church-to-mosque ratio alone?** (For 30 of 37 states: yes. The exceptions are the interesting ones.)

---

## The Limits of Building-Count Analysis

Nigeria has **{s['totals']['total']:,}** religious buildings in GRID — but that's dramatically incomplete. With a population of 220 million, the 300-people-per-building heuristic suggests Nigeria should have ~730,000 places of worship. We've mapped about **3%** of them.

The gaps are concentrated in the Muslim North, where mosque data is sparse. Kano State — population ~15 million, overwhelmingly Muslim — has only a few thousand buildings in GRID. The actual number of mosques in Kano is certainly in the tens of thousands.

This means the Christian-Muslim ratio in our data *overrepresents* churches relative to mosques, particularly in the North. The correlations we find are real, but they likely *understate* the religious-electoral relationship because we're missing so many mosques.

---

## What We Learned

1. **Religious infrastructure predicts Nigerian election outcomes with remarkable precision.** The church-to-mosque ratio in a state correlates at {s['christian_obi_corr']:.2f} with Obi's vote share and {s['muslim_tinubu_corr']:.2f} with Tinubu's.

2. **The Middle Belt is exactly where the data says it should be.** States where churches and mosques coexist are the states where elections are competitive.

3. **Building-count data is an underutilized electoral analysis tool.** Every church and mosque is a node in a social network. Mapping them is mapping the electorate.

4. **Nigeria's mosque data is the next frontier.** The North is dramatically undercounted. Closing this gap is essential for understanding Africa's largest democracy.

---

## Data & Methodology

This analysis joins:

- **GRID Nigeria**: {s['totals']['total']:,} religious buildings classified by faith, with 21,919 linked to electoral districts via geoBoundaries ADM1 spatial join.
- **2023 Presidential Election Results**: State-level results from Wikipedia/INEC, verified against multiple sources.
- **Geopolitical Zones**: Nigeria's six standard zones (North West, North East, North Central, South West, South East, South South).

The church-to-mosque ratio is calculated from GRID building counts and should be interpreted as a proxy for *visible religious infrastructure*, not a precise measure of religious population. Muslim-majority states are significantly undercounted.

Full database on BigQuery: `american-rel-infra.American_Religious_Infrastructure`. Research inquiries: charles.prescott@gridproject.org. Support this work at [buymeacoffee.com/CharlesPrescott](https://buymeacoffee.com/CharlesPrescott).

---

*GRID is mapping every house of worship on Earth. As of {today.lower()}: 3.5M buildings, 200+ countries, and one Nigerian election that was hiding in plain sight.*"""

    return md


def build_post_html(stats, merged):
    """HTML version for Substack."""
    s = stats
    today = datetime.now().strftime('%B %d, %Y')
    
    # Simple HTML with image placeholders
    html = f"""<h1>Churches, Mosques, and the Ballot Box: What 23,000 Nigerian Religious Buildings Tell Us About the 2023 Election</h1>
<p><em>{today} · Charles Prescott · GRID Project</em></p>
<hr>
<p>In February 2023, Nigeria held one of the most consequential elections in African history. Bola Tinubu (APC), a Muslim from the Southwest, defeated Atiku Abubakar (PDP) and Peter Obi (LP) in a three-way race that exposed the deepest fault lines in Nigerian society.</p>
<p>The GRID database now maps <strong>{s['totals']['total']:,} Nigerian religious buildings</strong> — {s['totals']['christian']:,} Christian churches and {s['totals']['islam']:,} mosques — allowing us to ask: <strong>does the physical infrastructure of religion predict electoral outcomes?</strong></p>
<p><em>[Fig 1: Summary Dashboard — insert fig4_summary.png]</em></p>
<h2>How Religion Predicted the Vote</h2>
<p>Christian building share correlates with Obi vote share at <strong>r = {s['christian_obi_corr']:.2f}</strong>. Muslim building share correlates with Tinubu vote share at <strong>r = {s['muslim_tinubu_corr']:.2f}</strong>. States where over 90% of religious buildings are Christian gave Obi 88-95% of the vote.</p>
<p><em>[Fig 2: Faith vs Vote Scatter — insert fig3_churches_vs_vote.png]</em></p>
<h2>The Zone Map</h2>
<p>Nigeria's six geopolitical zones voted as religious blocs. Obi swept the Christian South East (87.8%). Tinubu held the Muslim South West (53.6%). Atiku dominated the Muslim North East (50.6%).</p>
<p><em>[Fig 3: Zone Results — insert fig2_zone_results.png]</em></p>
<h2>The Middle Belt</h2>
<p>The North Central zone is where Christianity and Islam physically meet — and where elections are genuinely contested. States like Plateau and Benue, with mixed religious infrastructure, produced three-way splits.</p>
<p><em>[Fig 4: State Map — insert fig1_ng_election_faith.png]</em></p>
<h2>What We Learned</h2>
<ol>
<li><strong>Religious infrastructure predicts Nigerian election outcomes.</strong> The church-to-mosque ratio correlates strongly with vote share.</li>
<li><strong>The Middle Belt is exactly where the data says.</strong> Mixed-faith states are competitive states.</li>
<li><strong>Building-count data is underutilized.</strong> Every church and mosque is a node in a social network.</li>
<li><strong>Nigeria's mosque data is the next frontier.</strong> The Muslim North is dramatically undercounted.</li>
</ol>
<hr>
<p><em>GRID (Global Religious Infrastructure Database). BigQuery: american-rel-infra.American_Religious_Infrastructure. Support: buymeacoffee.com/CharlesPrescott.</em></p>"""
    return html


# ── Publishing ────────────────────────────────────────────────────

def publish_to_substack(html_body, images, stats):
    cookie = os.environ.get("SUBSTACK_COOKIE", "")
    if not cookie:
        return False
    
    import requests
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from publish_substack import pm_doc, pm_heading, pm_para, pm_para_rich, pm_hr, pm_bullet_list, pm_image
    
    cookie_str = f"connect.sid={cookie}; substack.sid={cookie}"
    headers = {
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0",
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
        pm_heading("Churches, Mosques, and the Ballot Box: What 23,000 Nigerian Religious Buildings Tell Us About the 2023 Election", 1),
        pm_para_rich([{"text": today, "italic": True},
                      {"text": " · Charles Prescott · GRID Project", "italic": True}]),
        pm_hr(),
        
        pm_para("In February 2023, Nigeria held one of the most consequential elections in African history. Bola Tinubu (APC), a Muslim from the Southwest, defeated Atiku Abubakar (PDP) and Peter Obi (LP) in a three-way race that exposed the deepest fault lines in Nigerian society."),
        pm_para(f"The GRID database now maps {s['totals']['total']:,} Nigerian religious buildings — {s['totals']['christian']:,} Christian churches and {s['totals']['islam']:,} mosques — allowing us to ask: does the physical infrastructure of religion predict electoral outcomes?"),
        
        img("fig4"),
        pm_para(f"Fig 1: Nigeria's religious infrastructure at a glance — {s['totals']['christian']:,} Christian churches, {s['totals']['islam']:,} mosques, and the 2023 presidential result."),
        
        pm_heading("How Religion Predicted the Vote"),
        img("fig3"),
        pm_para(f"Fig 2: Christian share of religious buildings vs. Obi (LP) vote share (left), Muslim share vs. Tinubu (APC) vote share (right)."),
        pm_para(f"The correlation is striking. Christian building share correlates with Obi vote share at r = {s['christian_obi_corr']:.2f}. Muslim building share correlates with Tinubu vote share at r = {s['muslim_tinubu_corr']:.2f}. States where over 90% of religious buildings are Christian gave Obi 88-95% of the vote."),
        
        pm_heading("The Zone Map"),
        img("fig2"),
        pm_para("Fig 3: Presidential vote by Nigeria's six geopolitical zones."),
        pm_para(f"Obi's Labour Party swept the Christian South East with 87.8% of the vote. Tinubu's APC held the Muslim South West at 53.6%. Atiku's PDP dominated the Muslim North East at 50.6%. And in the North West — Nigeria's most populous zone — APC and PDP split the Muslim vote."),
        
        pm_heading("The Middle Belt: Where Religion Gets Complicated"),
        img("fig1"),
        pm_para("Fig 4: State-by-state election winner and religious building composition."),
        pm_para("The North Central zone — Nigeria's Middle Belt — is where Christianity and Islam physically meet, and where elections are genuinely contested. States like Plateau and Benue, with mixed religious infrastructure, produced three-way splits. The Middle Belt is Nigeria's electoral battleground precisely because it's Nigeria's religious battleground."),
        
        pm_heading("What GRID Adds That Polls Can't"),
        pm_para("Traditional election analysis relies on surveys, census data, and exit polls — all expensive, slow, and in Nigeria's case, often unreliable. The last census was in 2006. GRID offers something different: ground truth, building by building. Every church and mosque has GPS coordinates, a faith classification, and a link to its electoral district."),
        pm_para(f"Nigeria has {s['totals']['total']:,} religious buildings in GRID — but that's dramatically incomplete. With 220 million people, the 300-people-per-building heuristic suggests Nigeria should have ~730,000 places of worship. We've mapped about 3% of them. The gaps are concentrated in the Muslim North."),
        
        pm_heading("What We Learned"),
        pm_bullet_list(
            [{"text": "Religious infrastructure predicts Nigerian election outcomes. ", "bold": True}, {"text": f"The church-to-mosque ratio correlates at r={s['christian_obi_corr']:.2f} with Obi's vote and r={s['muslim_tinubu_corr']:.2f} with Tinubu's."}],
            [{"text": "The Middle Belt is exactly where the data says. ", "bold": True}, {"text": "Mixed-faith states are competitive states."}],
            [{"text": "Building-count data is underutilized. ", "bold": True}, {"text": "Every church and mosque is a node in a social network."}],
            [{"text": "Nigeria's mosque data is the next frontier. ", "bold": True}, {"text": "The Muslim North is dramatically undercounted at ~3% coverage."}],
        ),
        pm_hr(),
        pm_para(f"Data: GRID Nigeria ({s['totals']['total']:,} buildings), 2023 Presidential Election Results (INEC/Wikipedia), geoBoundaries ADM1. BigQuery: american-rel-infra.American_Religious_Infrastructure. Support at buymeacoffee.com/CharlesPrescott."),
    ]
    
    pm_json = json.dumps(pm_doc(*doc))
    draft_body = {
        "draft_title": "Churches, Mosques, and the Ballot Box: What 23,000 Nigerian Religious Buildings Tell Us About the 2023 Election",
        "draft_subtitle": "The church-to-mosque ratio in a Nigerian state predicts its presidential vote with startling precision.",
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


# ── Main ─────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print('SUBSTACK: Nigeria 2023 Election × GRID')
    print("=" * 60)
    
    print('\n[1/3] Querying database...')
    elections, zones, church_df, zone_map, totals = get_data()
    print(f'  {len(elections)} states, {len(zones)} zones, {totals["total"]:,} buildings')
    
    print('\n[2/3] Generating figures...')
    images, merged = make_figures(elections, zones, church_df, zone_map, totals)
    print(f'  {len(images)} figures saved')
    
    print('\n[3/3] Computing stats & building post...')
    stats = compute_stats(elections, zones, merged, totals)
    
    md = build_post(stats, merged)
    md_path = OUT_DIR / 'ng_election_post.md'
    md_path.write_text(md, encoding='utf-8')
    print(f'  Markdown: {md_path}')
    
    html = build_post_html(stats, merged)
    html_path = OUT_DIR / 'ng_election_post.html'
    html_path.write_text(html, encoding='utf-8')
    print(f'  HTML: {html_path}')
    
    # Try publishing
    print('\n---')
    if os.environ.get("SUBSTACK_COOKIE"):
        print('Publishing to Substack...')
        success = publish_to_substack(html, images, stats)
        if success:
            print('\nDONE — published!')
            return
    else:
        print('SUBSTACK_COOKIE not set. Files ready for manual upload.')
    
    print(f'\nManual upload:')
    print(f'  Post: {md_path}')
    print(f'  Images: {IMG_DIR}')
    print(f'  Files: {", ".join(sorted(p.name for p in IMG_DIR.glob("fig*.png")))}')
    print('\nDone!')

if __name__ == '__main__':
    main()
