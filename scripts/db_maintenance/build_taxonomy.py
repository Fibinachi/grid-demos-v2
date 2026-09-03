"""
Build unified religion taxonomy: faith → tradition → family → denomination
as a single self-referencing table. Migrate churches to use taxonomy_id FK,
drop old free-text columns, create v_churches view.

Big 7 faiths: Christian, Islam, Buddhist, Hindu, Shinto, Jewish, Other
Everything not in those → Other

Usage:
    python scripts/db_maintenance/build_taxonomy.py [--dry-run]
"""

import sys, sqlite3, json
from datetime import datetime
from collections import defaultdict

DRY_RUN = '--dry-run' in sys.argv
DB_PATH = 'E:\\grid\\churches.db'
TRIPLES_PATH = 'data/denom_triples.json'

# ──────────────────────────────────────────────
# The taxonomy: (parent_path, name)
# Each entry's parent is the previous level.
# Faith nodes have parent_id=NULL.
# ──────────────────────────────────────────────
TAXONOMY = [
    # ── Christian ──
    (None, 'Christian'),
    ('Christian', 'Catholic'),
    ('Christian', 'Orthodox'),
    ('Christian', 'Protestant'),
    ('Christian', 'Anglican'),
    ('Christian', 'Latter-day Saints'),
    ('Christian', "Jehovah's Witnesses"),
    ('Christian', 'Christian'),
    ('Christian', 'Protestant'),  # generic protestant bucket

    # Protestant families
    ('Christian/Protestant', 'Baptist'),
    ('Christian/Protestant', 'Methodist'),
    ('Christian/Protestant', 'Presbyterian'),
    ('Christian/Protestant', 'Reformed'),
    ('Christian/Protestant', 'Congregational'),
    ('Christian/Protestant', 'Lutheran'),
    ('Christian/Protestant', 'Pentecostal'),
    ('Christian/Protestant', 'Evangelical'),
    ('Christian/Protestant', 'Non-Denominational'),
    ('Christian/Protestant', 'Adventist'),
    ('Christian/Protestant', 'Churches of Christ'),
    ('Christian/Protestant', 'Holiness'),
    ('Christian/Protestant', 'Anabaptist'),
    ('Christian/Protestant', 'Quaker'),
    ('Christian/Protestant', 'Moravian'),

    # Baptist denominations
    ('Christian/Protestant/Baptist', 'Southern Baptist Convention'),
    ('Christian/Protestant/Baptist', 'American Baptist'),
    ('Christian/Protestant/Baptist', 'American Baptist Churches'),
    ('Christian/Protestant/Baptist', 'American Baptist Churches USA'),
    ('Christian/Protestant/Baptist', 'American Baptist Churches in the USA'),
    ('Christian/Protestant/Baptist', 'Baptist General Convention'),
    ('Christian/Protestant/Baptist', 'Independent Baptist'),
    ('Christian/Protestant/Baptist', 'Primitive Baptist'),
    ('Christian/Protestant/Baptist', 'Free Will Baptist'),
    ('Christian/Protestant/Baptist', 'General Baptist'),
    ('Christian/Protestant/Baptist', 'Missionary Baptist'),
    ('Christian/Protestant/Baptist', 'National Baptist Convention'),
    ('Christian/Protestant/Baptist', 'National Baptist Convention of America'),
    ('Christian/Protestant/Baptist', 'National Baptist Convention, USA'),
    ('Christian/Protestant/Baptist', 'National Baptist'),
    ('Christian/Protestant/Baptist', 'Progressive Baptist'),
    ('Christian/Protestant/Baptist', 'Progressive National Baptist Convention'),
    ('Christian/Protestant/Baptist', 'Baptist Missionary Association'),
    ('Christian/Protestant/Baptist', 'Baptist Missionary Association of America'),
    ('Christian/Protestant/Baptist', 'Seventh Day Baptist'),
    ('Christian/Protestant/Baptist', 'Full Gospel Baptist Church Fellowship'),
    ('Christian/Protestant/Baptist', 'Full Gospel Baptist Church Fellowship, International'),
    ('Christian/Protestant/Baptist', 'General Association of General Baptist Churches'),
    ('Christian/Protestant/Baptist', 'General Association of Regular Baptist Churches'),
    ('Christian/Protestant/Baptist', 'National Association of Free Will Baptists'),
    ('Christian/Protestant/Baptist', 'Alliance of Baptists'),
    ('Christian/Protestant/Baptist', 'American Baptist Association'),
    ('Christian/Protestant/Baptist', 'American Baptist Church'),
    ('Christian/Protestant/Baptist', 'Baptist (unspecified)'),
    ('Christian/Protestant/Baptist', 'Baptist Bible Fellowship International'),
    ('Christian/Protestant/Baptist', 'Conservative Baptist Association of America'),
    ('Christian/Protestant/Baptist', 'Converge Worldwide'),
    ('Christian/Protestant/Baptist', 'Cooperative Baptist Fellowship'),
    ('Christian/Protestant/Baptist', 'North American Baptist Conference'),
    ('Christian/Protestant/Baptist', 'Old Regular Baptist'),
    ('Christian/Protestant/Baptist', 'Original Free Will Baptist Convention'),
    ('Christian/Protestant/Baptist', 'Reformed Baptist'),
    ('Christian/Protestant/Baptist', 'Regular Baptist'),
    ('Christian/Protestant/Baptist', 'Separate Baptist'),
    ('Christian/Protestant/Baptist', 'Southern Baptist'),
    ('Christian/Protestant/Baptist', 'United Baptist'),
    ('Christian/Protestant/Baptist', 'United Free Will Baptist'),
    ('Christian/Protestant/Baptist', 'Baptist'),

    # Methodist denominations
    ('Christian/Protestant/Methodist', 'United Methodist Church'),
    ('Christian/Protestant/Methodist', 'United Methodist'),
    ('Christian/Protestant/Methodist', 'African Methodist Episcopal'),
    ('Christian/Protestant/Methodist', 'African Methodist Episcopal Church'),
    ('Christian/Protestant/Methodist', 'AME'),
    ('Christian/Protestant/Methodist', 'African Methodist Episcopal Zion Church'),
    ('Christian/Protestant/Methodist', 'AME Zion'),
    ('Christian/Protestant/Methodist', 'Christian Methodist Episcopal'),
    ('Christian/Protestant/Methodist', 'Christian Methodist Episcopal Church'),
    ('Christian/Protestant/Methodist', 'Free Methodist'),
    ('Christian/Protestant/Methodist', 'Free Methodist Church'),
    ('Christian/Protestant/Methodist', 'Free Methodist Church of North America'),
    ('Christian/Protestant/Methodist', 'Methodist Episcopal'),
    ('Christian/Protestant/Methodist', 'Evangelical Methodist Church'),
    ('Christian/Protestant/Methodist', 'Congregational Methodist Church'),
    ('Christian/Protestant/Methodist', 'African Union First Colored Methodist Protestant Church and Connection'),
    ('Christian/Protestant/Methodist', 'Wesleyan'),
    ('Christian/Protestant/Methodist', 'Wesleyan Church'),
    ('Christian/Protestant/Methodist', 'Methodist'),

    # Presbyterian denominations
    ('Christian/Protestant/Presbyterian', 'Presbyterian Church (USA)'),
    ('Christian/Protestant/Presbyterian', 'Presbyterian Church (U.S.A.)'),
    ('Christian/Protestant/Presbyterian', 'Presbyterian Church USA'),
    ('Christian/Protestant/Presbyterian', 'Presbyterian Church in America'),
    ('Christian/Protestant/Presbyterian', 'Cumberland Presbyterian'),
    ('Christian/Protestant/Presbyterian', 'Associate Reformed Presbyterian Church'),
    ('Christian/Protestant/Presbyterian', 'Evangelical Presbyterian Church'),
    ('Christian/Protestant/Presbyterian', 'Free Presbyterian Church of North America'),
    ('Christian/Protestant/Presbyterian', 'Orthodox Presbyterian Church'),
    ('Christian/Protestant/Presbyterian', 'Presbyterian (Other)'),
    ('Christian/Protestant/Presbyterian', 'Reformed Presbyterian'),
    ('Christian/Protestant/Presbyterian', 'Reformed Presbyterian Church'),
    ('Christian/Protestant/Presbyterian', 'Reformed Presbyterian Church of North America'),
    ('Christian/Protestant/Presbyterian', 'Presbyterian'),

    # Reformed denominations
    ('Christian/Protestant/Reformed', 'Reformed Church in America'),
    ('Christian/Protestant/Reformed', 'Christian Reformed'),
    ('Christian/Protestant/Reformed', 'Christian Reformed Church'),
    ('Christian/Protestant/Reformed', 'Christian Reformed Church in North America'),
    ('Christian/Protestant/Reformed', 'Netherlands Reformed Congregations'),
    ('Christian/Protestant/Reformed', 'Protestant Reformed Churches'),
    ('Christian/Protestant/Reformed', 'Protestant Reformed Churches in America'),
    ('Christian/Protestant/Reformed', 'United Reformed Churches'),
    ('Christian/Protestant/Reformed', 'United Reformed Churches in North America'),
    ('Christian/Protestant/Reformed', 'Other (Reformed)'),
    ('Christian/Protestant/Reformed', 'Reformed'),

    # Congregational denominations
    ('Christian/Protestant/Congregational', 'United Church of Christ'),
    ('Christian/Protestant/Congregational', 'Congregational Christian Church'),
    ('Christian/Protestant/Congregational', 'Conservative Congregational Christian Conference'),
    ('Christian/Protestant/Congregational', 'Congregational'),
    ('Christian/Protestant/Congregational', 'Evangelical Covenant Church'),
    ('Christian/Protestant/Congregational', 'Evangelical Covenant'),

    # Lutheran denominations
    ('Christian/Protestant/Lutheran', 'Evangelical Lutheran Church in America'),
    ('Christian/Protestant/Lutheran', 'ELCA'),
    ('Christian/Protestant/Lutheran', 'Lutheran (ELCA)'),
    ('Christian/Protestant/Lutheran', 'Lutheran Church Missouri Synod'),
    ('Christian/Protestant/Lutheran', 'Lutheran Church--Missouri Synod'),
    ('Christian/Protestant/Lutheran', 'Lutheran Church - Missouri Synod'),
    ('Christian/Protestant/Lutheran', 'Lutheran (LCMS)'),
    ('Christian/Protestant/Lutheran', 'Missouri Synod'),
    ('Christian/Protestant/Lutheran', 'Wisconsin Evangelical Lutheran Synod'),
    ('Christian/Protestant/Lutheran', 'Wisconsin Synod'),
    ('Christian/Protestant/Lutheran', 'Lutheran (WELS)'),
    ('Christian/Protestant/Lutheran', 'Evangelical Lutheran Synod'),
    ('Christian/Protestant/Lutheran', 'Lutheran (unspecified)'),
    ('Christian/Protestant/Lutheran', 'Lutheran (Other)'),
    ('Christian/Protestant/Lutheran', 'Lutheran Congregations in Mission for Christ'),
    ('Christian/Protestant/Lutheran', 'American Association of Lutheran Churches'),
    ('Christian/Protestant/Lutheran', 'Apostolic Lutheran Church of America'),
    ('Christian/Protestant/Lutheran', 'Association of Free Lutheran Congregations'),
    ('Christian/Protestant/Lutheran', 'Church of the Lutheran Brethren of America'),
    ('Christian/Protestant/Lutheran', 'Church of the Lutheran Confession'),
    ('Christian/Protestant/Lutheran', 'North American Lutheran Church'),
    ('Christian/Protestant/Lutheran', 'Lutheran'),

    # Pentecostal denominations
    ('Christian/Protestant/Pentecostal', 'Assemblies of God'),
    ('Christian/Protestant/Pentecostal', 'Church of God (Cleveland, TN)'),
    ('Christian/Protestant/Pentecostal', 'Church of God (Cleveland)'),
    ('Christian/Protestant/Pentecostal', 'Church of God in Christ'),
    ('Christian/Protestant/Pentecostal', 'COGIC'),
    ('Christian/Protestant/Pentecostal', 'Pentecostal Holiness'),
    ('Christian/Protestant/Pentecostal', 'Foursquare Gospel'),
    ('Christian/Protestant/Pentecostal', 'Foursquare Church'),
    ('Christian/Protestant/Pentecostal', 'International Church of the Foursquare Gospel'),
    ('Christian/Protestant/Pentecostal', 'United Pentecostal'),
    ('Christian/Protestant/Pentecostal', 'United Pentecostal Church'),
    ('Christian/Protestant/Pentecostal', 'United Pentecostal Church International'),
    ('Christian/Protestant/Pentecostal', 'Full Gospel'),
    ('Christian/Protestant/Pentecostal', 'International Pentecostal Holiness Church'),
    ('Christian/Protestant/Pentecostal', 'International Pentecostal Church of Christ'),
    ('Christian/Protestant/Pentecostal', 'Apostolic'),
    ('Christian/Protestant/Pentecostal', 'Apostolic Church'),
    ('Christian/Protestant/Pentecostal', 'Apostolic Faith'),
    ('Christian/Protestant/Pentecostal', 'Open Bible'),
    ('Christian/Protestant/Pentecostal', 'Open Bible Standard Churches'),
    ('Christian/Protestant/Pentecostal', 'Pentecostal Church of God'),
    ('Christian/Protestant/Pentecostal', 'Pentecostal Assemblies'),
    ('Christian/Protestant/Pentecostal', 'Pentecostal Assemblies of the World'),
    ('Christian/Protestant/Pentecostal', 'Pentecostal (unspecified)'),
    ('Christian/Protestant/Pentecostal', 'Latter Rain Pentecostal'),
    ('Christian/Protestant/Pentecostal', 'Church of God of Prophecy'),
    ('Christian/Protestant/Pentecostal', 'Church of God of the Mountain Assembly'),
    ('Christian/Protestant/Pentecostal', 'Church of God (Anderson)'),
    ('Christian/Protestant/Pentecostal', 'Congregational Holiness Church'),
    ('Christian/Protestant/Pentecostal', 'Elim Fellowship'),
    ('Christian/Protestant/Pentecostal', 'Elim Pentecostal'),
    ('Christian/Protestant/Pentecostal', 'Pentecostal Free Will Baptist'),
    ('Christian/Protestant/Pentecostal', 'Redeemed Christian Church of God'),
    ('Christian/Protestant/Pentecostal', 'United Holy Church of America'),
    ('Christian/Protestant/Pentecostal', 'Pentecostal'),

    # Evangelical
    ('Christian/Protestant/Evangelical', 'Evangelical Free Church of America'),
    ('Christian/Protestant/Evangelical', 'Evangelical Church of North America'),
    ('Christian/Protestant/Evangelical', 'Fellowship of Evangelical Bible Churches'),
    ('Christian/Protestant/Evangelical', 'Fellowship of Evangelical Churches'),
    ('Christian/Protestant/Evangelical', 'Confederation of Refomed Evangelicals'),
    ('Christian/Protestant/Evangelical', 'Christian and Missionary Alliance'),
    ('Christian/Protestant/Evangelical', 'Evangelical'),

    # Non-Denominational
    ('Christian/Protestant/Non-Denominational', 'Interdenominational'),
    ('Christian/Protestant/Non-Denominational', 'Non-Denominational / Independent'),
    ('Christian/Protestant/Non-Denominational', 'Non-Denom'),
    ('Christian/Protestant/Non-Denominational', 'Non-Denominational'),

    # Adventist
    ('Christian/Protestant/Adventist', 'Seventh-day Adventist'),
    ('Christian/Protestant/Adventist', 'Seventh-day Adventist Church'),
    ('Christian/Protestant/Adventist', 'Seventh Day Adventist'),
    ('Christian/Protestant/Adventist', 'Advent Christian'),
    ('Christian/Protestant/Adventist', 'Advent Christian General Conference'),
    ('Christian/Protestant/Adventist', 'General Conference of the Church of God (Seventh Day)'),
    ('Christian/Protestant/Adventist', 'United Seventh-Day Brethren'),
    ('Christian/Protestant/Adventist', 'Adventist'),

    # Restoration Movement
    ('Christian/Protestant/Churches of Christ', 'Christian Church (Disciples of Christ)'),
    ('Christian/Protestant/Churches of Christ', 'Christian Churches and Churches of Christ'),
    ('Christian/Protestant/Churches of Christ', 'Christian Church'),
    ('Christian/Protestant/Churches of Christ', 'Independent Christian Church'),
    ('Christian/Protestant/Churches of Christ', 'Church of Christ'),
    ('Christian/Protestant/Churches of Christ', 'Churches of Christ in Christian Union'),
    ('Christian/Protestant/Churches of Christ', 'Disciples of Christ'),
    ('Christian/Protestant/Churches of Christ', 'Churches of Christ'),

    # Holiness
    ('Christian/Protestant/Holiness', 'Church of God (Anderson, IN)'),
    ('Christian/Protestant/Holiness', 'Church of God (Holiness)'),
    ('Christian/Protestant/Holiness', 'Church of God (Mountain Assembly)'),
    ('Christian/Protestant/Holiness', 'Church of the Nazarene'),
    ('Christian/Protestant/Holiness', 'Nazarene'),
    ('Christian/Protestant/Holiness', 'Wesleyan Holiness'),
    ('Christian/Protestant/Holiness', 'Holiness'),

    # Anabaptist
    ('Christian/Protestant/Anabaptist', 'Amish'),
    ('Christian/Protestant/Anabaptist', 'Brethren'),
    ('Christian/Protestant/Anabaptist', 'Brethren Church'),
    ('Christian/Protestant/Anabaptist', 'Brethren In Christ of North America'),
    ('Christian/Protestant/Anabaptist', 'Church of the Brethren'),
    ('Christian/Protestant/Anabaptist', 'Fellowship of Grace Brethren Churches'),
    ('Christian/Protestant/Anabaptist', 'Grace Brethren'),
    ('Christian/Protestant/Anabaptist', 'Mennonite'),
    ('Christian/Protestant/Anabaptist', 'Mennonite (unspecified)'),
    ('Christian/Protestant/Anabaptist', 'Mennonite (Other)'),
    ('Christian/Protestant/Anabaptist', 'Mennonite Brethren'),
    ('Christian/Protestant/Anabaptist', 'Mennonite Church USA'),
    ('Christian/Protestant/Anabaptist', 'Missionary Church'),
    ('Christian/Protestant/Anabaptist', 'Conservative Mennonite'),
    ('Christian/Protestant/Anabaptist', 'Anabaptist'),

    # Quaker
    ('Christian/Protestant/Quaker', 'Society of Friends'),
    ('Christian/Protestant/Quaker', 'Religious Society of Friends (Quakers)'),
    ('Christian/Protestant/Quaker', 'Quaker/Friends'),
    ('Christian/Protestant/Quaker', 'Evangelical Friends International'),
    ('Christian/Protestant/Quaker', 'Friends United Meeting'),
    ('Christian/Protestant/Quaker', 'Quaker'),

    # Anglican
    ('Christian/Anglican', 'Church of England'),
    ('Christian/Anglican', 'Episcopal'),
    ('Christian/Anglican', 'Episcopal Church'),
    ('Christian/Anglican', 'Anglican Church in North America'),
    ('Christian/Anglican', 'Anglican Church of Canada'),
    ('Christian/Anglican', 'Anglican Province of America'),
    ('Christian/Anglican', 'Anglican Church'),
    ('Christian/Anglican', 'Reformed Episcopal Church'),
    ('Christian/Anglican', 'International Communion of the Charismatic Episcopal Church'),
    ('Christian/Anglican', 'Anglican'),

    # Catholic
    ('Christian/Catholic', 'Roman Catholic'),
    ('Christian/Catholic', 'Roman Catholic Church'),
    ('Christian/Catholic', 'Old Catholic'),
    ('Christian/Catholic', 'Eastern Catholic'),
    ('Christian/Catholic', 'Eastern Catholic (Armenian)'),
    ('Christian/Catholic', 'Eastern Catholic (Chaldean)'),
    ('Christian/Catholic', 'Eastern Catholic (Maronite)'),
    ('Christian/Catholic', 'Eastern Catholic (Melkite)'),
    ('Christian/Catholic', 'Eastern Catholic (Syro-Malabar)'),
    ('Christian/Catholic', 'Eastern Catholic (Ukrainian)'),
    ('Christian/Catholic', 'Ukrainian Catholic'),
    ('Christian/Catholic', 'Byzantine Catholic Church'),
    ('Christian/Catholic', 'Maronite Catholic Church'),
    ('Christian/Catholic', 'Independent Catholic'),
    ('Christian/Catholic', 'Polish National Catholic'),
    ('Christian/Catholic', 'Reformed Catholic Church'),
    ('Christian/Catholic', 'Traditional Catholic'),
    ('Christian/Catholic', 'Liberal Catholic'),
    ('Christian/Catholic', 'Ecumenical Catholic'),
    ('Christian/Catholic', 'Communion of International Catholic Communities'),
    ('Christian/Catholic', 'Roman Catholic (Augustinian)'),
    ('Christian/Catholic', 'Roman Catholic (Basilian)'),
    ('Christian/Catholic', 'Roman Catholic (Benedictine)'),
    ('Christian/Catholic', 'Roman Catholic (Capuchin)'),
    ('Christian/Catholic', 'Roman Catholic (Carmelite)'),
    ('Christian/Catholic', 'Roman Catholic (Cistercian)'),
    ('Christian/Catholic', 'Roman Catholic (Dominican)'),
    ('Christian/Catholic', 'Roman Catholic (Franciscan)'),
    ('Christian/Catholic', 'Roman Catholic (Jesuit)'),
    ('Christian/Catholic', 'Roman Catholic (Marianist)'),
    ('Christian/Catholic', 'Roman Catholic (Marist)'),
    ('Christian/Catholic', 'Roman Catholic (Norbertine/Premonstratensian)'),
    ('Christian/Catholic', 'Roman Catholic (Oblate)'),
    ('Christian/Catholic', 'Roman Catholic (Passionist)'),
    ('Christian/Catholic', 'Roman Catholic (Pauline)'),
    ('Christian/Catholic', 'Roman Catholic (Poor Clare)'),
    ('Christian/Catholic', 'Roman Catholic (Redemptorist)'),
    ('Christian/Catholic', 'Roman Catholic (Salesian)'),
    ('Christian/Catholic', 'Roman Catholic (Servite)'),
    ('Christian/Catholic', 'Roman Catholic (Vincentian)'),
    ('Christian/Catholic', 'Society of St. Pius X'),
    ('Christian/Catholic', 'Catholic'),

    # Orthodox
    ('Christian/Orthodox', 'Eastern Orthodox'),
    ('Christian/Orthodox', 'Greek Orthodox'),
    ('Christian/Orthodox', 'Eastern Orthodox (Greek)'),
    ('Christian/Orthodox', 'Russian Orthodox'),
    ('Christian/Orthodox', 'Eastern Orthodox (Russian)'),
    ('Christian/Orthodox', 'Antiochian Orthodox Christian Archdiocese'),
    ('Christian/Orthodox', 'Antiochian Orthodox Christian Archdiocese of North America'),
    ('Christian/Orthodox', 'Eastern Orthodox (Antiochian)'),
    ('Christian/Orthodox', 'Coptic Orthodox'),
    ('Christian/Orthodox', 'Oriental Orthodox (Coptic)'),
    ('Christian/Orthodox', 'Ethiopian Orthodox'),
    ('Christian/Orthodox', 'Oriental Orthodox (Ethiopian)'),
    ('Christian/Orthodox', 'Serbian Orthodox'),
    ('Christian/Orthodox', 'Serbian Orthodox Church'),
    ('Christian/Orthodox', 'Eastern Orthodox (Serbian)'),
    ('Christian/Orthodox', 'Romanian Orthodox'),
    ('Christian/Orthodox', 'Romanian Orthodox Church'),
    ('Christian/Orthodox', 'Eastern Orthodox (Romanian)'),
    ('Christian/Orthodox', 'Bulgarian Orthodox'),
    ('Christian/Orthodox', 'Bulgarian Orthodox Church'),
    ('Christian/Orthodox', 'Eastern Orthodox (Bulgarian)'),
    ('Christian/Orthodox', 'Eastern Orthodox (Georgian)'),
    ('Christian/Orthodox', 'Eastern Orthodox (OCA)'),
    ('Christian/Orthodox', 'Eastern Orthodox (Ukrainian)'),
    ('Christian/Orthodox', 'Ukrainian Orthodox'),
    ('Christian/Orthodox', 'Ukrainian Orthodox Church'),
    ('Christian/Orthodox', 'Oriental Orthodox'),
    ('Christian/Orthodox', 'Oriental Orthodox (Armenian)'),
    ('Christian/Orthodox', 'Oriental Orthodox (Eritrean)'),
    ('Christian/Orthodox', 'Oriental Orthodox (Malankara)'),
    ('Christian/Orthodox', 'Oriental Orthodox (Syriac)'),
    ('Christian/Orthodox', 'Malankara Orthodox Syrian Church'),
    ('Christian/Orthodox', 'Other Eastern Orthodox'),
    ('Christian/Orthodox', 'Orthodox'),

    # LDS
    ('Christian/Latter-day Saints', 'Church of Jesus Christ of Latter-day Saints'),
    ('Christian/Latter-day Saints', 'The Church of Jesus Christ of Latter-day Saints'),
    ('Christian/Latter-day Saints', 'LDS'),
    ('Christian/Latter-day Saints', 'LDS / Mormon'),
    ('Christian/Latter-day Saints', 'Mormon/LDS'),
    ('Christian/Latter-day Saints', 'Latter-day Saints'),
    ('Christian/Latter-day Saints', 'Community of Christ'),

    # Jehovah's Witnesses
    ('Christian/Jehovah\'s Witnesses', "Jehovah's Witnesses"),

    # Christian generic
    ('Christian/Christian', 'Christian'),
    ('Christian/Christian', 'Christianity'),
    ('Christian/Christian', 'Protestant'),
    ('Christian/Christian', 'Church of God'),
    ('Christian/Christian', 'Grace'),
    ('Christian/Christian', 'Grace Communion International'),
    ('Christian/Christian', 'Salvation Army'),
    ('Christian/Christian', 'Universalist'),
    ('Christian/Christian', 'Unitarian Universalist'),
    ('Christian/Christian', 'Unity'),
    ('Christian/Christian', 'Independent Fundamentalist'),
    ('Christian/Christian', 'Fellowship of Independent Reformed Evangelicals'),
    ('Christian/Christian', 'Metropolitan Community Churches'),
    ('Christian/Christian', 'Moravian Church in North America'),
    ('Christian/Christian', 'Calvary'),
    ('Christian/Christian', 'Calvary Chapel'),
    ('Christian/Christian', 'Vineyard'),
    ('Christian/Christian', 'Vineyard Churches'),
    ('Christian/Christian', 'Association of Vineyard Churches'),
    ('Christian/Christian', 'Bible Church (unspecified)'),
    ('Christian/Christian', 'Bible Fellowship Church'),
    ('Christian/Christian', 'Community Church (unspecified)'),
    ('Christian/Christian', 'Sovereign Grace Ministries'),
    ('Christian/Christian', 'Class V Org'),
    ('Christian/Christian', 'Flag Service Org'),
    ('Christian/Christian', 'Celebrity Centre'),
    ('Christian/Christian', 'Trinity'),
    ('Christian/Christian', 'St. John'),
    ('Christian/Christian', 'St. Mark'),
    ('Christian/Christian', 'St. Mary'),
    ('Christian/Christian', 'St. Paul'),
    ('Christian/Christian', 'St. Peter'),
    ('Christian/Christian', 'Christian Science (First Church of Christ, Scientist)'),
    ('Christian/Christian', 'Christ Holy Sanctified Church of America'),
    ('Christian/Christian', 'Christian Union'),
    ('Christian/Christian', 'Church of the United Brethren in Christ'),
    ('Christian/Christian', 'Apostolic Overcoming Holy Church of God'),
    ('Christian/Christian', 'Other Christian'),
    ('Christian/Christian', 'Other Protestant'),

    # ── Islam ──
    (None, 'Islam'),
    ('Islam', 'Sunni'),
    ('Islam', 'Shia'),
    ('Islam', 'Ahmadiyya'),
    ('Islam', 'Ismaili'),
    ('Islam', 'Sufi'),
    ('Islam', 'Other'),
    ('Islam/Sunni', 'Sunni Islam'),
    ('Islam/Sunni', 'Sunni'),
    ('Islam/Sunni', 'Sunni/Salafi'),
    ('Islam/Sunni', 'Sunni/Deobandi'),
    ('Islam/Shia', 'Shia Islam'),
    ('Islam/Shia', 'Shia'),
    ('Islam/Shia', 'Zaydi'),
    ('Islam/Other', 'Ibadhi'),
    ('Islam/Other', 'Nation of Islam'),
    ('Islam/Other', 'Five Percent Nation'),
    ('Islam/Other', 'Moorish Science'),
    ('Islam/Other', 'Muslim'),

    # ── Buddhist ──
    (None, 'Buddhist'),
    ('Buddhist', 'Theravada'),
    ('Buddhist', 'Mahayana'),
    ('Buddhist', 'Vajrayana'),
    ('Buddhist', 'Buddhist'),
    ('Buddhist', 'Buddhism'),
    ('Buddhist/Mahayana', 'Zen'),
    ('Buddhist/Mahayana', 'Pure Land'),
    ('Buddhist/Mahayana', 'Nichiren'),
    ('Buddhist/Mahayana', 'Soka Gakkai'),
    ('Buddhist/Mahayana', 'Tendai'),
    ('Buddhist/Mahayana', 'Korean Buddhism'),
    ('Buddhist/Mahayana', 'Chinese Buddhism'),
    ('Buddhist/Vajrayana', 'Tibetan Buddhist'),
    ('Buddhist/Vajrayana', 'Shingon'),

    # ── Hindu ──
    (None, 'Hindu'),
    ('Hindu', 'Vaishnavism'),
    ('Hindu', 'Shaivism'),
    ('Hindu', 'Shaktism'),
    ('Hindu', 'Smartism'),
    ('Hindu', 'Hindu'),
    ('Hindu', 'Hinduism'),
    ('Hindu/Vaishnavism', 'ISKCON'),

    # ── Shinto ──
    (None, 'Shinto'),
    ('Shinto', 'Shinto'),

    # ── Jewish ──
    (None, 'Judaism'),
    ('Judaism', 'Orthodox'),
    ('Judaism', 'Reform'),
    ('Judaism', 'Conservative'),
    ('Judaism', 'Reconstructionist'),
    ('Judaism', 'Karaite'),
    ('Judaism', 'Other'),
    ('Judaism', 'Judaism'),
    ('Judaism/Orthodox', 'Chabad'),
    ('Judaism/Orthodox', 'Orthodox (Chabad)'),
    ('Judaism/Orthodox', 'Jewish (Chabad)'),
    ('Judaism/Orthodox', 'Hasidic'),
    ('Judaism/Orthodox', 'Orthodox (Hasidic)'),
    ('Judaism/Orthodox', 'Sephardic'),
    ('Judaism/Other', 'Humanistic Judaism'),
    ('Judaism/Other', 'Orthodox Union'),
    ('Judaism/Other', 'Jewish'),

    # Messianic Judaism -> Christian (messianic)
    ('Christian/Christian', 'Messianic Judaism'),

    # ── Other (catch-all for small faiths) ──
    (None, 'Other'),
    ('Other', 'Sikh'),
    ('Other', 'Sikhism'),
    ('Other', 'Taoist'),
    ('Other', 'Taoism'),
    ('Other', 'Chinese Folk'),
    ('Other', 'Bahai'),
    ('Other', 'Baháʼí'),
    ('Other', 'Baháʼí (General)'),
    ('Other', 'Baháʼí Temple'),
    ('Other', 'Local Spiritual Assembly'),
    ('Other', 'National Spiritual Assembly'),
    ('Other', 'Jain'),
    ('Other', 'Jainism'),
    ('Other', 'Zoroastrian'),
    ('Other', 'Confucian'),
    ('Other', 'Pagan'),
    ('Other', 'Animist'),
    ('Other', 'Masonic'),
    ('Other', 'Rastafarian'),
    ('Other', 'Spiral Cult'),
    ('Other', 'Other'),
    ('Other', 'Unknown'),
    ('Other', 'unclassified'),

    # Non-religious under Other
    ('Other', 'Non-religious'),
    ('Other/Non-religious', 'Humanist'),
    ('Other/Non-religious', 'Humanistic Judaism'),
    ('Other/Non-religious', 'Unitarian Universalist'),
    ('Other/Non-religious', 'Ethical Culture'),
    ('Other/Non-religious', 'Secular Humanist'),
    ('Other/Non-religious', 'Atheist'),
    ('Other/Non-religious', 'Agnostic'),
]


