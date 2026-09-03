"""Test address-based church website search."""
from duckduckgo_search import DDGS
import time, re

# Test with real churches from different sources
test_cases = [
    # Format: (name, street, city, state, zip)
    ("First Baptist Church", "500 E Capitol St SE", "Washington", "DC", "20003"),
    ("St. John's Lutheran Church", "4139 N Tonalea Dr", "Tucson", "AZ", "85749"),
    ("Victory Church", "1700 Tullie Rd NE", "Atlanta", "GA", "30329"),
    ("Calvary Church", "8200 E Belleview Ave", "Denver", "CO", "80237"),
]

def search_church(name, street, city, state):
    queries = [
        f'{name} {city} {state}',
        f'{name} {street} {city}',
        f'{street} {city} {state} church',
        f'{name} {city} {state} official website',
    ]
    
    all_results = []
    for query in queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
                for r in results:
                    url = r.get('href', '')
                    title = r.get('title', '')
                    body = (r.get('body', '') or '')
                    all_results.append((url, title, body, query))
        except Exception as e:
            print(f'  Error: {e}')
        time.sleep(0.5)
    
    # Score results
    scored = []
    for url, title, body, query in all_results:
        score = 0
        text = (title + ' ' + body).lower()
        url_lower = url.lower()
        
        # Skip unwanted
        skip = ['wikipedia', 'facebook', 'yelp', 'linkedin', 'instagram', 
                'twitter', 'yellowpages', 'whitepages', 'mapquest',
                'merriam-webster', 'dictionary', 'cambridge']
        if any(s in url_lower for s in skip):
            continue
        
        # It's likely a church website
        church_indicators = ['church', 'ministry', 'worship', 'pastor',
                            'sermon', 'bible', 'fellowship', 'chapel',
                            'catholic', 'baptist', 'lutheran', 'methodist',
                            'presbyterian', 'pentecostal', 'anglican',
                            'episcopal', 'evangelical', 'calvary']
        
        for indicator in church_indicators:
            if indicator in text or indicator in url_lower:
                score += 2
        
        # Personal pages / dashboards score lower
        if 'wordpress' in url_lower or 'squarespace' in url_lower:
            score -= 1
        if '.org' in url_lower or '.church' in url_lower:
            score += 1
        if city.lower() in text or city.lower() in url_lower:
            score += 1
        if state.lower() in text:
            score += 1
        
        # Exact name match = big bonus
        name_words = set(name.lower().split())
        for w in name_words:
            if len(w) > 3 and w in text:
                score += 2
        
        scored.append((score, url, title, query))
    
    scored.sort(reverse=True)
    return scored[:3] if scored else []

for name, street, city, state, zipcode in test_cases:
    print(f'Searching: {name}')
    print(f'  Address: {street}, {city}, {state} {zipcode}')
    
    results = search_church(name, street, city, state)
    
    if results:
        best_score, best_url, best_title, used_query = results[0]
        print(f'  BEST: {best_url}')
        print(f'  Score: {best_score}')
        print(f'  Query: "{used_query}"')
    else:
        print(f'  No website found')
    
    if len(results) > 1:
        print(f'  Also: {results[1][1][:70]}')
    print()
