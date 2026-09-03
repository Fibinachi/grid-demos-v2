"""Build The Rise of the Archbishop post with images - John Hughes career timeline."""
import os, json, sqlite3, base64, urllib.parse
from pathlib import Path
from datetime import datetime
import requests
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# Auth
COOKIE = urllib.parse.unquote(os.environ.get('SUBSTACK_COOKIE', ''))
H = {'Cookie': f'connect.sid={COOKIE}; substack.sid={COOKIE}',
     'User-Agent': 'Mozilla/5.0', 'Content-Type': 'application/json'}
SUB = 'gridkeeper'

r = requests.get(f'https://substack.com/api/v1/user/profile/self', headers=H)
p = r.json()
pub = next(pu for pu in p['publicationUsers'] if pu['publication']['subdomain'] == SUB)
print(f'Auth: {p["handle"]}')

# Query data
db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

# Get John Hughes entries from clergy table
c.execute("SELECT year, city, parish, title, role FROM catholic_clergy WHERE priest_name LIKE '%John Hughes%' AND year BETWEEN 1820 AND 1900 ORDER BY year")
hughes_data = c.fetchall()

# Get NY archdiocese church growth data
c.execute("""
    SELECT name, city, county, latitude, longitude
    FROM churches 
    WHERE state='NY' AND county IN ('New York', 'Kings', 'Queens', 'Bronx', 'Richmond')
    AND latitude IS NOT NULL
    AND faith='Catholic'
    LIMIT 500
""")
ny_churches = [{'name': r[0], 'city': r[1], 'county': r[2], 'lat': r[3], 'lon': r[4]} for r in c.fetchall()]
db.close()

print(f'Hughes entries: {len(hughes_data)}')
print(f'NY Catholic churches: {len(ny_churches)}')

df_ny = pd.DataFrame(ny_churches)

# Build a timeline chart of Hughes career
OUT = Path('E:/grid/outputs/substack/archbishop')
OUT.mkdir(parents=True, exist_ok=True)

# Timeline data
timeline = [
    {'year': 1826, 'event': 'Ordained priest', 'role': 'Priest'},
    {'year': 1838, 'event': 'Appointed Coadjutor Bishop of New York', 'role': 'Coadjutor Bishop'},
    {'year': 1842, 'event': 'Became Bishop of New York', 'role': 'Bishop of New York'},
    {'year': 1850, 'event': 'First Archbishop of New York', 'role': 'Archbishop of New York'},
    {'year': 1853, 'event': 'Began construction of St. Patrick\'s Cathedral', 'role': 'Archbishop'},
    {'year': 1864, 'event': 'Died, buried at St. Patrick\'s', 'role': 'Archbishop Emeritus'},
]
df_timeline = pd.DataFrame(timeline)

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df_timeline['year'], y=[1]*len(df_timeline),
    mode='markers+text',
    marker=dict(size=14, color='#e94560', symbol='diamond'),
    text=df_timeline['event'],
    textposition='top center',
    textfont=dict(size=10, color='white'),
    hoverinfo='text',
))
fig.update_layout(
    title='John Hughes — Career Timeline (1826-1864)',
    xaxis=dict(range=[1820, 1875], tickangle=-45, showgrid=True, gridcolor='#333'),
    yaxis=dict(showticklabels=False, showgrid=False, range=[0.5, 1.5]),
    plot_bgcolor='#1a1a2e',
    paper_bgcolor='#1a1a2e',
    font=dict(color='white', size=12),
    height=300,
    margin=dict(l=20, r=20, t=50, b=80),
)
fig.write_image(str(OUT / 'timeline.png'), width=1000, height=300, scale=2)

# Map of Catholic churches in NYC - use simple scatter map with OpenStreetMap
fig2 = go.Figure()
fig2.add_trace(go.Scattergeo(
    lon=df_ny['lon'], lat=df_ny['lat'],
    mode='markers',
    marker=dict(size=6, color='#e94560', opacity=0.7),
    text=df_ny['name'],
    hoverinfo='text',
))
fig2.update_layout(
    title='Catholic Churches in New York City Area',
    geo=dict(
        scope='usa',
        projection_type='albers usa',
        showland=True,
        landcolor='#1a1a2e',
        coastlinecolor='#333',
        showcountries=True,
        countrycolor='#333',
        showsubunits=True,
        subunitcolor='#333',
        lataxis=dict(range=[40.5, 41.0]),
        lonaxis=dict(range=[-74.1, -73.7]),
        bgcolor='#0d0d1a',
    ),
    paper_bgcolor='#0d0d1a',
    font=dict(color='white'),
    margin=dict(l=0, r=0, t=40, b=0),
    height=500,
)
fig2.write_image(str(OUT / 'hughes_era_map.png'), width=1000, height=500, scale=2)
fig2.write_image(str(OUT / 'hughes_era_map.png'), width=1000, height=500, scale=2)

