"""Test IA search API for city directories."""
import requests, json, sys

url = 'https://archive.org/advancedsearch.php'
params = {
    'q': 'title:"city directory" AND year:[1960 TO 1980]',
    'output': 'json',
    'rows': 25,
    'sort': 'date',
    'fl': ['identifier', 'title', 'year', 'date', 'creator', 'collection']
}
r = requests.get(url, params=params, timeout=30)
data = r.json()
print(f'Total results: {data["response"]["numFound"]}')
print()

for doc in data['response']['docs'][:20]:
    title = doc.get('title', 'N/A')[:90]
    year = doc.get('year', 'N/A')
    ident = doc.get('identifier', 'N/A')
    coll = ', '.join(doc.get('collection', [])[:3])
    print(f'{year} | {ident}')
    print(f'  {title}')
    print(f'  Collections: {coll}')
    print()
