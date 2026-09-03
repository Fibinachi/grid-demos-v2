"""Test refined DuckDuckGo search for churches."""
from duckduckgo_search import DDGS
import time

test_churches = [
    ("First Baptist Church", "Springfield", "IL"),
    ("St. John's Lutheran Church", "Charleston", "SC"),
    ("Grace Community Church", "Nashville", "TN"),
    ("New Life Pentecostal Church", "Columbus", "OH"),
]

for name, city, state in test_churches:
    query = f'{name} {city} {state} church'
    print('Search:', query)
    
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=5))
    
    found_website = None
    for r in results:
        url = r.get('href', '')
        title = r.get('title', '')
        body = (r.get('body', '') or '')
        skip_words = ['wikipedia', 'dictionary', 'merriam', 'facebook', 'yelp', 'linkedin', 'instagram']
        if any(w in url.lower() for w in skip_words):
            continue
        church_words = ['church', 'ministry', 'pastor', 'worship', 'baptist', 'lutheran', 'pentecostal', 'methodist']
        text = (title + ' ' + body).lower()
        if any(w in text for w in church_words) or any(w in url.lower() for w in church_words):
            found_website = url
            break
    
    if found_website:
        print('  FOUND:', found_website)
    else:
        print('  No church website found')
        for r in results[:3]:
            print('  -', r.get('href',''))
    print()
    time.sleep(1)
