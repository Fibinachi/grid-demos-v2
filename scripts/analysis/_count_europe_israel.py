"""Count remaining Judaism entries in Europe and Israel."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Europe
europe = [
    'AL','Albania','AD','Andorra','AM','Armenia','AT','Austria','AZ','Azerbaijan',
    'BY','Belarus','BE','Belgium','BA','Bosnia','BG','Bulgaria','HR','Croatia',
    'CY','Cyprus','CZ','Czech Republic','DK','Denmark','EE','Estonia',
    'FI','Finland','FR','France','GE','Georgia','DE','Germany','GR','Greece',
    'HU','Hungary','IS','Iceland','IE','Ireland','IT','Italy','XK','Kosovo',
    'LV','Latvia','LI','Liechtenstein','LT','Lithuania','LU','Luxembourg',
    'MT','Malta','MD','Moldova','MC','Monaco','ME','Montenegro','NL','Netherlands',
    'MK','North Macedonia','NO','Norway','PL','Poland','PT','Portugal',
    'RO','Romania','RU','Russia','SM','San Marino','RS','Serbia','SK','Slovakia',
    'SI','Slovenia','ES','Spain','SE','Sweden','CH','Switzerland',
    'TR','Turkey','UA','Ukraine','GB','United Kingdom','VA','Vatican City',
    'GG','Guernsey','JE','Jersey','IM','Isle of Man','GI','Gibraltar',
    # also 'GB-ENG','GB-SCT','GB-WLS','GB-NIR' style codes
    'England','Scotland','Wales','Northern Ireland'
]

# Some countries may overlap with Asia scan - RU, TR, CY, GE, AZ, AM were in Asia
# but we should focus on truly European ones not yet done
# Actually, RU, TR, CY, GE, AZ, AM were already scanned in Asia.
# Let's get the clean list of European countries that weren't in Asia scan.

eu_only = [c for c in europe if c not in (
    'RU','Russia','TR','Turkey','CY','Cyprus','GE','Georgia','AZ','Azerbaijan','AM','Armenia'
)]

ph = ','.join('?' for _ in eu_only)
c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph})", eu_only)
eu_total = c.fetchone()[0]

c.execute(f"SELECT country, COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) GROUP BY country ORDER BY COUNT(*) DESC", eu_only)
print(f"=== Europe ({eu_total:,} entries, excluding RU/TR/CY/GE/AZ/AM already scanned) ===")
for r in c.fetchall():
    print(f"  {r[0]:25s} {r[1]:>6,}")

# By type
c.execute(f"SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) GROUP BY landmark_type ORDER BY COUNT(*) DESC", eu_only)
print(f"\nBy landmark_type:")
for r in c.fetchall():
    marker = "  PROBLEM" if r[0] in ('church','chapel','cathedral','mosque','abbey','shrine','NULL','') else ""
    print(f"  {r[0]:25s} {r[1]:>6,}{marker}")

c.execute(f"SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ({ph}) AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))", eu_only)
print(f"\nProblematic: {c.fetchone()[0]}")

# Israel
c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel')")
il_total = c.fetchone()[0]
c.execute("SELECT COALESCE(landmark_type,'NULL'), COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel') GROUP BY landmark_type ORDER BY COUNT(*) DESC")
print(f"\n=== Israel ({il_total:,} entries) ===")
for r in c.fetchall():
    marker = "  PROBLEM" if r[0] in ('church','chapel','cathedral','mosque','abbey','shrine','NULL','') else ""
    print(f"  {r[0]:25s} {r[1]:>6,}{marker}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND country IN ('IL','Israel') AND (landmark_type IS NULL OR landmark_type IN ('','church','chapel','cathedral','mosque','abbey','shrine'))")
print(f"Problematic: {c.fetchone()[0]}")

print(f"\n\n=== GRAND TOTAL REMAINING ===")
print(f"Europe: {eu_total:,}")
print(f"Israel: {il_total:,}")
print(f"Total:  {eu_total + il_total:,}")

conn.close()
