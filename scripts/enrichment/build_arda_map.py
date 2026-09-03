
"""Complete church_denom -> ARDA code mapping for all 215 denominations.
Enables county-level elimination matching for unclassified churches.
"""
import sqlite3

conn = sqlite3.connect('churches.db')
c = conn.cursor()

MAP = {
    'Southern Baptist Convention': 'SBC',
    'Roman Catholic Church': 'CATH', 'Byzantine Catholic Church': 'CATH',
    'Maronite Catholic Church': 'CATH', 'Ecumenical Catholic': 'CATH',
    'Liberal Catholic': 'CATH', 'Traditional Catholic': 'CATH',
    'Communion of International Catholic Communities': 'CATH',
    'Society of St. Pius X': 'CATH',
    'Presbyterian Church (U.S.A.)': 'PC', 'Presbyterian Church USA': 'PC',
    'Churches of Christ': 'CHCH', 'Church of Christ (Holiness) U.S.A.': 'CHCH',
    'Churches of Christ in Christian Union': 'CHCH',
    'Church of God (Cleveland, TN)': 'CGCT', 'Church of God (Cleveland)': 'CGCT',
    'Church of God of Prophecy': 'CGAI',
    'Church of God in Christ': 'COGIC',
    'Assemblies of God': 'AGC',
    'Christian Church (Disciples of Christ)': 'CCDC',
    'Christian Churches and Churches of Christ': 'CCCC',
    'United Methodist Church': 'UMC', 'Congregational Methodist Church': 'UMC',
    'Evangelical Methodist Church': 'UMC',
    'Missionary Baptist': 'NMBC', 'National Baptist Convention, USA': 'NMBC',
    'National Baptist Convention': 'NMBC',
    'National Baptist Convention of America': 'NBCA',
    'Progressive National Baptist Convention': 'PNBC',
    'Lutheran Church - Missouri Synod': 'LCMS',
    'Lutheran Church Missouri Synod': 'LCMS', 'Lutheran Church--Missouri Synod': 'LCMS',
    'Non-Denominational / Independent': 'NOND', 'Non-Denominational': 'NOND',
    'Interdenominational': 'NOND', 'Independent Christian Church': 'NOND',
    'Community Church (unspecified)': 'NOND', 'Bible Church (unspecified)': 'NOND',
    'National Association of Free Will Baptists': 'FWB',
    'Original Free Will Baptist Convention': 'FWB', 'Free Will Baptist': 'FWB',
    'Church of the Nazarene': 'NAZ',
    'Orthodox': 'ORTH', 'Eastern Orthodox': 'ORTH',
    'Greek Orthodox Archdiocese of America': 'GRK',
    'Orthodox Church in America': 'OCA',
    'Antiochian Orthodox Christian Archdiocese': 'ORTH',
    'Antiochian Orthodox Christian Archdiocese of North America': 'ORTH',
    'Russian Orthodox': 'ROC', 'Serbian Orthodox Church': 'SERB',
    'Romanian Orthodox Church': 'ROAA', 'Ukrainian Orthodox Church': 'ORTH',
    'Bulgarian Orthodox Church': 'ORTH', 'Coptic Orthodox Church': 'ORTH',
    'Ethiopian Orthodox Tewahedo Church': 'ORTH',
    'Malankara Orthodox Syrian Church': 'ORTH',
    'Armenian Apostolic Church': 'ORTH', 'Other Eastern Orthodox': 'ORTH',
    'Episcopal Church': 'EC', 'Anglican Church': 'EC',
    'Anglican Church in North America': 'EC', 'Continuing Anglican': 'EC',
    'Reformed Episcopal Church': 'EC',
    'Evangelical Lutheran Church in America': 'ELCA',
    'Christian Science (First Church of Christ, Scientist)': 'CCNA',
    'LDS / Mormon': 'LDS', 'The Church of Jesus Christ of Latter-day Saints': 'LDS',
    'Church of Jesus Christ of Latter-day Saints': 'LDS',
    'Foursquare Church': 'FOUR', 'International Church of the Foursquare Gospel': 'FOUR',
    "Jehovah's Witness": 'JW',
    'Seventh-day Adventist Church': 'SDAC', 'Seventh-day Adventist': 'SDAC',
    'Seventh Day Adventist': 'SDAC',
    'Seventh Day Baptist General Conference': 'SDB',
    'General Conference of the Church of God (Seventh Day)': 'SDAC',
    'United Church of Christ': 'UCC',
    'Christian and Missionary Alliance': 'CMA',
    'African Methodist Episcopal Church': 'AME',
    'African Methodist Episcopal Zion Church': 'AMEZ',
    'African Union First Colored Methodist Protestant Church and': 'AMEZ',
    'Free Methodist Church': 'FMC', 'Free Methodist': 'FMC',
    'Free Methodist Church of North America': 'FMC',
    'Calvary Chapel': 'CCNA',
    'Local Spiritual Assembly': 'BAHAI', 'Bahai (General)': 'BAHAI',
    'Bahai Center': 'BAHAI', 'Bahai Temple': 'BAHAI',
    'National Spiritual Assembly': 'BAHAI',
    'Class V Org': 'SCIENTOLOGY', 'Celebrity Centre': 'SCIENTOLOGY',
    'Flag Service Org': 'SCIENTOLOGY',
    'Orthodox Union': 'OJUD',
    'Independent Baptist': 'IBAORB', 'Baptist (unspecified)': 'BAPT', 'Baptist': 'BAPT',
    'Salvation Army': 'SALV',
    'Presbyterian Church in America': 'PCA',
    'Covenant Reformed Presbyterian Church': 'PCA',
    'Reformed Presbyterian Church': 'PCA', 'Reformed Presbyterian': 'PCA',
    'Reformed Presbyterian Church of North America': 'PCA',
    'Free Presbyterian Church of North America': 'PCA',
    'American Baptist Churches USA': 'ABC',
    'American Baptist Churches in the USA': 'ABC', 'American Baptist': 'ABC',
    'American Baptist Association': 'ABC',
    'Mennonite Church USA': 'MENN', 'Mennonite (unspecified)': 'MENN',
    'Mennonite (Other)': 'MENN', 'Mennonite': 'MENN',
    'Mennonite Brethren': 'USMB', 'Conservative Mennonite': 'MENN',
    'Orthodox Presbyterian Church': 'OPC',
    'Evangelical Presbyterian Church': 'EPC',
    'Cumberland Presbyterian': 'CPC',
    'Wisconsin Evangelical Lutheran Synod': 'WELS',
    'Lutheran (unspecified)': 'OTH', 'Lutheran (Other)': 'OTH',
    'Lutheran Congregations in Mission for Christ': 'LCMC',
    'North American Lutheran Church': 'OTH', 'Evangelical Lutheran Synod': 'ELS',
    'American Association of Lutheran Churches': 'OTH',
    'Apostolic Lutheran Church of America': 'OTH',
    'Evangelical Lutheran Conference and Ministerium of North Ame': 'OTH',
    'Church of the Lutheran Brethren of America': 'OTH',
    'Converge Worldwide': 'BGC',
    'Evangelical Free Church of America': 'EFCA',
    'Christian Reformed Church in North America': 'CRC', 'Christian Reformed Church': 'CRC',
    'Reformed Church in America': 'RCA', 'Other (Reformed)': 'RCA',
    'Associate Reformed Presbyterian Church': 'ARP',
    'Wesleyan Church': 'WES', 'Wesleyan': 'WES',
    'Church of the United Brethren in Christ': 'WES',
    'Church of the Brethren': 'BIC', 'Brethren Church': 'BRN',
    'Brethren In Christ of North America': 'BIC', 'Grace Brethren': 'FGC',
    'Fellowship of Grace Brethren Churches': 'FGC',
    'Unitarian Universalist': 'UUA',
    'Conservative Baptist Association of America': 'CBAP',
    'Full Gospel Baptist Church Fellowship': 'FGCAI',
    'Full Gospel Baptist Church Fellowship, International': 'FGCAI',
    'Christian Methodist Episcopal Church': 'CME',
    'Jewish (Chabad)': 'JEW', 'Jewish': 'JEW',
    'Muslim': 'MUS', 'Hindu': 'HINT',
    'Church of God (Anderson)': 'CGGC', 'Church of God (Anderson, IN)': 'CGGC',
    'Church of God': 'CGGC', 'Church of God (Holiness)': 'OTH',
    'Church of God of the Mountain Assembly': 'OTH',
    'Presbyterian (Other)': 'OTH',
    'United Pentecostal Church International': 'UPCI',
    'International Pentecostal Holiness Church': 'IPHC',
    'Pentecostal (unspecified)': 'OTH', 'Pentecostal Assemblies of the World': 'PAW',
    'Pentecostal Church of God': 'OTH', 'Pentecostal Holiness': 'OTH',
    'International Pentecostal Church of Christ': 'OTH',
    'Vineyard Churches': 'VINE', 'Association of Vineyard Churches': 'VINE',
    'Reformed Baptist': 'BAPT', 'Primitive Baptist': 'BAPT',
    'Evangelical Covenant Church': 'ECC', 'Evangelical Covenant': 'ECC',
    'Moravian Church in North America': 'MORV',
    'Religious Society of Friends (Quakers)': 'FRND', 'Quaker/Friends': 'FRND',
    'Community of Christ': 'OTH',
    'Metropolitan Community Churches': 'MCC',
    'Alliance of Baptists': 'BAPT',
    'Baptist Bible Fellowship International': 'BFC',
    'Baptist Missionary Association of America': 'BMA',
    'Bible Fellowship Church': 'BFC',
    'Charismatic Episcopal Church': 'OTH',
    'Christ Holy Sanctified Church of America': 'OTH',
    'Christian Union': 'OTH',
    'Confederation of Refomed Evangelicals': 'OTH',
    'Conservative Congregational Christian Conference': 'CCON',
    'Cooperative Baptist Fellowship': 'BAPT',
    'Elim Fellowship': 'OTH', 'Evangelical Friends International': 'OTH',
    'Fellowship of Evangelical Bible Churches': 'OTH',
    'Fellowship of Evangelical Churches': 'OTH',
    'Fellowship of Independent Reformed Evangelicals': 'OTH',
    'General Association of General Baptist Churches': 'BAPT',
    'General Association of Regular Baptist Churches': 'BAPT',
    'Grace Communion International': 'OTH', 'Independent Fundamentalist': 'OTH',
    'International Communion of the Charismatic Episcopal Church': 'OTH',
    'Mission': 'OTH', 'Missionary Church': 'MCF',
    'National Association of Congregational Christian Churches': 'CCON',
    'North American Baptist Conference': 'NACC',
    'Open Bible Standard Churches': 'OTH',
    'Primitive Methodist': 'OTH',
    'Protestant Reformed Churches in America': 'OTH',
    'Redeemed Christian Church of God': 'OTH', 'Reformed Catholic': 'OTH',
    'Seventh Day Baptist': 'SDB', 'Sovereign Grace Ministries': 'OTH',
    'Support Organization': 'OTH', 'United Free Methodist': 'UFM',
    'United Holy Church of America': 'OTH',
    'United Reformed Churches in North America': 'OTH',
    'Apostolic': 'OTH', 'Apostolic Overcoming Holy Church of God': 'OTH',
    '2022': 'OTH', 'Advent Christian General Conference': 'OTH',
    'Congregational Holiness Church': 'OTH', 'Pilgrim Holiness': 'OTH',
    'Evangelical Church of North America': 'OTH',
    'Primitive Methodist Church in the United States of America': 'OTH',
    'Other Protestant': 'OTH', 'Other Christian': 'OTH',
    'Reformed Catholic Church': 'OTH', 'Polish National Catholic': 'OTH',
}

