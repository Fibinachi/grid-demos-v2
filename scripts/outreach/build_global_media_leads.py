"""Build global media leads for GRID outreach.
Major news organizations with religion beats that would benefit from the dataset.

NOTE: Email addresses below are GENERIC PLACEHOLDERS.
Real contacts need research via LinkedIn, Muck Rack, or newsroom directories.
The org names and sectors are correct starting points."""
import json
from pathlib import Path

OUT = Path("outputs/outreach")

media_leads = [
    # Global news agencies — contacts need real research
    {"org": "BBC News — Religion & Ethics", "email": "PLACEHOLDER", "sector": "broadcaster", "country": "GB"},
    {"org": "Al Jazeera English", "email": "PLACEHOLDER", "sector": "broadcaster", "country": "QA"},
    {"org": "Reuters — Faith & Religion", "email": "PLACEHOLDER", "sector": "newswire", "country": "GB"},
    {"org": "Associated Press — Religion", "email": "PLACEHOLDER", "sector": "newswire", "country": "US"},
    {"org": "CNN — Belief Blog / Religion", "email": "PLACEHOLDER", "sector": "broadcaster", "country": "US"},
    {"org": "Deutsche Welle — Religion", "email": "PLACEHOLDER", "sector": "broadcaster", "country": "DE"},
    {"org": "France 24 — Religion", "email": "PLACEHOLDER", "sector": "broadcaster", "country": "FR"},
    {"org": "The Guardian — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "GB"},
    {"org": "The New York Times — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "US"},
    {"org": "The Washington Post — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "US"},
    {"org": "The Wall Street Journal — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "US"},
    {"org": "The Economist — Religion", "email": "PLACEHOLDER", "sector": "magazine", "country": "GB"},
    {"org": "National Geographic — Religion", "email": "PLACEHOLDER", "sector": "magazine", "country": "US"},
    {"org": "The Atlantic — Religion", "email": "PLACEHOLDER", "sector": "magazine", "country": "US"},
    {"org": "The New Yorker — Religion", "email": "PLACEHOLDER", "sector": "magazine", "country": "US"},
    {"org": "Foreign Policy — Religion", "email": "PLACEHOLDER", "sector": "magazine", "country": "US"},
    {"org": "Le Monde — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "FR"},
    {"org": "El País — Religión", "email": "PLACEHOLDER", "sector": "newspaper", "country": "ES"},
    {"org": "Der Spiegel — Religion", "email": "PLACEHOLDER", "sector": "magazine", "country": "DE"},
    {"org": "The Times of India — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "IN"},
    {"org": "The Hindu — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "IN"},
    {"org": "Daily Sabah — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "TR"},
    {"org": "Arab News — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "SA"},
    {"org": "The Japan Times — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "JP"},
    {"org": "South China Morning Post — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "HK"},
    {"org": "The Globe and Mail — Religion", "email": "PLACEHOLDER", "sector": "newspaper", "country": "CA"},
    {"org": "ABC Australia — Religion & Ethics", "email": "PLACEHOLDER", "sector": "broadcaster", "country": "AU"},
    {"org": "CBC Canada — Religion", "email": "PLACEHOLDER", "sector": "broadcaster", "country": "CA"},
    {"org": "TRT World — Religion", "email": "PLACEHOLDER", "sector": "broadcaster", "country": "TR"},
    {"org": "PBS — Religion & Ethics NewsWeekly", "email": "PLACEHOLDER", "sector": "broadcaster", "country": "US"},
    {"org": "NPR — Religion", "email": "PLACEHOLDER", "sector": "radio", "country": "US"},
    {"org": "The Conversation — Religion", "email": "PLACEHOLDER", "sector": "academic news", "country": "AU"},
    {"org": "Religion News Service", "email": "PLACEHOLDER", "sector": "wire service", "country": "US"},
    {"org": "Vatican News", "email": "PLACEHOLDER", "sector": "broadcaster", "country": "VA"},
]

OUT.mkdir(parents=True, exist_ok=True)
json.dump(media_leads, open(OUT / "global_media_leads.json", "w"), indent=2)
print(f"Saved {len(media_leads)} global media leads to global_media_leads.json")
for m in media_leads:
    print(f"  {m['org']:50s} | {m['sector']:16s} | {m['country']}")
