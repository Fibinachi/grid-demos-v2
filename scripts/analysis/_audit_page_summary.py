"""Summarize page-name artifacts in church names."""
from gw_db import connect

db = connect()
c = db.cursor()

# Total records from catholic_diocese_scrape
c.execute("SELECT COUNT(*) FROM churches WHERE source = 'catholic_diocese_scrape'")
total = c.fetchone()[0]

# How many look like news articles / press releases / job postings / social pages
# (not actual church names)
queries = {
    "News article titles (starts with newsy patterns)": """
        SELECT COUNT(*) FROM churches WHERE source = 'catholic_diocese_scrape'
        AND (name LIKE 'POPE %' OR name LIKE 'CATHOLIC CHURCH %' 
             OR name LIKE 'VATICAN %' OR name LIKE 'BISHOP %'
             OR name LIKE 'IS THE CATHOLIC CHURCH%'
             OR name LIKE 'IS THIS%'
             OR name LIKE 'IN % CATHOLIC CHURCH%'
             OR name LIKE 'MAN % CATHOLIC CHURCH%'
             OR name LIKE 'WOMAN % CATHOLIC CHURCH%'
             OR name LIKE 'NEW % CATHOLIC%'
             OR name LIKE 'AFTER % CATHOLIC%'
             OR name LIKE 'LOCAL CATHOLIC%'
             OR name LIKE 'FEAST HIGHLIGHTS%'
             OR name LIKE 'ICYMI%'
             OR name LIKE 'LENTEN%'
             OR name LIKE 'CHRISTMAS%'
             OR name LIKE 'MASSIVE TURNING%'
             OR name LIKE 'MASS TO BE%'
             OR name LIKE 'INDIANA INMATES%'
             OR name LIKE 'IN CENTRAL AFRICA%'
             OR name LIKE 'IGNORING THE POOR%'
             OR name LIKE 'IF YOURE NOT%'
             OR name LIKE 'UKRAINIAN%'
             OR name LIKE 'PUERTO RICO%'
             OR name LIKE 'ONE YEAR OF%'
             OR name LIKE 'MUSLIM FATHER%'
             OR name LIKE 'MARSHFIELD PARK RIDE%'
             OR name LIKE 'MARRYING IN%'
             OR name LIKE 'MASSIVE%'
             OR name LIKE 'MASS AT%'
             OR name LIKE 'LETTER FROM%'
             OR name LIKE 'LEAKED EMAILS%'
             OR name LIKE 'KYIVS%'
             OR name LIKE 'KJZT%'
             OR name LIKE 'KENYAN%'
             OR name LIKE 'JUBILEE YEAR%'
             OR name LIKE 'JOINING CATHOLIC%'
             OR name LIKE 'JEFF CAVINS%'
             OR name LIKE 'ISRAELI POLICE%'
             OR name LIKE 'IN METOO%'
             OR name LIKE 'IN THIS TIKTOK%'
             OR name LIKE 'INDIAS SYRO%'
             OR name LIKE 'INDICATIONS OF%'
             OR name LIKE 'IDEAS GUIDELINES%'
             OR name LIKE 'MADAGASCAR%'
             OR name LIKE 'MARRYING%'
             OR name LIKE 'MARRIAGE RETREAT%'
             OR name LIKE 'MEMPHIS CATHOLIC%'
             OR name LIKE 'KEANY PRODUCE%')
    """,
    "Media advisories / press releases": """
        SELECT COUNT(*) FROM churches WHERE source = 'catholic_diocese_scrape'
        AND (name LIKE 'MEDIA ADVISORY%' OR name LIKE 'MEDIA ALERT%')
    """,
    "Job postings": """
        SELECT COUNT(*) FROM churches WHERE source = 'catholic_diocese_scrape'
        AND (name LIKE '% DIRECTOR %' OR name LIKE '% TECHNICIAN%' 
             OR name LIKE '% ASSISTANT' OR name LIKE '% COORDINATOR%'
             OR name LIKE 'MAINTENANCE%' OR name LIKE 'LITURGY AND MUSIC%'
             OR name LIKE 'LIMITED PART TIME%' OR name LIKE 'LAY ECCLESIAL%')
    """,
    ".html filenames (already identified)": """
        SELECT COUNT(*) FROM churches WHERE source = 'catholic_diocese_scrape'
        AND (name LIKE '%.html' OR name LIKE '%.HTM')
    """,
    "Social page names (PUBLIC/GROUP/MEMORIAL PAGE)": """
        SELECT COUNT(*) FROM churches 
        WHERE name LIKE '%PUBLIC PAGE%' OR name LIKE '%GROUP PAGE%' 
           OR name LIKE '%MEMORIAL PAGE%'
    """,
    "URLs as names": """
        SELECT COUNT(*) FROM churches 
        WHERE name LIKE 'http%' OR name LIKE 'www.%' 
           OR name LIKE 'Https:%' OR name LIKE '%goo.gl/maps%'
    """,
    "Bingo/event/social announcements": """
        SELECT COUNT(*) FROM churches WHERE source = 'catholic_diocese_scrape'
        AND (name LIKE 'BINGO%' OR name LIKE 'JACKPOT BINGO%' 
             OR name LIKE 'ICE CREAM SOCIAL%' OR name LIKE '%BANNER%'
             OR name LIKE 'MASS TIMES%' OR name LIKE 'LOCATOR%'
             OR name LIKE 'INSTITUTIONAL RECORDS%'
             OR name LIKE 'MARRIAGE PREPARATION%')
    """,
    "Random filenames/codes": """
        SELECT COUNT(*) FROM churches WHERE source = 'catholic_diocese_scrape'
        AND (name LIKE 'IMG%' OR name LIKE 'JPII GROUP%' 
             OR name LIKE '%UNSPLASH%' OR name LIKE 'JEN COUSER%')
    """,
    "Self-referential 'THE CATHOLIC CHURCH...' article titles": """
        SELECT COUNT(*) FROM churches WHERE source = 'catholic_diocese_scrape'
        AND name LIKE 'THE CATHOLIC CHURCH%'
        AND name NOT LIKE '%PARISH%' AND name NOT LIKE '%CHURCH OF%'
        AND name NOT LIKE '%CATHEDRAL%'
        AND name NOT LIKE 'THE CATHOLIC CHURCH OF%'
        AND name NOT LIKE 'THE CATHOLIC CHURCH AT%'
    """,
}

