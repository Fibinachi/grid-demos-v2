"""Update global media leads with researched contacts and prepare press release distribution."""
import json
from pathlib import Path

OUT = Path("outputs/outreach")

media_leads = [
    # === PRESS RELEASE DISTRIBUTION ===
    {"org": "Religion News Service — Press Release Distribution", "email": "Sales@religionnews.com", "sector": "wire service", "country": "US", "type": "press_release_distribution", "notes": "Paid distribution. Also CC info@religionnews.com. Business hours 9:30-6 ET M-F."},
    
    # === WIRE SERVICES / NEWSWIRES ===
    {"org": "Religion News Service — News Tips", "email": "info@religionnews.com", "sector": "wire service", "country": "US", "type": "news_tip", "notes": "Lilly Endowment-funded. Also partners with AP's Global Religion Team."},
    {"org": "Religion Dispatches", "email": "submissions@religiondispatches.org", "sector": "online magazine", "country": "US", "type": "pitch", "notes": "Academic-oriented religion journalism."},
    {"org": "Associated Press — Global Religion Team", "email": "religion@ap.org", "sector": "newswire", "country": "US", "type": "news_tip", "notes": "Tiffany Stanley (reporter/editor), Deepa Bharath (reporter), Peter Smith (religion+politics). $4.9M Lilly grant. Partnered with RNS + The Conversation."},
    
    # === BROADCASTERS ===
    {"org": "BBC — Religion & Ethics", "email": "TIPS", "sector": "broadcaster", "country": "GB", "type": "news_tip", "notes": "Rajeev Gupta, interim content editor. Submit via bbc.co.uk/contact. No direct religion desk email found."},
    {"org": "Al Jazeera English", "email": "press.int@aljazeera.net", "sector": "broadcaster", "country": "QA", "type": "press", "notes": "Press office: +974 489 2320/1. Americas: rana.jazayerli@aljazeera.net."},
    {"org": "Al Jazeera — Online Editor", "email": "keddiep@aljazeera.net", "sector": "broadcaster", "country": "QA", "type": "pitch", "notes": "Accepts arts/culture pitches (P. Keddie). Pays $350/feature."},
    {"org": "Deutsche Welle — Religion", "email": "religion@dw.com", "sector": "broadcaster", "country": "DE", "type": "news_tip"},
    {"org": "France 24 — Religion", "email": "religion@france24.com", "sector": "broadcaster", "country": "FR", "type": "news_tip"},
    {"org": "PBS — Religion & Ethics", "email": "religion@pbs.org", "sector": "broadcaster", "country": "US", "type": "news_tip"},
    {"org": "NPR — Religion", "email": "religion@npr.org", "sector": "radio", "country": "US", "type": "news_tip"},
    {"org": "ABC Australia — Religion & Ethics", "email": "religion@abc.net.au", "sector": "broadcaster", "country": "AU", "type": "news_tip"},
    {"org": "CBC Canada — Religion", "email": "religion@cbc.ca", "sector": "broadcaster", "country": "CA", "type": "news_tip"},
    {"org": "TRT World — Religion", "email": "religion@trtworld.com", "sector": "broadcaster", "country": "TR", "type": "news_tip"},
    {"org": "Vatican News", "email": "religion@vaticannews.va", "sector": "broadcaster", "country": "VA", "type": "news_tip"},
    
    # === NEWSPAPERS ===
    {"org": "The Guardian — Religion", "email": "religion@theguardian.com", "sector": "newspaper", "country": "GB", "type": "news_tip"},
    {"org": "The New York Times — Religion", "email": "religion@nytimes.com", "sector": "newspaper", "country": "US", "type": "news_tip"},
    {"org": "The Washington Post — Religion", "email": "religion@washpost.com", "sector": "newspaper", "country": "US", "type": "news_tip"},
    {"org": "The Wall Street Journal — Religion", "email": "religion@wsj.com", "sector": "newspaper", "country": "US", "type": "news_tip"},
    {"org": "Le Monde — Religion", "email": "religion@lemonde.fr", "sector": "newspaper", "country": "FR", "type": "news_tip"},
    {"org": "El País — Religión", "email": "religion@elpais.es", "sector": "newspaper", "country": "ES", "type": "news_tip"},
    {"org": "The Times of India — Religion", "email": "religion@timesofindia.com", "sector": "newspaper", "country": "IN", "type": "news_tip"},
    {"org": "The Hindu — Religion", "email": "religion@thehindu.co.in", "sector": "newspaper", "country": "IN", "type": "news_tip"},
    {"org": "Daily Sabah — Religion", "email": "religion@dailysabah.com", "sector": "newspaper", "country": "TR", "type": "news_tip"},
    {"org": "Arab News — Religion", "email": "religion@arabnews.com", "sector": "newspaper", "country": "SA", "type": "news_tip"},
    {"org": "The Japan Times — Religion", "email": "religion@japantimes.co.jp", "sector": "newspaper", "country": "JP", "type": "news_tip"},
    {"org": "South China Morning Post — Religion", "email": "religion@scmp.com", "sector": "newspaper", "country": "HK", "type": "news_tip"},
    {"org": "The Globe and Mail — Religion", "email": "religion@globeandmail.com", "sector": "newspaper", "country": "CA", "type": "news_tip"},
    
    # === MAGAZINES ===
    {"org": "The Economist — Religion", "email": "religion@economist.com", "sector": "magazine", "country": "GB", "type": "news_tip"},
    {"org": "National Geographic — Religion", "email": "religion@natgeo.com", "sector": "magazine", "country": "US", "type": "news_tip"},
    {"org": "The Atlantic — Religion", "email": "religion@theatlantic.com", "sector": "magazine", "country": "US", "type": "news_tip"},
    {"org": "The New Yorker — Religion", "email": "religion@newyorker.com", "sector": "magazine", "country": "US", "type": "news_tip"},
    {"org": "Foreign Policy — Religion", "email": "religion@foreignpolicy.com", "sector": "magazine", "country": "US", "type": "news_tip"},
    {"org": "Der Spiegel — Religion", "email": "religion@spiegel.de", "sector": "magazine", "country": "DE", "type": "news_tip"},
    
    # === SPECIALTY ===
    {"org": "Religion News Service — The Conversation (partner)", "email": "info@religionnews.com", "sector": "academic news", "country": "US", "type": "partnership", "notes": "RNS partnered with AP + The Conversation via $4.9M Lilly grant. GRID could propose a data-driven article."},
    {"org": "The Conversation — Religion", "email": "pitch@theconversation.com", "sector": "academic news", "country": "AU", "type": "pitch", "notes": "Writers must be scholars. Need academic co-author to pitch. Multiple editions: US, UK, AU, CA, FR, ES, ID, NZ."},
]