def get_db():
    db = sqlite3.connect(DB_PATH, timeout=120)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA busy_timeout=120000")
    db.execute("PRAGMA synchronous=NORMAL")
    db.execute("PRAGMA foreign_keys=OFF")
    return db


def log_provenance(db, script_name, started_at, churches_updated, notes):
    cur = db.cursor()
    now = datetime.now().isoformat()
    cur.execute("""
        INSERT INTO provenance_log
            (source, script_name, started_at, completed_at, churches_updated,
             fields_populated, status, notes)
        VALUES (?, ?, ?, ?, ?, 'taxonomy_id', 'completed', ?)
    """, (script_name, script_name, started_at, now, churches_updated, notes))
    db.commit()


def progress_bar(current, total, label=''):
    if total == 0:
        return
    pct = current * 100 // total
    bar_len = 40
    filled = pct * bar_len // 100
    bar = chr(9608) * filled + chr(9617) * (bar_len - filled)
    print(f'\r  {label} [{bar}] {pct:3d}% ({current:,}/{total:,})', end='', flush=True)
    if current >= total:
        print()


def create_taxonomy_table(db, c):
    """Create taxonomy table and seed from TAXONOMY list."""
    print("\nCreating taxonomy table...", flush=True)
    c.executescript("""
        CREATE TABLE IF NOT EXISTS taxonomy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            parent_id INTEGER REFERENCES taxonomy(id),
            name TEXT NOT NULL,
            full_path TEXT NOT NULL,
            depth INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_taxonomy_path ON taxonomy(full_path);
        CREATE INDEX IF NOT EXISTS idx_taxonomy_parent ON taxonomy(parent_id);
    """)
    db.commit()

    # Build a map of parent_path -> parent_id
    # First pass: insert all nodes
    # Split TAXONOMY entries into levels
    node_map = {}  # full_path -> node_info
    id_map = {}    # full_path -> id

    for parent_path, name in TAXONOMY:
        if parent_path is None:
            full_path = name
            depth = 0
        else:
            full_path = f"{parent_path}/{name}"
            depth = parent_path.count('/') + 1
        node_map[full_path] = {'name': name, 'parent_path': parent_path, 'depth': depth}

    # Insert in depth order
    by_depth = defaultdict(list)
    for fp, info in node_map.items():
        by_depth[info['depth']].append(fp)

    for depth in sorted(by_depth.keys()):
        for fp in sorted(by_depth[depth]):
            info = node_map[fp]
            parent_id = None
            if info['parent_path']:
                parent_id = id_map.get(info['parent_path'])
            # Check if already exists
            existing = c.execute("SELECT id FROM taxonomy WHERE full_path=?", (fp,)).fetchone()
            if existing:
                id_map[fp] = existing[0]
            else:
                c.execute("INSERT INTO taxonomy (parent_id, name, full_path, depth) VALUES (?, ?, ?, ?)",
                          (parent_id, info['name'], fp, info['depth']))
                id_map[fp] = c.lastrowid

    db.commit()
    print(f"  Taxonomy seeded: {len(id_map)} nodes", flush=True)
    return id_map


