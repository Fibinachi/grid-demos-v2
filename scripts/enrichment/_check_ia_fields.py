import requests, json
r = requests.get('https://archive.org/advancedsearch.php', params={
    'q': 'title:"city directory" AND year:[1970 TO 1975]',
    'output': 'json', 'rows': 2
})
print(json.dumps(r.json()['response']['docs'][0], indent=2))