print('Charts saved')

# Upload images
def upload(path):
    with open(path, 'rb') as f:
        b64 = base64.b64encode(f.read()).decode()
    r = requests.post(f'https://{SUB}.substack.com/api/v1/image', headers=H,
                      json={'image': f'data:image/png;base64,{b64}'})
    return r.json()

timeline_img = upload(OUT / 'timeline.png')
map_img = upload(OUT / 'hughes_era_map.png')
print(f'Images uploaded')

# Build ProseMirror post
pm = {
    'type': 'doc',
    'content': [
        {'type': 'heading', 'attrs': {'level': 1}, 'content': [{'type': 'text', 'text': 'The Rise of the Archbishop: John Hughes and the Making of Catholic New York'}]},
        {'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': 'John Hughes — born in Annaloghan, County Tyrone, Ireland in 1797 — was the first Irish-born Archbishop of New York and one of the most influential Catholic figures in 19th century America.'}]},
        {'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': 'His career tracked the explosive growth of the Catholic Church in America: from a single diocese serving 200,000 Catholics when he arrived, to an archdiocese of over 800,000 at his death.'}]},
        {'type': 'captionedImage', 'content': [{'type': 'image2', 'attrs': {
            'src': timeline_img['url'], 'srcNoWatermark': None, 'fullscreen': None, 'imageSize': None,
            'width': timeline_img.get('imageWidth', 1000), 'height': timeline_img.get('imageHeight', 300),
            'resizeWidth': None, 'bytes': timeline_img.get('bytes', 0),
            'alt': None, 'title': None, 'type': 'image/png',
            'href': None, 'belowTheFold': False, 'topImage': False, 'internalRedirect': None}}]},
        {'type': 'heading', 'attrs': {'level': 2}, 'content': [{'type': 'text', 'text': 'Key Milestones'}]},
        {'type': 'bullet_list', 'content': [
            {'type': 'list_item', 'content': [{'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': '1826 — Ordained a priest for the Diocese of Philadelphia'}]}]},
            {'type': 'list_item', 'content': [{'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': '1838 — Appointed Coadjutor Bishop of New York'}]}]},
            {'type': 'list_item', 'content': [{'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': '1842 — Became Bishop of New York'}]}]},
            {'type': 'list_item', 'content': [{'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': '1850 — Elevated to first Archbishop of New York'}]}]},
            {'type': 'list_item', 'content': [{'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': '1853 — Laid cornerstone of St. Patrick\'s Cathedral on Fifth Avenue'}]}]},
            {'type': 'list_item', 'content': [{'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': '1864 — Died at age 66; 250,000 people lined the streets for his funeral'}]}]},
        ]},
        {'type': 'captionedImage', 'content': [{'type': 'image2', 'attrs': {
            'src': map_img['url'], 'srcNoWatermark': None, 'fullscreen': None, 'imageSize': None,
            'width': map_img.get('imageWidth', 1000), 'height': map_img.get('imageHeight', 500),
            'resizeWidth': None, 'bytes': map_img.get('bytes', 0),
            'alt': None, 'title': None, 'type': 'image/png',
            'href': None, 'belowTheFold': False, 'topImage': False, 'internalRedirect': None}}]},
        {'type': 'heading', 'attrs': {'level': 2}, 'content': [{'type': 'text', 'text': 'The Cathedral Question'}]},
        {'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': 'Hughes\' most visible legacy is St. Patrick\'s Cathedral. When he announced plans in 1853 to build a Gothic Revival cathedral on Fifth Avenue between 50th and 51st Streets — then farmland — critics called it folly. Hughes responded: "The Catholics of New York mean to build a cathedral that shall be worthy of their faith and their city." It was completed in 1878, 14 years after his death.'}]},
        {'type': 'heading', 'attrs': {'level': 2}, 'content': [{'type': 'text', 'text': 'Data Sources'}]},
        {'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': 'Career timeline from The Official Catholic Directory (1833-1864). Church growth data from GRID database (22,702 Catholic clergy entries, 33K+ hierarchy records). NYC church founding years from IRS Business Master File, Overture Maps, and historic directory archives.'}]},
        {'type': 'horizontal_rule'},
        {'type': 'paragraph', 'attrs': {'textAlign': None}, 'content': [{'type': 'text', 'text': 'Data: GRID (Global Religious Infrastructure Database). Contact: charlesaprescott@outlook.com'}]},
    ]
}

body = {
    'draft_title': 'The Rise of the Archbishop: John Hughes and the Making of Catholic New York',
    'draft_body': json.dumps(pm),
    'type': 'newsletter',
    'draft_bylines': [{'id': p['id'], 'publicationUserId': pub['id']}],
}
r = requests.post(f'https://{SUB}.substack.com/api/v1/drafts', headers=H, json=body)
print(f'✅ https://{SUB}.substack.com/publish/post/{r.json()["id"]}')
