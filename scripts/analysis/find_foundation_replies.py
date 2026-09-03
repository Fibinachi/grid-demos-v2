"""Search Hostinger for actual foundation/philanthropy replies."""
import json

d = json.load(open("scripts/outreach/hostinger_responses.json"))

keywords = [
    "foundation", "grant", "fund", "scholarship", "philanthropy",
    "theology", "theological", "seminary", "trinity", "toronto",
    "tuition", "research", "support", "donation", "religious",
    "church", "ministry", "faith", "christian", "spiritual",
    "angel", "investor", "endowment"
]

found = set()
for kw in keywords:
    for r in d:
        text = (r.get("subject","") + " " + r.get("body_preview","")).lower()
        if kw in text:
            key = r.get("msg_id", r.get("sender","") + r.get("subject",""))
            found.add(key)

# Get unique matching messages
matched = []
seen_senders = set()
for r in d:
    key = r.get("msg_id", r.get("sender","") + r.get("subject",""))
    if key in found and r["sender"] not in seen_senders:
        matched.append(r)
        seen_senders.add(r["sender"])

# Sort by date (newest first)
matched.sort(key=lambda x: x.get("date",""), reverse=True)

print(f"=== FOUNDATION-RELATED HOSTINGER REPLIES ({len(matched)}) ===")
for i, r in enumerate(matched, 1):
    preview = (r.get("body_preview") or "")[:200]
    print(f"\n--- #{i} ---")
    print(f"  From: {r['sender'][:50]}")
    print(f"  Subj: {r['subject'][:70]}")
    print(f"  Date: {r['date'][:16]}")
    print(f"  Class: {r.get('classification','?')}")
    print(f"  Body: {preview}")

print(f"\n\n=== NON-FOUNDATION (everything else): {len(d) - len(matched)} messages ===")
