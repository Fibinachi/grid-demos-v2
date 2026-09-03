"""
Phase 2: Build taxonomy entries for all non-Christian, non-Islam faiths
Creates the 4-level FLTD hierarchy in the taxonomy table.
"""
import sqlite3

db = sqlite3.connect('E:/grid/churches.db')
c = db.cursor()

# Get max existing taxonomy ID
c.execute("SELECT COALESCE(MAX(id), 490) FROM taxonomy")
next_id = c.fetchone()[0] + 1
print(f"Starting taxonomy ID: {next_id}")

def add_taxonomy(name, parent_id=None, full_path=None):
    """Add a taxonomy entry and return its ID."""
    global next_id
    tid = next_id
    next_id += 1
    if parent_id is not None and full_path is None:
        # Build path from parent
        c.execute("SELECT full_path FROM taxonomy WHERE id=?", (parent_id,))
        parent_path = c.fetchone()
        if parent_path:
            full_path = parent_path[0] + '/' + name
        else:
            full_path = name
    elif full_path is None:
        full_path = name
    
    c.execute("INSERT INTO taxonomy (id, parent_id, name, full_path) VALUES (?, ?, ?, ?)",
              (tid, parent_id, name, full_path))
    return tid

# ============ ROOT NODES ============
# Root IDs: Buddhist=1, Christian=2, Hindu=3, Islam=4, Judaism=5, Other=6, Shinto=7
# Let me verify
c.execute("SELECT id, name FROM taxonomy WHERE parent_id IS NULL")
print("Existing roots:")
for r in c.fetchall():
    print(f"  id={r[0]} {r[1]}")

# ============ BUDDHIST FLTD ============
print("\n=== Building Buddhist taxonomy ===")
buddhist_root = 1  # confirmed

mahayana = add_taxonomy('Mahayana', buddhist_root)
theravada = add_taxonomy('Theravada', buddhist_root)
vajrayana = add_taxonomy('Vajrayana', buddhist_root)

# Mahayana traditions
add_taxonomy('Zen', mahayana)
add_taxonomy('Pure Land', mahayana)
add_taxonomy('Nichiren', mahayana)
add_taxonomy('Tiantai/Tendai', mahayana)
add_taxonomy('Huayan/Kegon', mahayana)
add_taxonomy('Chinese Buddhism', mahayana)
add_taxonomy('Korean Buddhism', mahayana)
add_taxonomy('Vietnamese Buddhism', mahayana)
add_taxonomy('Shingon', vajrayana)  # Actually Vajrayana but often counted separately
add_taxonomy('Tibetan Buddhism', vajrayana)
add_taxonomy('Mahayana (general)', mahayana)

# Theravada
add_taxonomy('Theravada (general)', theravada)
add_taxonomy('Thai Forest Tradition', theravada)
add_taxonomy('Vipassana', theravada)

# ============ HINDU FLTD ============
print("=== Building Hindu taxonomy ===")
hindu_root = 3

vaishnavism = add_taxonomy('Vaishnavism', hindu_root)
shaivism = add_taxonomy('Shaivism', hindu_root)
shaktism = add_taxonomy('Shaktism', hindu_root)
smartism = add_taxonomy('Smartism', hindu_root)
hindu_other = add_taxonomy('Other', hindu_root)

# Vaishnava traditions
add_taxonomy('ISKCON', vaishnavism)
add_taxonomy('Swaminarayan', vaishnavism)
add_taxonomy('Gaudiya Vaishnavism', vaishnavism)
add_taxonomy('Sri Vaishnavism', vaishnavism)
add_taxonomy('Brahma Kumaris', vaishnavism)
add_taxonomy('Vaishnavism (general)', vaishnavism)

# Shaiva traditions
add_taxonomy('Lingayat', shaivism)
add_taxonomy('Kashmir Shaivism', shaivism)
add_taxonomy('Shaiva Siddhanta', shaivism)
add_taxonomy('Nath', shaivism)
add_taxonomy('Aghori', shaivism)
add_taxonomy('Shaivism (general)', shaivism)

# Shakta traditions
add_taxonomy('Shaktism (general)', shaktism)
add_taxonomy('Kali', shaktism)
add_taxonomy('Durga', shaktism)

