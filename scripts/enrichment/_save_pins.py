"""Save the Religiana pin data from the JS temp file to the project."""
import json, os

SRC = r"c:\Users\charlesp\AppData\Roaming\Code\User\workspaceStorage\57f490fd5e5d93b548e5747412df34f1\GitHub.copilot-chat\chat-session-resources\f5b5d7a8-4536-44b6-bb8f-e8f1a88ad8ee\call_00_jwLTxOmM2rUEDgKR0tvf3949__vscode-1781963447555\content.txt"
DST = "data/religiana_pins.json"

with open(SRC, 'r', encoding='utf-8') as f:
    raw = f.read()

# File has format: Result: "[{...}]" — strip the Result: wrapper and outer quotes
if raw.startswith('Result: "'):
    inner = raw[len('Result: "'):-1]  # Strip prefix and trailing "
elif raw.startswith('Result: '):
    inner = raw[len('Result: '):]
else:
    inner = raw

# Unescape escaped quotes
inner = inner.replace('\\"', '"')

# Parse then re-serialize to validate
pins = json.loads(inner)
print(f"Loaded {len(pins)} pins from temp file")
print(f"ID range: {pins[0]['church_id']} .. {pins[-1]['church_id']}")

# Check for dupes
ids = [p['church_id'] for p in pins]
print(f"Unique IDs: {len(set(ids))}")
if len(ids) != len(set(ids)):
    from collections import Counter
    dupes = [k for k,v in Counter(ids).items() if v > 1]
    print(f"WARNING: {len(dupes)} duplicate IDs found")

# Write properly
with open(DST, 'w', encoding='utf-8') as f:
    json.dump(pins, f, ensure_ascii=False)

print(f"Saved to {DST} ({os.path.getsize(DST)} bytes)")
print(f"Sample: {pins[0]}")