def build_denom_map(id_map):
    """Build denom_string -> taxonomy_id mapping from TAXONOMY entries."""
    denom_map = {}
    for parent_path, name in TAXONOMY:
        if parent_path is not None:
            full_path = f"{parent_path}/{name}"
            tid = id_map.get(full_path)
            if tid:
                denom_map[name] = tid
    return denom_map


def migrate_churches(db, c, denom_map, id_map):
    """Add taxonomy_id, backfill, drop old columns, create view."""
    cols = [r[1] for r in c.execute("PRAGMA table_info(churches)")]
    has_col = 'taxonomy_id' in cols

    if not has_col:
        print("\nAdding taxonomy_id to churches...", flush=True)
        c.execute("ALTER TABLE churches ADD COLUMN taxonomy_id INTEGER REFERENCES taxonomy(id)")
        db.commit()

    # Count records
    total = c.execute("SELECT COUNT(*) FROM churches").fetchone()[0]
    with_denom = c.execute("SELECT COUNT(*) FROM churches WHERE denomination IS NOT NULL AND denomination != ''").fetchone()[0]

    print(f"  Total records: {total:,}", flush=True)
    print(f"  With denomination: {with_denom:,}", flush=True)

    # Unmapped denominations
    all_denoms = set(r[0] for r in c.execute("SELECT DISTINCT denomination FROM churches WHERE denomination IS NOT NULL AND denomination != ''"))
    mapped_denoms = set(denom_map.keys())
    unmapped = all_denoms - mapped_denoms

    if unmapped:
        print(f"\n  WARNING: {len(unmapped)} unmapped denomination values:", flush=True)
        for d in sorted(unmapped)[:30]:
            cnt = c.execute("SELECT COUNT(*) FROM churches WHERE denomination=?", (d,)).fetchone()[0]
            print(f"    {d[:60]:60s} ({cnt:,} records)", flush=True)

    # Backfill
    print(f"\n  Backfilling taxonomy_id...", flush=True)
    total_backfilled = 0

    # By denomination (batched)
    batch = []
    for denom_str, tax_id in sorted(denom_map.items(), key=lambda x: -c.execute("SELECT COUNT(*) FROM churches WHERE denomination=? AND denomination IS NOT NULL AND denomination != ''", (x[0],)).fetchone()[0]):
        rids = [r[0] for r in c.execute("SELECT rowid FROM churches WHERE denomination=? AND taxonomy_id IS NULL", (denom_str,))]
        for rid in rids:
            batch.append((tax_id, rid))
            if len(batch) >= 5000:
                c.executemany("UPDATE churches SET taxonomy_id=? WHERE rowid=?", batch)
                total_backfilled += len(batch)
                batch = []
                db.commit()
                progress_bar(total_backfilled, total, 'Backfilling')

    if batch:
        c.executemany("UPDATE churches SET taxonomy_id=? WHERE rowid=?", batch)
        total_backfilled += len(batch)
        db.commit()

    progress_bar(total, total, 'Backfilling')

    # Set None/null faith -> 'unclassified' -> Other taxonomy
    print(f"\n  Assigning unclassified records to Other...", flush=True)
    other_id = id_map['Other']
    c.execute("UPDATE churches SET taxonomy_id=? WHERE taxonomy_id IS NULL AND (faith IS NULL OR faith='None' OR faith='' OR faith='unclassified')", (other_id,))
    other_assigned = c.rowcount
    db.commit()
    print(f"    {other_assigned:,} unclassified -> Other", flush=True)

    # Verify
    filled = c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id IS NOT NULL").fetchone()[0]
    remaining = c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id IS NULL").fetchone()[0]
    print(f"  taxonomy_id filled: {filled:,} / {total:,}", flush=True)
    print(f"  Remaining NULL: {remaining:,}", flush=True)

    return total_backfilled + other_assigned


