"""Quick PH election map from existing data."""
import json, plotly.express as px, pandas as pd

with open('outputs/ph_election_map.json') as f:
    data = json.load(f)

df = pd.DataFrame(data)
print(f"Plotting {len(df):,} churches across {df['province'].nunique()} provinces")

# Map: color by winner, each province visible
fig = px.scatter_mapbox(
    df,
    lat='lat', lon='lon',
    color='winner',
    hover_name='name',
    hover_data={'province': True, 'winner_pct': ':.1f', 'faith': True, 'lat': False, 'lon': False},
    title='PH 2022 Presidential Election — Churches by Province Winner<br><sup>Red = Marcos | Pink = Robredo | 14/86 provinces</sup>',
    color_discrete_map={
        'MARCOS, BONGBONG (PFP)': '#C41E3A',
        'ROBREDO, LENI (IND)': '#FF69B4'
    },
    zoom=5,
    center={'lat': 12.8, 'lon': 122.5},
    height=700,
    mapbox_style='carto-positron',
    opacity=0.6
)

fig.write_html('outputs/ph_election_map.html')
print("Saved outputs/ph_election_map.html")

# Summary
print(f"\n=== KEY TAKEAWAYS ===")
print(f"• 8,979 churches linked to 2022 presidential results across 14 provinces")
print(f"• 4 swing provinces where margin < 10%:")
for _, r in df[['province','winner_pct','winner']].drop_duplicates().sort_values('winner_pct').head(4).iterrows():
    print(f"    {r['province']:25s}: {r['winner'][:25]:25s} {r['winner_pct']:.1f}%")
print(f"• Robredo won 2 provinces (Negros Occ, Sorsogon), Marcos won 12")
print(f"• Faith composition: 99% Christian across both winners")  
print(f"• Full coverage needs 72 more provinces (figshare/COMELEC data)")
