"""Show YES/warm leads and archive declines."""
import json

d = json.load(open("scripts/outreach/hostinger_responses.json"))

# Show YES replies
yes = [r for r in d if r.get("classification") == "YES"]
print(f"=== WARM LEADS ({len(yes)}) ===")
for i, r in enumerate(yes, 1):
    preview = (r.get("body_preview") or "")[:200]
    print(f"\n--- #{i} ---")
    print(f"  From: {r['sender']}")
    print(f"  Subj: {r['subject']}")
    print(f"  Date: {r['date'][:16]}")
    print(f"  Body: {preview}")

# Items to archive (NO, AUTO, BOUNCE = 28 total)
archive = [r for r in d if r.get("classification") in ("NO", "AUTO", "BOUNCE")]
archive_senders = set(r["sender"].lower() for r in archive)
print(f"\n\n=== TO ARCHIVE ({len(archive)} items) ===")
for r in archive:
    print(f"  [{r['classification']:5s}] {r['sender'][:40]:40s} | {r['subject'][:55]}")
