"""Quick add SafeGraph to unified queue."""
import json
from pathlib import Path
from datetime import datetime

OUT = Path("outputs/outreach")
QUEUE_FILE = OUT / "unified_queue.jsonl"
NOW = datetime.now().strftime("%B %d, %Y")

body = """Subject: GRID: 3.5M Worship Sites - Fill the Religious POI Gap in SafeGraph Places

Dear SafeGraph Data Team,

I'm reaching out because SafeGraph Places is the gold standard for POI data - but religious sites are notoriously hard to get right. Denominations change, churches close and reopen, mosques relocate. I've built exactly the dataset to fill this gap.

GRID (Global Religious Infrastructure Database) has 3,537,585 worship sites - every church, mosque, synagogue, temple, and gurdwara worldwide. Here's what makes it different from OSM or Google Places:

WHY GRID > RAW OSM FOR RELIGIOUS POIs:
- 85+ faith traditions classified (200+ Christian denominations, not just "Christian")
- 17 Muslim traditions (Sunni/Shia/Twelver/Ismaili/Salafi/etc.)
- 12 Jewish movements (Orthodox/Chabad/Reform/Conservative/etc.)
- Name-normalized - "First Baptist Church" vs "1st Bpt Ch" resolved
- Denomination hierarchies built (Catholic dioceses, Lutheran synods, LDS stakes)
- 463K+ verified phone numbers, emails, websites
- 614K US addresses normalized (IRS + Overture/OSM cross-referenced)
- Census tract, congressional district, county mapped for every US site

YOUR PLACES DATASET + GRID:
I imagine this could work as:
1. Bulk data license - the full 3.5M religious sites as a Places supplement
2. API enrichment - match your POI IDs to GRID for faith/tradition classification
3. Ongoing refresh partnership - GRID actively maintained, not a one-time dump

Happy to send sample data, discuss pricing, or jump on a call. This is the world's most comprehensive religious POI dataset - and it's built specifically to solve the religious site accuracy problem that every POI provider struggles with.

--
Charles Prescott
Creator, GRID - Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542
https://buymeacoffee.com/CharlesPrescott"""

entry = {
    "to": "press@safegraph.com",
    "subject": "GRID: 3.5M Worship Sites - Fill the Religious POI Gap in SafeGraph Places",
    "body": body,
    "source": "cppa_safegraph",
    "org": "SafeGraph",
    "queued": NOW,
}

existing = []
if QUEUE_FILE.exists():
    existing = [json.loads(l) for l in QUEUE_FILE.read_text(encoding="utf-8").strip().split("\n") if l.strip()]

existing_emails = {e.get("to", "").lower() for e in existing}
if entry["to"] in existing_emails:
    print("Already in queue.")
else:
    all_entries = existing + [entry]
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        for item in all_entries:
            f.write(json.dumps(item) + "\n")
    print(f"SafeGraph added. Queue: {len(existing)} -> {len(all_entries)} entries ({len(all_entries)*3/3600:.1f} days)")
