"""Sort Hostinger emails into categories."""
import json
from collections import Counter

d = json.load(open("scripts/outreach/hostinger_responses.json"))

# Classification breakdown
cats = Counter(r.get("classification", "UNKNOWN") for r in d)
print("=== CLASSIFICATION BREAKDOWN ===")
for cat, cnt in cats.most_common():
    print(f"  {cat:15s}: {cnt}")

print()

# Show POSITIVE/REAL replies
real = [r for r in d if r.get("classification") in ("REAL", "YES", "POSITIVE")]
print(f"=== POSITIVE/REAL REPLIES ({len(real)}) ===")
for r in real:
    preview = r.get("body_preview", "")[:200]
    print(f"  From: {r['sender'][:45]:45s}")
    print(f"  Subj: {r['subject'][:70]}")
    print(f"  Body: {preview}")
    print()

# Show MAYBE replies
maybe = [r for r in d if r.get("classification") == "MAYBE"]
print(f"=== MAYBE REPLIES ({len(maybe)}) ===")
for r in maybe:
    preview = r.get("body_preview", "")[:150]
    print(f"  {r['sender'][:40]:40s} | {r['subject'][:55]}")
    print(f"    {preview}")
    print()

print()

# What we'll move to 'declines' folder
decline_types = {"DECLINE", "BOUNCE", "BOUNCE_SOFT", "SPAM", "AUTO_REPLY"}
declines = [r for r in d if r.get("classification") in decline_types]
print(f"=== TO ARCHIVE/DECLINES ({len(declines)} msgs) ===")
for r in declines[:5]:
    print(f"  [{r['classification']:12s}] {r['sender'][:35]:35s} | {r['subject'][:55]}")
print(f"  ... and {len(declines)-5} more")

# Count by folder
folders = Counter(r.get("folder", "?") for r in d)
print(f"\n=== BY FOLDER ===")
for f, cnt in folders.most_common():
    print(f"  {f:10s}: {cnt}")
