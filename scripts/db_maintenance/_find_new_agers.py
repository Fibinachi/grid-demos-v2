"""
Find New Age / esoteric spirituality orgs among the unknown IRS Jewish records.

New Age indicators:
  - astara, theosoph*, rosicrucian*, spiritualist*, metaphysical,
  - new age, new thought, unity church*, science of mind, religious science,
  - spiritual center, spiritual growth, spiritual healing, spiritualist,
  - meditation center, energy healing, mystic*, esoteric, occult,
  - anthroposoph*, transcendental meditation, TM center,
  - channeling, psychic, reiki, holistic healing, crystal*, astrology*,
  - ufologist*, ufo, extraterrestrial*, ascended master*, i am activity,
  - eckankar, self-realization, srf, yoga society (when not Hindu temple),
  - swedenborg*, universalist*, unitarian universalist*,
  - wicca*, pagan*, druid*, goddess temple*, earth-based,
  - scientology*, dianetics*
"""
import sqlite3, datetime

DB = 'churches.db'
TS = datetime.datetime.now().isoformat()
conn = sqlite3.connect(DB, timeout=30)
c = conn.cursor()

# ── Find all candidates ──────────────────────────────────────────────────────
new_age_patterns = [
    # Astara
    "%astara%",
    # Theosophical
    "%theosoph%",
    # Rosicrucian
    "%rosicrucian%",
    # Spiritualism / Spiritualist
    "%spiritualist%",
    # New Thought / Unity / Religious Science / Science of Mind
    "%unity church%", "%unity center%", "%religious science%",
    "%science of mind%", "%new thought%",
    # Metaphysical
    "%metaphysical%",
    # Spiritual center / growth / healing (careful: could be Christian)
    "%spiritual center%", "%spiritual awakening%", "%spiritual healing%",
    "%spiritual growth%", "%spiritual living%", "%spiritual life%",
    # Meditation / Mindfulness
    "%meditation center%", "%meditation society%", "%tm center%",
    "%transcendental meditation%",
    # Mystic / Esoteric / Occult
    "%mystic%", "%esoteric%", "%occult%",
    # Energy healing / Reiki / Holistic
    "%energy healing%", "%reiki%", "%holistic healing%",
    "%crystal healing%", "%crystal%",
    # Psychic / Channeling
    "%psychic%", "%channeling%", "%medium%",
    # Anthroposophy
    "%anthroposoph%",
    # Eckankar
    "%eckankar%",
    # Self-Realization Fellowship / SRF / Yogananda
    "%self-realization%", "%self realization%", "%yogananda%",
    # Swedenborgian / Church of the New Jerusalem
    "%swedenborg%", "%new jerusalem%",
    # Unitarian Universalist (not exactly New Age but not Christian either)
    "%unitarian universalist%", "%universalist%",
    # Wicca / Pagan / Druid / Goddess
    "%wicca%", "%pagan%", "%druid%", "%goddess temple%",
    "%earth-based%", "%neopagan%",
    # Scientology / Dianetics
    "%scientology%", "%dianetics%",
    # UFO / Extraterrestrial
    "%ufo%", "%extraterrestrial%",
    # Ascended Masters / I AM Activity
    "%ascended master%", "%i am activity%", "%saint germain foundation%",
    # Astrology
    "%astrology%", "%astrological%",
    # General New Age
    "%new age%", "%new-age%",
    # Light centers (common New Age name pattern)
    "%light center%", "%light of%",  # too broad? let me be more specific
    # Aquarian
    "%aquarian%",
    # Mind-body-spirit
    "%mind body spirit%", "%mind-body-spirit%",
    # Additional: "Center for Spiritual Living" (Religious Science offshoot)
    "%center for spiritual living%",
    # "Spiritual Assembly" = Baha'i (already handled, but double-check)
    # "Agape" spiritual centers
    "%agape international%", "%agape spiritual%",
]

base_where = ("country='US' AND source LIKE 'irs%' AND faith='Jewish'"
              " AND (religion_type IN ('unknown','other') OR religion_type IS NULL)")

found = {}
for pattern in new_age_patterns:
    c.execute(f"""
        SELECT id, name, city, state FROM churches 
        WHERE {base_where} AND LOWER(name) LIKE '{pattern}'
    """)
    for row in c.fetchall():
        if row[0] not in found:
            found[row[0]] = row

print(f"New Age / esoteric candidates found: {len(found)}")
print()

# Show them grouped by rough category
for cid, (rid, name, city, state) in found.items():
    print(f"  {str(name)[:65]:<65} | {str(city or '')[:15]} | {str(state or '')[:4]}")

# ── Apply fixes ──────────────────────────────────────────────────────────────
print(f"\n=== Applying fixes ===")

# Build WHERE for all found IDs
if found:
    ids = list(found.keys())
    # SQLite can't handle huge IN lists, batch if needed
    for i in range(0, len(ids), 500):
        batch = ids[i:i+500]
        placeholders = ','.join(['?'] * len(batch))
        c.execute(f"""
            UPDATE churches SET faith='Other', religion_type='new_age'
            WHERE id IN ({placeholders})
        """, batch)
        print(f"  Fixed batch {i//500 + 1}: {c.rowcount}")

conn.commit()

# ── Log ──────────────────────────────────────────────────────────────────────
c.execute("""
    INSERT INTO provenance_log (source, script_name, started_at, completed_at,
        churches_updated, churches_inserted, fields_populated, status, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('manual', '_find_new_agers.py', TS, TS,
      len(found), 0, 'faith,religion_type', 'completed',
      f'Reclassified {len(found)} New Age/esoteric orgs: faith=Other, religion_type=new_age'))

conn.commit()

print(f"\nTotal reclassified: {len(found)}")
conn.close()
print("Done!")