# Create table
c.execute("""CREATE TABLE IF NOT EXISTS denom_arda_map (
    church_denom TEXT PRIMARY KEY, arda_code TEXT NOT NULL,
    confidence REAL DEFAULT 1.0, mapped_by TEXT DEFAULT 'manual',
    exclude_from_attendance INTEGER DEFAULT 0)""")

inserted = 0
unmapped = []
for denom in sorted(MAP.keys()):
    code = MAP[denom]
    exclude = 1 if code in ('BAHAI', 'SCIENTOLOGY') else 0
    c.execute("INSERT OR REPLACE INTO denom_arda_map VALUES (?,?,1.0,'manual',?)",
              (denom, code, exclude))
    inserted += 1

all_denoms = [r[0] for r in c.execute(
    "SELECT DISTINCT denomination FROM churches WHERE denomination IS NOT NULL AND denomination != ''")]
for d in all_denoms:
    if d not in MAP:
        unmapped.append(d)

conn.commit()

total_with_denom = c.execute("SELECT COUNT(1) FROM churches WHERE denomination IS NOT NULL AND denomination != ''").fetchone()[0]
mapped_churches = c.execute("""SELECT COUNT(1) FROM churches c 
    INNER JOIN denom_arda_map m ON c.denomination = m.church_denom""").fetchone()[0]

print(f"Mapped: {inserted} denominations")
print(f"Unmapped: {len(unmapped)}")
for d in unmapped:
    cnt = c.execute("SELECT COUNT(1) FROM churches WHERE denomination=?", (d,)).fetchone()[0]
    print(f"  {d[:60]:60s} {cnt:,}")
print(f"\nCoverage: {mapped_churches:,} / {total_with_denom:,} ({mapped_churches*100/total_with_denom:.1f}%)")
excluded = c.execute("SELECT COUNT(1) FROM denom_arda_map WHERE exclude_from_attendance=1").fetchone()[0]
print(f"Excluded (Bahai/Scientology): {excluded} denominations")
print(f"\nReady for county-level elimination matching.")
conn.close()
