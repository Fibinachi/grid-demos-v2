import json
r = json.load(open('gmail_responses.json'))
for x in r:
    print(f"Foundation: {x['foundation']}")
    print(f"From: {x['sender']}")
    print(f"Subject: {x['subject']}")
    print(f"Classification: {x['classification']}")
    print(f"Body preview:")
    print(f"  {x['body_preview'][:300]}")
    print()
