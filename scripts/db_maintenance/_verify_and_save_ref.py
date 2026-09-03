"""Verify fixes and save classification reference."""
import sqlite3
conn = sqlite3.connect(r"E:\grid\churches.db")
c = conn.cursor()

# Verify
for lbl, pat in [('New Life', '%new life%'), ('Presbytery', '%presbytery%'), ('Reel Recovery', '%reel recovery%')]:
    c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism' AND LOWER(COALESCE(name,'')) LIKE ?", (pat,))
    print(f"{lbl} in Judaism: {c.fetchone()[0]}")

c.execute("SELECT COUNT(*) FROM churches WHERE faith='Judaism'")
print(f"\nGlobal Judaism: {c.fetchone()[0]:,}")

# Save reference note to repo memory
ref = """# Jewish Site Type Classification (landmark_type)

Applies to all records with `faith='Judaism'` (~25,983 global).

## Site Types

| Type | Count | Description |
|---|---|---|
| **synagogue** | ~19,970 | Worship/prayer — congregations, temples, shuls |
| **chabad_house** | ~2,836 | Chabad-Lubavitch outreach centers |
| **community_center** | ~442 | JCCs, Jewish community centers (not worship) |
| **school** | ~473 | Day schools, Hebrew academies, Gan Israel |
| **kollel** | ~225 | Advanced post-graduate Torah study |
| **yeshiva** | ~165 | Full-time Torah study institutions |
| **hillel** | ~56 | Campus student ministries (not synagogues) |
| **mikveh** | ~100 | Standalone ritual bath facilities |
| **cemetery** | ~37 | Consecrated burial grounds |
| **museum** | ~16 | Jewish museums, Holocaust museums |
| **organization** | ~11 | Federations, B'nai B'rith, etc. |
| **food** | ~6 | Kosher markets, glatt |
| **retail** | ~7 | Judaica shops, seforim stores |
| **senior_home** | ~1 | Jewish nursing homes |
| **other** | ~520 | Trusts, foundations, generic orgs |

## Rules
- Synagogue ≠ yeshiva (worship vs. education)
- Chabad houses are outreach centers (have prayer but primary mission is outreach)
- JCCs = community_center (social/cultural, NOT worship)
- Hillel = campus student ministry (NOT synagogue)
- Mikveh = standalone ritual bath (mikvehs within synagogues are services, not separate records)
- Cemetery = consecrated ground (not a worship facility, but a religious site)

## Not Jewish (moved to Christian during cleanup)
- "New Life *" → Christian/Protestant (Christian ministries)
- "* Presbytery *" → Christian/Presbyterian
- "Reel Recovery" → Christian ministry
- "El Tabernaculo/*" → Christian/Protestant (Spanish Christian)
- "Iglesia/*/Asamblea/*/Cristo/*" → Christian/Protestant

"""
with open('data/jewish_site_classification.md', 'w', encoding='utf-8') as f:
    f.write(ref)

print("\nReference saved to data/jewish_site_classification.md")
conn.close()