def drop_old_columns_and_create_view(db, c):
    """Drop old faith/tradition/denom columns, create v_churches."""
    cols = [r[1] for r in c.execute("PRAGMA table_info(churches)")]

    # Check SQLite version
    sv = c.execute("SELECT sqlite_version()").fetchone()[0]
    parts = sv.split('.')
    major, minor = int(parts[0]), int(parts[1])
    can_drop = major > 3 or (major == 3 and minor >= 35)

    if can_drop:
        print("\nDropping old free-text columns...", flush=True)
        for col in ['faith', 'faith_tradition', 'denomination']:
            if col in cols:
                c.execute(f"ALTER TABLE churches DROP COLUMN {col}")
                print(f"  Dropped {col}", flush=True)
        db.commit()
    else:
        print(f"\nSQLite {sv} doesn't support DROP COLUMN. Skipping.", flush=True)
        print("  Columns faith, faith_tradition, denomination left in place (deprecated).", flush=True)

    # Create view
    print("\nCreating v_churches view...", flush=True)
    current_cols = [r[1] for r in c.execute("PRAGMA table_info(churches)")]
    view_cols = [f'c.{col}' for col in current_cols if col not in ('taxonomy_id',)]
    view_cols.append(
        "COALESCE(t1.name, 'Other') AS faith"
    )
    view_cols.append(
        "COALESCE(t2.name, 'Unclassified') AS faith_tradition"
    )
    view_cols.append(
        "COALESCE(t3.name, 'Unclassified') AS denomination"
    )

    c.execute("DROP VIEW IF EXISTS v_churches")
    c.execute(f"""
        CREATE VIEW v_churches AS
        SELECT {', '.join(view_cols)}
        FROM churches c
        LEFT JOIN taxonomy t1 ON c.taxonomy_id = t1.id
        LEFT JOIN taxonomy t2 ON t1.parent_id = t2.id
        LEFT JOIN taxonomy t3 ON t2.parent_id = t3.id
    """)
    db.commit()
    print("  v_churches created.", flush=True)

    # Verify view
    test = c.execute("SELECT faith, faith_tradition, denomination FROM v_churches LIMIT 5").fetchall()
    print("  Sample v_churches rows:", flush=True)
    for row in test:
        print(f"    faith={row[0]:20s} trad={row[1]:25s} denom={row[2]}", flush=True)


