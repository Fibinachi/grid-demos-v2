"""Scrape Wikipedia's list of US + Canada Catholic dioceses as canonical reference."""
import requests, re, json

headers = {'User-Agent': 'GRID-Project/1.0 (research; charlesaprescott@outlook.com)'}

def scrape_page(page, section):
    """Scrape dioceses from a Wikipedia page section."""
    r = requests.get('https://en.wikipedia.org/w/api.php', params={
        'action': 'parse', 'page': page,
        'prop': 'wikitext', 'format': 'json', 'section': section
    }, headers=headers)
    data = r.json()
    text = data['parse']['wikitext']['*']
    
    dioceses = set()
    for m in re.finditer(r'\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]', text):
        title = m.group(1).strip()
        low = title.lower()
        if any(w in low for w in ['diocese', 'archdiocese', 'eparchy', 'archeparchy']):
            if any(skip in low for skip in ['list of', 'conference', 'catholic church in', 'titular']):
                continue
            name = title
            for prefix in ['Roman Catholic ', 'Diocese of ', 'Archdiocese of ', 'Eparchy of ', 'Archeparchy of ']:
                if name.startswith(prefix):
                    name = name[len(prefix):]
            dioceses.add(name)
    return dioceses

# US
us_current = scrape_page('List_of_Catholic_dioceses_in_the_United_States', '2')
us_former = scrape_page('List_of_Catholic_dioceses_in_the_United_States', '11')

# Canada
ca_current = scrape_page('List_of_Catholic_dioceses_in_Canada', '1')
ca_former = scrape_page('List_of_Catholic_dioceses_in_Canada', '24')

# Merge
all_current = sorted(us_current | ca_current)
all_former = sorted(us_former | ca_former)

print(f"US: {len(us_current)} current + {len(us_former)} former")
print(f"CA: {len(ca_current)} current + {len(ca_former)} former")
print(f"Total: {len(all_current)} current + {len(all_former)} former = {len(set(all_current)|set(all_former))} unique")

with open("E:/grid/data/directories/wikipedia_dioceses.json", "w") as f:
    json.dump({"current": all_current, "former": all_former}, f, indent=2)
print("Saved to data/directories/wikipedia_dioceses.json")