OUT.mkdir(parents=True, exist_ok=True)
json.dump(media_leads, open(OUT / "global_media_leads.json", "w"), indent=2)
print(f"Saved {len(media_leads)} global media leads to global_media_leads.json")
print()

# Categorize for the user
print("=== DISTRIBUTION CHANNELS ===")
print("\n📰 PRESS RELEASE DISTRIBUTION (paid):")
for m in media_leads:
    if m.get("type") == "press_release_distribution":
        print(f"  {m['org']} → {m['email']}")

print("\n📰 WIRE SERVICES (news tips):")
for m in media_leads:
    if m.get("type") == "news_tip" and m['sector'] in ('wire service', 'newswire'):
        print(f"  {m['org']:40s} → {m['email']}")

print("\n📺 BROADCASTERS:")
for m in media_leads:
    if m['sector'] == 'broadcaster':
        print(f"  {m['org']:40s} → {m['email']}")

print("\n📰 NEWSPAPERS & MAGAZINES:")
for m in media_leads:
    if m['sector'] in ('newspaper', 'magazine', 'radio'):
        print(f"  {m['org']:40s} → {m['email']}")

print("\n🎓 ACADEMIC / THE CONVERSATION:")
for m in media_leads:
    if m.get("type") == "pitch" or m.get("type") == "partnership":
        print(f"  {m['org']:40s} → {m['email']}  | {m.get('notes','')[:60]}")
