"""
BUILD: Christian Missions Outreach — Census Data × Infrastructure Intersection
Targets mission-sending organizations with personalized pitches about how
GRID's census-enriched religious infrastructure data can inform their work.

Single-pass query for efficiency on 3.5M records.
"""
import sqlite3, json, sys, csv
from pathlib import Path
from datetime import datetime

# Add project root to path for gw_db import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from gw_db import connect

OUT = Path("outputs/outreach")
OUT.mkdir(parents=True, exist_ok=True)
QUEUE_FILE = OUT / "unified_queue.jsonl"
CAMPAIGN_FILE = OUT / "missions_census_contacts.csv"

SIG = """Charles Prescott
Creator, GRID — Global Religious Infrastructure Database
JD, LLM (Taxation) | Trinity College, University of Toronto
charlesaprescottjr@gmail.com | 843-504-4542"""

# ============================================================
# CENSUS STATS (cached, fast)
# ============================================================
def get_census_stats(db):
    stats = {}
    stats['county_count'] = db.execute("SELECT COUNT(*) FROM county_census_us").fetchone()[0]
    stats['church_census_links'] = db.execute("SELECT COUNT(*) FROM church_census_US").fetchone()[0]
    stats['total_churches'] = db.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
    stats['us_churches'] = db.execute("SELECT COUNT(*) FROM churches WHERE country='US'").fetchone()[0]

    # Church deserts: counties with 50K+ pop but <50 churches per 100K
    stats['church_deserts'] = db.execute("""
        SELECT COUNT(*) FROM (
            SELECT cu.county_fips FROM county_census_us cu
            LEFT JOIN churches c ON c.county_fips_5=cu.county_fips
            WHERE cu.total_pop > 50000
            GROUP BY cu.county_fips
            HAVING CAST(COUNT(c.id) AS REAL) / cu.total_pop * 100000 < 50
        )
    """).fetchone()[0]

    stats['high_poverty_counties'] = db.execute(
        "SELECT COUNT(*) FROM county_census_us WHERE poverty_rate > 20 AND total_pop > 10000"
    ).fetchone()[0]

    stats['diverse_counties'] = db.execute("""
        SELECT COUNT(DISTINCT c.county_fips_5) FROM churches c
        JOIN county_census_us cu ON c.county_fips_5=cu.county_fips
        WHERE cu.hispanic_pct > 25 OR cu.asian_pct > 10
    """).fetchone()[0]

    stats['countries_with_census'] = db.execute(
        "SELECT COUNT(DISTINCT country) FROM church_census_catalog WHERE category='census'"
    ).fetchone()[0]

    stats['total_contacts'] = db.execute(
        "SELECT COUNT(*) FROM church_contact_values WHERE contact_type='email'"
    ).fetchone()[0]

    return stats

# ============================================================
# SINGLE-PASS CONTACT DISCOVERY
# ============================================================
def find_mission_contacts(db):
    """Find all Christian mission orgs in a single efficient query."""

    exclusions = """AND name NOT LIKE '%rescue%' AND name NOT LIKE '%submission%'
    AND name NOT LIKE '%church%' AND name NOT LIKE '%parish%'
    AND name NOT LIKE '%chapel%' AND name NOT LIKE '%cathedral%'
    AND name NOT LIKE '%basilica%' AND name NOT LIKE '%shrine%'
    AND name NOT LIKE '%school%' AND name NOT LIKE '%academy%'
    AND name NOT LIKE '%college%' AND name NOT LIKE '%university%'
    AND name NOT LIKE '%hospital%' AND name NOT LIKE '%nursing%'
    AND name NOT LIKE '%day care%' AND name NOT LIKE '%preschool%'
    AND name NOT LIKE '%cemetery%' AND name NOT LIKE '%seminary%'"""

    query = f"""
    SELECT DISTINCT c.id, c.name, c.city, c.state, c.landmark_type,
           c.tradition, c.faith
    FROM churches c
    WHERE c.country='US'
    AND c.faith='Christian'
    {exclusions}
    AND (
        c.name LIKE '%mission board%' OR c.name LIKE '%missions board%'
        OR c.name LIKE '%mission agency%' OR c.name LIKE '%missions agency%'
        OR c.name LIKE '%mission fellow%' OR c.name LIKE '%missions fellow%'
        OR c.name LIKE '%missionary society%' OR c.name LIKE '%missionary fellow%'
        OR c.name LIKE '%world mission%' OR c.name LIKE '%world missions%'
        OR c.name LIKE '%global mission%' OR c.name LIKE '%global missions%'
        OR c.name LIKE '%international mission%' OR c.name LIKE '%international missions%'
        OR c.name LIKE '%frontier mission%' OR c.name LIKE '%frontier missions%'
        OR c.name LIKE '%foreign mission%' OR c.name LIKE '%foreign missions%'
        OR c.name LIKE '%overseas mission%' OR c.name LIKE '%overseas missions%'
        OR c.name LIKE '%gospel mission%' OR c.name LIKE '%gospel missions%'
        OR c.name LIKE '%outreach mission%' OR c.name LIKE '%outreach missions%'
        OR c.name LIKE '%mission aviation%'
        OR c.name LIKE '%sending mission%' OR c.name LIKE '%sending missions%'
        OR c.name LIKE '%mission to %' OR c.name LIKE '%missions to %'
        OR (c.name LIKE '%missions inc%' AND c.landmark_type IN ('other','center','office','headquarters'))
        OR (c.name LIKE '%baptist%mission%' AND c.name NOT LIKE '%church%' AND c.name NOT LIKE '%parish%')
        OR (c.name LIKE '%methodist%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%presbyterian%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%lutheran%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%episcopal%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%pentecostal%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%nazarene%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%menonite%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%evangelical%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%orthodox%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%anglican%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%reformed%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%congregational%mission%' AND c.name NOT LIKE '%church%')
        OR (c.name LIKE '%catholic%mission%' AND c.landmark_type IN ('other','center','office','headquarters'))
        OR (c.name LIKE '%missions%' AND c.landmark_type IN ('center','office','headquarters'))
    )
    ORDER BY c.name
    """

    rows = db.execute(query).fetchall()
    contacts = []
    for r in rows:
        contacts.append({
            'id': r[0], 'name': r[1], 'city': r[2], 'state': r[3],
            'landmark_type': r[4], 'tradition': r[5], 'faith': r[6],
            'email': None, 'website': None, 'phone': None
        })
    return contacts

