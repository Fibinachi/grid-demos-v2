import sqlite3
db = sqlite3.connect('churches.db')

# Search for likely person names in the remaining unprocessed pool
# Pattern: two words, both starting with capital, no religious keywords, no org markers
rows = db.execute("""
    SELECT id, name, faith, tradition, landmark_type
    FROM churches
    WHERE (tradition IS NULL OR tradition IN ('Christian','Muslim','Jewish','Hindu','Buddhist','Sikh','Jain','Taoist','Shinto','Bahai','Other'))
      AND name NOT LIKE '% % %'  -- exactly two words
      AND name NOT LIKE '% % % %'
      AND length(name) BETWEEN 6 AND 24
      AND name GLOB '[A-Z]* [A-Z]*'  -- Title Case Two Words
      AND name NOT LIKE '%CHURCH%' AND name NOT LIKE '%MINISTR%'
      AND name NOT LIKE '%TEMPLE%' AND name NOT LIKE '%MOSQUE%'
      AND name NOT LIKE '%CATHEDRAL%' AND name NOT LIKE '%SYNAGOGUE%'
      AND name NOT LIKE '%INC%' AND name NOT LIKE '%LLC%'
      AND name NOT LIKE '%CENTER%' AND name NOT LIKE '%SCHOOL%'
      AND name NOT LIKE '%SAINT%' AND name NOT LIKE '% ST %'
      AND name NOT LIKE '%CHAPEL%' AND name NOT LIKE '%BASILICA%'
      AND name NOT LIKE '%SHRINE%' AND name NOT LIKE '%GURDWARA%'
      AND name NOT LIKE '%MONASTERY%' AND name NOT LIKE '%ABBEY%'
      AND name NOT LIKE '%PAGODA%' AND name NOT LIKE '%STUPA%'
      AND name NOT LIKE '% CATHEDRAL%'
      AND name NOT LIKE 'Q%'  -- exclude Q-IDs
      AND name NOT GLOB '*[0-9]*'  -- no numbers
      AND landmark_type IN ('church', 'other', 'organization', 'unknown')
    LIMIT 25
""").fetchall()

print(f"Person-name candidates still in unprocessed pool ({len(rows)} shown):")
for r in rows:
    print(f'  id={r[0]} name=\"{r[1]}\"  faith={r[2]}  type={r[4]}')

# Also check processed entries for person names
print("\nProcessed entries that were flagged Non-Religious:")
rows2 = db.execute("""
    SELECT c.id, c.name, c.landmark_type, ch.reasoning
    FROM churches c
    JOIN classification_history ch ON c.id = ch.church_id
    WHERE ch.stage='stage1' AND ch.field_name='faith' AND ch.new_val='Non-Religious'
    LIMIT 20
""").fetchall()
for r in rows2:
    print(f'  id={r[0]} name=\"{r[1]}\"  type={r[2]}')
    print(f'    reason: {r[3]}')

db.close()