print(f"Total records from catholic_diocese_scrape source: {total}")
print()
for label, q in queries.items():
    c.execute(q)
    cnt = c.fetchone()[0]
    print(f"  {label}: {cnt}")

print()
print("=== ALL problematic name patterns counted ===")
all_queries = list(queries.values())
all_union = " UNION ALL ".join(f"SELECT ({q}) AS cnt" for q in all_queries)
c.execute("SELECT SUM(cnt) FROM (" + all_union + ")")
print(f"  Total (may have overlap): {c.fetchone()[0]}")

# Also show a few examples of the most "offensive" ones
print()
print("=== Worst offenders (clearly not church names) ===")
c.execute("""
    SELECT name, COUNT(*) as cnt 
    FROM churches 
    WHERE source = 'catholic_diocese_scrape'
    AND (name LIKE 'IMG%' OR name LIKE 'JPII GROUP%'
         OR name LIKE 'MAINTENANCE%' OR name LIKE 'MEDIA ADVISORY%'
         OR name LIKE 'MAN CHARGED%' OR name LIKE 'MASSIVE TURNING%'
         OR name LIKE 'LEAKED EMAILS%' OR name LIKE 'KENYAN%'
         OR name LIKE 'IS THIS%' OR name LIKE 'IS THE CATHOLIC CHURCH%'
         OR name LIKE 'IF YOURE%' OR name LIKE 'IGNORING%'
         OR name LIKE 'IN METOO%' OR name LIKE 'IN THIS TIKTOK%'
         OR name LIKE 'INDIANA INMATES%' OR name LIKE 'INDIAS SYRO%'
         OR name LIKE 'MADAGASCAR%' OR name LIKE 'MARRYING%'
         OR name LIKE 'JEFF CAVINS%' OR name LIKE 'MEMPHIS%'
         OR name LIKE 'KYIVS%' OR name LIKE 'KJZT%'
         OR name LIKE 'MUSLIM FATHER%' OR name LIKE 'PUERTO RICO%'
         OR name LIKE 'ONE YEAR OF%' OR name LIKE 'FEAST HIGHLIGHTS%'
         OR name LIKE 'NEW GLOBAL INITIATIVE%'
         OR name LIKE 'AFTER CANADA%' OR name LIKE 'LENTEN%'
         OR name LIKE 'MEDIA%' OR name LIKE 'ICONOSTASIS%'
         OR name LIKE 'ICYMI%' OR name LIKE 'IDEAS GUIDELINES%'
         OR name LIKE 'JOINING CATHOLIC%'
         OR name LIKE 'INTERRELIGIOUS DIALOGUE%'
         OR name LIKE 'JACKPOT BINGO%' OR name LIKE 'ICE CREAM SOCIAL%'
         OR name LIKE 'INSTALLATION OF FR%')
    GROUP BY name 
    ORDER BY cnt DESC
    LIMIT 50
""")
for r in c.fetchall():
    print(f"  [{r[1]}] {r[0][:120]}")

print()
print("Done.")