# Other Hindu
add_taxonomy('Reform Hindu', hindu_other)
add_taxonomy('Neo-Hindu', hindu_other)
add_taxonomy('Arya Samaj', hindu_other)

# ============ SHINTO FLTD ============
print("=== Building Shinto taxonomy ===")
shinto_root = 7

shrine_shinto = add_taxonomy('Shrine Shinto', shinto_root)
sect_shinto = add_taxonomy('Sect Shinto', shinto_root)
folk_shinto = add_taxonomy('Folk Shinto', shinto_root)

add_taxonomy('Shrine Shinto (general)', shrine_shinto)
add_taxonomy('Ise Shinto', shrine_shinto)
add_taxonomy('Yoshida Shinto', shrine_shinto)
add_taxonomy('Sect Shinto (general)', sect_shinto)
add_taxonomy('Folk Shinto (general)', folk_shinto)

# ============ JUDAISM FLTD ============
print("=== Building Judaism taxonomy ===")
judaism_root = 5

rabbinic = add_taxonomy('Rabbinic', judaism_root)
karaite = add_taxonomy('Karaite', judaism_root)
judaism_other = add_taxonomy('Other', judaism_root)

# Rabbinic traditions
add_taxonomy('Orthodox', rabbinic)
add_taxonomy('Orthodox (Chabad)', rabbinic)
add_taxonomy('Orthodox (Hasidic)', rabbinic)
add_taxonomy('Orthodox (Modern)', rabbinic)
add_taxonomy('Orthodox (Yeshiva)', rabbinic)
add_taxonomy('Conservative', rabbinic)
add_taxonomy('Reform', rabbinic)
add_taxonomy('Reconstructionist', rabbinic)
add_taxonomy('Sephardic', rabbinic)
add_taxonomy('Mizrahi', rabbinic)
add_taxonomy('Humanistic', rabbinic)
add_taxonomy('Rabbinic (general)', rabbinic)

add_taxonomy('Karaite (general)', karaite)

# ============ SIKH FLTD ============
print("=== Building Sikh taxonomy ===")
# Need a root for Sikh - add under Other? Or as a top-level?
# Let me check what makes sense... The user said "Other is anything but the big 7"
# So Sikh should be under Other
other_root = 6

sikh = add_taxonomy('Sikh', other_root)
add_taxonomy('Khalsa', sikh)
add_taxonomy('Nanakpanthi', sikh)
add_taxonomy('Sikh (general)', sikh)

# ============ BAHÁʼÍ ============
bahai = add_taxonomy('Baháʼí', other_root)
add_taxonomy('Baháʼí (general)', bahai)

# ============ JAIN ============
jain = add_taxonomy('Jain', other_root)
add_taxonomy('Digambara', jain)
add_taxonomy('Svetambara', jain)
add_taxonomy('Jain (general)', jain)

# ============ PAGAN ============
pagan = add_taxonomy('Pagan', other_root)
add_taxonomy('Wicca', pagan)
add_taxonomy('Druidry', pagan)
add_taxonomy('Heathenry', pagan)
add_taxonomy('Pagan (general)', pagan)

# ============ ZOROASTRIAN ============
zoroastrian = add_taxonomy('Zoroastrian', other_root)
add_taxonomy('Parsi', zoroastrian)
add_taxonomy('Zoroastrian (general)', zoroastrian)

# ============ ANIMIST ============
animist = add_taxonomy('Animist', other_root)
add_taxonomy('Animist (general)', animist)

# ============ CONFUCIAN ============
confucian = add_taxonomy('Confucian', other_root)
add_taxonomy('Confucian (general)', confucian)

# ============ OTHER (catch-all) ============
other_catchall = add_taxonomy('Other (catch-all)', other_root)
add_taxonomy('Humanist', other_catchall)
add_taxonomy('New Age', other_catchall)
add_taxonomy('Unclassified', other_catchall)

# ============ TAOIST ============
taoist = add_taxonomy('Taoist', other_root)
add_taxonomy('Zhengyi', taoist)
add_taxonomy('Quanzhen', taoist)
add_taxonomy('Taoist (general)', taoist)

db.commit()
print(f"\nTaxonomy built. Last ID: {next_id - 1}")
db.close()
