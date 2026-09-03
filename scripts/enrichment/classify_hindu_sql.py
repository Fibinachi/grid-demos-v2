"""SQL-based Hindu classifier — handles bulk with rules, leaves edge cases for DeepSeek."""
import sqlite3

DB = r"E:\grid\churches.db"

# Legacy → tradition mapping for valid Hindu legacy values
LEGACY_TO_TRADITION = {
    'Vaishnavism': 'Vaishnavism', 'Shaivism': 'Shaivism', 'Shaktism': 'Shaktism',
    'Smartism': 'Smartism', 'Neo-Hindu': 'Neo-Hindu', 'ISKCON': 'ISKCON',
    'Swaminarayan': 'Swaminarayan', 'Arya Samaj': 'Arya Samaj',
    'Folk Hinduism': 'Folk Hinduism', 'Hindu (general)': 'Hindu (general)',
    'Reform Hindu': 'Neo-Hindu', 'Reform': 'Neo-Hindu',
}

# Country defaults
COUNTRY_DEFAULTS = {
    'IN': 'Hindu (general)', 'ID': 'Balinese Hinduism', 'NP': 'Shaivism',
    'BD': 'Shaktism', 'LK': 'Shaivism', 'MY': 'Shaivism', 'PK': 'Shaivism',
    'FJ': 'Hindu (general)', 'TT': 'Hindu (general)', 'GY': 'Hindu (general)',
    'SR': 'Hindu (general)', 'MU': 'Hindu (general)',
    'US': 'Neo-Hindu', 'GB': 'Neo-Hindu', 'CA': 'Neo-Hindu', 'AU': 'Neo-Hindu',
}

# Name pattern → tradition (strong signals only)
NAME_PATTERNS = [
    ('%iskcon%', 'ISKCON'), ('%hare krishna%', 'ISKCON'),
    ('%swaminarayan%', 'Swaminarayan'), ('%arys samaj%', 'Arya Samaj'),
    ('%ramakrishna%', 'Ramakrishna Mission'), ('%vivekananda%', 'Ramakrishna Mission'),
    ('%shiva%', 'Shaivism'), ('%siva%', 'Shaivism'), ('%linga%', 'Shaivism'),
    ('%nath%', 'Nath'), ('%vishnu%', 'Vaishnavism'), ('%krishna%', 'Vaishnavism'),
    ('%radha%', 'Vaishnavism'), ('%rama%', 'Vaishnavism'), ('%hanuman%', 'Vaishnavism'),
    ('%venkateswara%', 'Vaishnavism'), ('%narayana%', 'Vaishnavism'),
    ('%devi%', 'Shaktism'), ('%durga%', 'Shaktism'), ('%kali%', 'Shaktism'),
    ('%lakshmi%', 'Vaishnavism'), ('%saraswati%', 'Shaktism'),
    ('%ganesh%', 'Hindu (general)'), ('%ganesha%', 'Hindu (general)'),
    ('%murugan%', 'Shaivism'), ('%ayyappan%', 'Shaivism'),
    ('%mandir%', 'Hindu (general)'), ('%hindu%', 'Hindu (general)'),
]

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    
    # ── Step 1: Fix clearly wrong legacy values ──
    c.execute("UPDATE churches SET legacy='', tradition='' WHERE faith='Hindu' AND legacy IN ('Protestant','Rabbinic','Methodist','Orthodox') AND (tradition IS NULL OR tradition='')")
    print(f"Step 1 - Cleared wrong legacy: {c.rowcount:,}")
    
    # ── Step 2: Promote valid legacy to tradition ──
    for legacy, tradition in LEGACY_TO_TRADITION.items():
        c.execute("UPDATE churches SET tradition=? WHERE faith='Hindu' AND legacy=? AND (tradition IS NULL OR tradition='')", (tradition, legacy))
        if c.rowcount:
            print(f"  legacy={legacy} -> tradition={tradition}: {c.rowcount:,}")
    
    # ── Step 3: Name pattern matching ──
    for pattern, tradition in NAME_PATTERNS:
        c.execute("UPDATE churches SET tradition=? WHERE faith='Hindu' AND (tradition IS NULL OR tradition='') AND name LIKE ?", (tradition, pattern))
        if c.rowcount:
            print(f"  pattern='{pattern}' -> {tradition}: {c.rowcount:,}")
    
    # ── Step 4: Country defaults ──
    for country, tradition in COUNTRY_DEFAULTS.items():
        c.execute("UPDATE churches SET tradition=? WHERE faith='Hindu' AND country=? AND (tradition IS NULL OR tradition='')", (tradition, country))
        if c.rowcount:
            print(f"  country={country} -> {tradition}: {c.rowcount:,}")
    
    # ── Step 5: Any remaining? ──
    c.execute("SELECT COUNT(*) FROM churches WHERE faith='Hindu' AND (tradition IS NULL OR tradition='')")
    remaining = c.fetchone()[0]
    print(f"\nRemaining unclassified: {remaining:,}")
    
    if remaining > 0:
        # Show what's left
        c.execute("SELECT country, COUNT(*) FROM churches WHERE faith='Hindu' AND (tradition IS NULL OR tradition='') GROUP BY country ORDER BY COUNT(*) DESC LIMIT 10")
        print("By country:")
        for r in c.fetchall():
            print(f"  {r[0] or 'NULL':15} {r[1]:>6,}")
        
        c.execute("SELECT name FROM churches WHERE faith='Hindu' AND (tradition IS NULL OR tradition='') LIMIT 10")
        print("Sample names:")
        for r in c.fetchall():
            print(f"  {r[0]}")
    
    # Tag remaining as Hindu (general)
    if remaining > 0:
        c.execute("UPDATE churches SET tradition='Hindu (general)' WHERE faith='Hindu' AND (tradition IS NULL OR tradition='')")
        print(f"\nTagged remaining {remaining:,} as Hindu (general)")
    
    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()
