"""Check pin data structure."""
import json
with open('data/religiana_pins.json') as f:
    pins = json.load(f)
print(f'Total pins: {len(pins)}')
keys = list(pins[0].keys()) if pins else 'empty'
print(f'Sample keys: {keys}')
print(f'Sample: {json.dumps(pins[:3], indent=2)}')
ids = [int(p['church_id']) for p in pins]
print(f'Min ID: {min(ids)}, Max ID: {max(ids)}')
print(f'Unique IDs: {len(set(ids))}')