# ============================================================
# ENRICH WITH CONTACT INFO (batch)
# ============================================================
def enrich_contacts(db, contacts):
    """Batch-load contact info for all contacts."""
    if not contacts:
        return contacts

    ids = [c['id'] for c in contacts]
    placeholders = ','.join('?' for _ in ids)

    rows = db.execute(f"""
        SELECT church_id, contact_type, value FROM church_contact_values
        WHERE church_id IN ({placeholders})
        ORDER BY CASE contact_type WHEN 'email' THEN 1 WHEN 'website' THEN 2 WHEN 'phone' THEN 3 END
    """, ids).fetchall()

    contact_map = {}
    for cid, ct, val in rows:
        if cid not in contact_map:
            contact_map[cid] = {'email': None, 'website': None, 'phone': None}
        if ct == 'email' and not contact_map[cid]['email']:
            contact_map[cid]['email'] = val
        elif ct == 'website' and not contact_map[cid]['website']:
            contact_map[cid]['website'] = val
        elif ct == 'phone' and not contact_map[cid]['phone']:
            contact_map[cid]['phone'] = val

    for c in contacts:
        if c['id'] in contact_map:
            c.update(contact_map[c['id']])

    return contacts

# ============================================================
# PITCH BUILDER
# ============================================================
def build_pitch(contact, stats):
    name = contact['name']
    city = contact['city'] or ''
    state = contact['state'] or ''
    location = f"{city}, {state}" if city and state else (city or state or 'US')

    tradition = contact.get('tradition', '')
    tradition_line = ""
    if tradition and tradition not in ('Christian', 'Protestant'):
        tradition_line = f"\nAs a {tradition} organization, you'd find our tradition-level taxonomy especially useful — we classify 206 distinct traditions, so you can filter to exactly the denominational landscape relevant to your work."

    body = f"""Hi {name} Team,

I'm reaching out because GRID (Global Religious Infrastructure Database) maps every church, mosque, temple, and synagogue worldwide — and we've cross-referenced them against census demographics to reveal where religious infrastructure is actually meeting (or missing) population needs.

Here's what this means for mission planning:

CENSUS × INFRASTRUCTURE — KEY INSIGHTS:

• Church Desert Detection: {stats['church_deserts']:,} US counties with 50K+ population have fewer than 50 churches per 100K residents. Know exactly where the underserved communities are.

• Poverty-Need Overlay: {stats['high_poverty_counties']:,} US counties exceed 20% poverty. Filter by poverty, income, education, and home values to find highest-need/lowest-church areas.

• Language/Ethnic Mapping: {stats['diverse_counties']:,} counties have significant Hispanic/Asian populations. Cross-reference immigrant communities against existing language-specific churches to identify truly "unreached" populations.

• Denominational Gap Analysis: With 206 traditions classified, we can show which denominations are missing from which communities — Catholic parishes per Hispanic-majority tract, Pentecostal churches per Black-majority tract, etc.

• International Deployment: Census joins for {stats['countries_with_census']} countries (ADM1/ADM2 levels). Know the religious infrastructure density before you send a team.{tradition_line}

The database covers {stats['total_churches']:,} worship sites globally ({stats['us_churches']:,} US), with {stats['church_census_links']:,} US churches linked to census tract-level ACS demographics — income, poverty, education, ethnicity, language, and home values for every tract.

I'd love to run a custom analysis for your specific mission fields. What regions or demographics are you currently focused on?

Best,

{SIG}"""

    subject = f"GRID: Census × Church Infrastructure — Mission Planning for {location}"

    return {
        'to': contact['email'],
        'subject': subject,
        'body': body,
        'source': 'missions_census',
        'org': name,
        'church_id': contact['id'],
        'city': city,
        'state': state,
        'tradition': tradition
    }

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 70)
    print("CHRISTIAN MISSIONS OUTREACH — Census × Infrastructure")
    print("=" * 70)

    db = connect()

    # Step 1: Find contacts (single query)
    print("\n[1/4] Discovering mission organizations (single query)...")
    contacts = find_mission_contacts(db)
    print(f"  Found {len(contacts)} unique Christian mission orgs")

    if not contacts:
        print("  No contacts found — check query patterns")
        return

    # Step 2: Batch enrich with contact info
    print("\n[2/4] Batch-enriching with emails/websites/phones...")
    contacts = enrich_contacts(db, contacts)

    with_email = [c for c in contacts if c['email']]
    with_web_only = [c for c in contacts if c['website'] and not c['email']]
    no_contact = [c for c in contacts if not c['email'] and not c['website'] and not c['phone']]

    print(f"  With email: {len(with_email)}")
    print(f"  Website only: {len(with_web_only)}")
    print(f"  No contact: {len(no_contact)}")

    # Step 3: Compute census stats
    print("\n[3/4] Computing census-infrastructure stats...")
    stats = get_census_stats(db)
    print(f"  US counties with demographics: {stats['county_count']:,}")
    print(f"  Church-census tract links: {stats['church_census_links']:,}")
    print(f"  Church deserts (<50/100K pop): {stats['church_deserts']:,}")
    print(f"  High-poverty counties (>20%): {stats['high_poverty_counties']:,}")
    print(f"  Diverse counties (Hisp/Asian): {stats['diverse_counties']:,}")
    print(f"  Countries with census joins: {stats['countries_with_census']}")
    print(f"  Total worship sites: {stats['total_churches']:,}")
    print(f"  US worship sites: {stats['us_churches']:,}")

    # Step 4: Build queue entries
    print("\n[4/4] Building & queueing personalized pitches...")

    # Save all contacts CSV for reference
    with open(CAMPAIGN_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id','name','city','state','landmark_type',
                                                'tradition','email','website','phone'])
        writer.writeheader()
        for c in contacts:
            writer.writerow({k: c.get(k) for k in writer.fieldnames})
    print(f"  Contacts CSV: {CAMPAIGN_FILE} ({len(contacts)} rows)")

    # Queue only those with valid email
    new_queue = []
    skipped = 0
    for c in contacts:
        if not c['email'] or '@' not in str(c['email']):
            skipped += 1
            continue
        entry = build_pitch(c, stats)
        new_queue.append(entry)

    # Append to unified queue
    with open(QUEUE_FILE, 'a', encoding='utf-8') as f:
        for entry in new_queue:
            f.write(json.dumps(entry) + '\n')

    print(f"\n  Queued: {len(new_queue)} emails")
    print(f"  Skipped (no email): {skipped}")
    print(f"  Queue file: {QUEUE_FILE}")

    # Print summary
    if new_queue:
        print(f"\n{'─'*70}")
        print(f"QUEUED ({len(new_queue)}):")
        print(f"{'─'*70}")
        for e in new_queue:
            nm = e['org'][:50]
            loc = f"{e.get('city','')}, {e.get('state','')}" if e.get('city') else ''
            trad = e.get('tradition', '')[:20]
            print(f"  {nm:<50} | {loc:<22} | {trad}")

    # Show website-only orgs that could be manually contacted
    if with_web_only:
        print(f"\n{'─'*70}")
        print(f"WEBSITE-ONLY ({len(with_web_only)}) — manual contact needed:")
        print(f"{'─'*70}")
        for c in with_web_only[:20]:
            nm = c['name'][:50]
            web = (c['website'] or '')[:45]
            loc = f"{c.get('city','')}, {c.get('state','')}" if c.get('city') else ''
            print(f"  {nm:<50} | {loc:<22} | {web}")

    print(f"\n{'─'*70}")
    print("NEXT: Run 'python scripts/outreach/send_unified.py' to start sending")
    print(f"{'─'*70}")

    db.close()

if __name__ == '__main__':
    main()