def main():
    mode = "DRY RUN" if DRY_RUN else "LIVE"
    print(f"=== Build Taxonomy ({mode}) ===", flush=True)
    started_at = datetime.now().isoformat()

    db = get_db()
    c = db.cursor()

    id_map = create_taxonomy_table(db, c)
    denom_map = build_denom_map(id_map)

    if DRY_RUN:
        print(f"\nWould migrate {len(denom_map):,} denomination mappings", flush=True)
        print(f"Taxonomy nodes: {len(id_map)}", flush=True)
    else:
        total_backfilled = migrate_churches(db, c, denom_map, id_map)
        drop_old_columns_and_create_view(db, c)

        note = f'Taxonomy migration: {total_backfilled:,} records assigned'
        log_provenance(db, 'build_taxonomy.py', started_at, total_backfilled, note)
        print(f"\n  Provenance logged.", flush=True)

    print(f"\n{'='*50}", flush=True)
    print(f"Summary ({mode}):", flush=True)
    print(f"  Taxonomy nodes: {len(id_map)}", flush=True)
    print(f"  Denom mappings: {len(denom_map)}", flush=True)
    if not DRY_RUN:
        filled = c.execute("SELECT COUNT(*) FROM churches WHERE taxonomy_id IS NOT NULL").fetchone()[0]
        print(f"  Churches with taxonomy: {filled:,}")
    print(f"{'='*50}", flush=True)

    db.close()


if __name__ == '__main__':
    main()
