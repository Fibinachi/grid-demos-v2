"""
Church Directory Research Catalog
==================================
This script documents the church directory sources found on USAChurches.org.
It creates a comprehensive sorted catalog by denomination and faith tradition.

Data sourced from researching www.usachurches.org structure.
To scrape actual church contacts, run church_directory_scraper.py after
foundations are complete.

Outputs:
  church_denomination_catalog.csv - Sorted by denomination family
"""

import csv
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_CSV = os.path.join(SCRIPT_DIR, "church_denomination_catalog.csv")

# Complete denomination catalog from USAChurches.org research
# Format: (family, denomination, approx_churches, listing_url_pattern)
CATALOG = [
    # ADVENTIST
    ("Adventist", "Advent Christian General Conference", 0, ""),
    ("Adventist", "General Conference of the Church of God (Seventh Day)", 0, ""),
    ("Adventist", "Seventh-day Adventist Church", 0, ""),

    # BAPTIST
    ("Baptist", "Alliance of Baptists", 0, ""),
    ("Baptist", "American Baptist Association", 0, ""),
    ("Baptist", "American Baptist Churches in the USA", 0, ""),
    ("Baptist", "Baptist Bible Fellowship International", 0, ""),
    ("Baptist", "Baptist Missionary Association of America", 0, ""),
    ("Baptist", "Conservative Baptist Association of America", 0, ""),
    ("Baptist", "Converge Worldwide", 0, ""),
    ("Baptist", "Cooperative Baptist Fellowship", 0, ""),
    ("Baptist", "Full Gospel Baptist Church Fellowship", 0, ""),
    ("Baptist", "General Association of General Baptist Churches", 0, ""),
    ("Baptist", "General Association of Regular Baptist Churches", 0, ""),
    ("Baptist", "Independent Baptist", 0, ""),
    ("Baptist", "National Association of Free Will Baptists", 0, ""),
    ("Baptist", "National Baptist Convention of America", 0, ""),
    ("Baptist", "National Baptist Convention, USA", 0, ""),
    ("Baptist", "North American Baptist Conference", 0, ""),
    ("Baptist", "Original Free Will Baptist Convention", 0, ""),
    ("Baptist", "Progressive National Baptist Convention", 0, ""),
    ("Baptist", "Seventh Day Baptist General Conference", 0, ""),
    ("Baptist", "Southern Baptist Convention", 0, ""),

    # BRETHREN
    ("Brethren", "Brethren Church (Ashland, OH)", 0, ""),
    ("Brethren", "Brethren in Christ Church", 0, ""),
    ("Brethren", "Church of the Brethren", 0, ""),
    ("Brethren", "Fellowship of Grace Brethren Churches", 0, ""),
    ("Brethren", "Old German Baptist Brethren", 0, ""),
    ("Brethren", "Plymouth Brethren", 0, ""),

    # CATHOLIC
    ("Catholic", "Reformed Catholic Church", 0, ""),
    ("Catholic", "Roman Catholic Church", 0, ""),

    # CHRISTIAN AND RESTORATIONIST
    ("Christian/Restorationist", "Christian Church (Disciples of Christ)", 0, ""),
    ("Christian/Restorationist", "Christian Churches and Churches of Christ", 0, ""),
    ("Christian/Restorationist", "Christian Union", 0, ""),
    ("Christian/Restorationist", "Churches of Christ", 0, ""),

    # CONGREGATIONAL
    ("Congregational", "Conservative Congregational Christian Conference", 0, ""),
    ("Congregational", "National Association of Congregational Christian Churches", 0, ""),
    ("Congregational", "United Church of Christ", 0, ""),

    # EPISCOPAL AND ANGLICAN  *** KEY TARGET ***
    ("Episcopal/Anglican", "Continuing Anglican", 0, ""),
    ("Episcopal/Anglican", "Episcopal Church (TEC)", 105, "https://www.usachurches.org/christian/episcopal-anglican/episcopal-church/"),
    ("Episcopal/Anglican", "International Communion of the Charismatic Episcopal Church", 0, ""),
    ("Episcopal/Anglican", "Reformed Episcopal Church", 0, ""),

    # FRIENDS (QUAKER)
    ("Friends (Quaker)", "Evangelical Friends Church International", 0, ""),
    ("Friends (Quaker)", "Friends General Conference", 0, ""),
    ("Friends (Quaker)", "Friends United Meeting", 0, ""),
    ("Friends (Quaker)", "Religious Society of Friends (Conservative)", 0, ""),

    # FUNDAMENTALIST AND BIBLE
    ("Fundamentalist/Bible", "Bible Fellowship Church", 0, ""),

    # HOLINESS
    ("Holiness", "Apostolic Overcoming Holy Church of God", 0, ""),
    ("Holiness", "Christ Holy Sanctified Church of America", 0, ""),
    ("Holiness", "Christian and Missionary Alliance", 0, ""),
    ("Holiness", "Church of Christ (Holiness) U.S.A.", 0, ""),
    ("Holiness", "Church of God (Anderson, IN)", 0, ""),
    ("Holiness", "Church of God (Holiness)", 0, ""),
    ("Holiness", "Church of the Nazarene", 0, ""),
    ("Holiness", "Churches of Christ in Christian Union", 0, ""),
    ("Holiness", "International Conservative Holiness Association", 0, ""),
    ("Holiness", "Wesleyan Church", 0, ""),

    # LUTHERAN
    ("Lutheran", "American Association of Lutheran Churches", 0, ""),
    ("Lutheran", "Apostolic Lutheran Church of America", 0, ""),
    ("Lutheran", "Association of Free Lutheran Congregations", 0, ""),
    ("Lutheran", "Church of the Lutheran Brethren of America", 0, ""),
    ("Lutheran", "Church of the Lutheran Confession", 0, ""),
    ("Lutheran", "Evangelical Lutheran Church in America (ELCA)", 0, ""),
    ("Lutheran", "Evangelical Lutheran Conference and Ministerium", 0, ""),
    ("Lutheran", "Lutheran Church--Missouri Synod (LCMS)", 0, ""),
    ("Lutheran", "Lutheran Congregations in Mission for Christ", 0, ""),
    ("Lutheran", "North American Lutheran Church", 0, ""),
    ("Lutheran", "Wisconsin Evangelical Lutheran Synod (WELS)", 0, ""),

    # MENNONITE
    ("Mennonite", "Beachy Amish Mennonite Churches", 0, ""),
    ("Mennonite", "Conservative Mennonite Conference", 0, ""),
    ("Mennonite", "Lancaster Mennonite Conference", 0, ""),
    ("Mennonite", "Mennonite Church USA", 0, ""),
    ("Mennonite", "Old Order Amish Church", 0, ""),

    # METHODIST
    ("Methodist", "African Methodist Episcopal Church (AME)", 0, ""),
    ("Methodist", "African Methodist Episcopal Zion Church (AME Zion)", 0, ""),
    ("Methodist", "African Union First Colored Methodist Protestant Church", 0, ""),
    ("Methodist", "Allegheny Wesleyan Methodist Connection", 0, ""),
    ("Methodist", "Christian Methodist Episcopal Church (CME)", 0, ""),
    ("Methodist", "Congregational Methodist Church", 0, ""),
    ("Methodist", "Evangelical Church of North America", 0, ""),
    ("Methodist", "Evangelical Methodist Church", 0, ""),
    ("Methodist", "Free Methodist Church of North America", 0, ""),
    ("Methodist", "Primitive Methodist Church", 0, ""),
    ("Methodist", "United Methodist Church (UMC)", 0, ""),

    # PENTECOSTAL
    ("Pentecostal", "Assemblies of God", 0, ""),
    ("Pentecostal", "Association of Vineyard Churches", 0, ""),
    ("Pentecostal", "Calvary Chapel", 0, ""),
    ("Pentecostal", "Church of God (Cleveland, TN)", 0, ""),
    ("Pentecostal", "Church of God by Faith, Inc.", 0, ""),
    ("Pentecostal", "Church of God in Christ (COGIC)", 0, ""),
    ("Pentecostal", "Church of God of Prophecy", 0, ""),
    ("Pentecostal", "Church of God of the Mountain Assembly", 0, ""),
    ("Pentecostal", "Congregational Holiness Church", 0, ""),
    ("Pentecostal", "Elim Fellowship", 0, ""),
    ("Pentecostal", "International Church of the Foursquare Gospel", 0, ""),
    ("Pentecostal", "International Pentecostal Church of Christ", 0, ""),
    ("Pentecostal", "International Pentecostal Holiness Church", 0, ""),
    ("Pentecostal", "Open Bible Standard Churches", 0, ""),
    ("Pentecostal", "Pentecostal Assemblies of the World", 0, ""),
    ("Pentecostal", "Pentecostal Church of God", 0, ""),
    ("Pentecostal", "Redeemed Christian Church of God", 0, ""),
    ("Pentecostal", "United Holy Church of America", 0, ""),
    ("Pentecostal", "United Pentecostal Church International", 0, ""),

    # PRESBYTERIAN
    ("Presbyterian", "Associate Reformed Presbyterian Church", 0, ""),
    ("Presbyterian", "Covenant Reformed Presbyterian Church", 0, ""),
    ("Presbyterian", "Cumberland Presbyterian Church", 0, ""),
    ("Presbyterian", "ECO: A Covenant Order of Evangelical Presbyterians", 0, ""),
    ("Presbyterian", "Evangelical Presbyterian Church (EPC)", 0, ""),
    ("Presbyterian", "Free Presbyterian Church of North America", 0, ""),
    ("Presbyterian", "Orthodox Presbyterian Church (OPC)", 0, ""),
    ("Presbyterian", "Presbyterian Church in America (PCA)", 0, ""),
    ("Presbyterian", "Presbyterian Church U.S.A. (PCUSA)", 0, ""),
    ("Presbyterian", "Reformed Presbyterian Church of North America", 0, ""),
    ("Presbyterian", "Westminster Presbyterian Church in the US", 0, ""),

    # REFORMED
    ("Reformed", "Christian Reformed Church in North America (CRC)", 0, ""),
    ("Reformed", "Confederation of Reformed Evangelicals", 0, ""),
    ("Reformed", "Fellowship of Independent Reformed Evangelicals", 0, ""),
    ("Reformed", "Protestant Reformed Churches in America", 0, ""),
    ("Reformed", "Reformed Church in America (RCA)", 0, ""),
    ("Reformed", "United Reformed Churches in North America", 0, ""),

    # ORTHODOX
    ("Orthodox", "Antiochian Orthodox Christian Archdiocese", 0, ""),
    ("Orthodox", "Greek Orthodox Archdiocese of America", 0, ""),
    ("Orthodox", "Orthodox Church in America (OCA)", 0, ""),

    # OTHER (includes Non-Denominational)
    ("Other/Non-Denominational", "Grace Communion International", 0, ""),
    ("Other/Non-Denominational", "Interdenominational", 0, ""),
    ("Other/Non-Denominational", "Metropolitan Community Churches", 0, ""),
    ("Other/Non-Denominational", "Non-Denominational / Independent", 2890, "https://www.usachurches.org/christian/other/non-denominational-independent/"),
    ("Other/Non-Denominational", "Sovereign Grace Ministries", 0, ""),
]

def main():
    # Write the catalog
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        fields = ['family', 'denomination', 'approx_churches', 'listing_url']
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in sorted(CATALOG, key=lambda r: (r[0], r[1])):
            w.writerow({
                'family': row[0],
                'denomination': row[1],
                'approx_churches': row[2],
                'listing_url': row[3]
            })

    # Print summary
    print("\n" + "="*70)
    print("  CHURCH DIRECTORY CATALOG - Sorted by Denomination")
    print("  Source: www.usachurches.org (researched 2026-06-07)")
    print("="*70)
    print("")

    by_family = {}
    for row in CATALOG:
        by_family.setdefault(row[0], []).append(row)

    grand_total = 0
    for family in sorted(by_family.keys()):
        rows = by_family[family]
        fam_total = sum(r[2] for r in rows)
        grand_total += fam_total
        print("  %s" % family)
        print("  " + "-"*len(family))
        for r in sorted(rows, key=lambda x: -x[2]):
            church_str = "Est. %d churches" % r[2] if r[2] > 0 else "Not yet counted"
            print("    %-55s %s" % (r[1][:53], church_str))

        known = sum(1 for r in rows if r[2] > 0)
        if known:
            print("    %-55s %d total counted" % ("", fam_total))
        print("")

    print("  " + "="*50)
    print("  GRAND TOTAL: ~%d+ church listings across %d families" % (grand_total, len(by_family)))
    print("  " + "="*50)
    print("")
    print("  KEY TARGET: Episcopal/Anglican - 105 Episcopal Church (TEC) listings")
    print("  KEY TARGET: Non-Denominational/Independent - 2,890 listings")
    print("  KEY TARGET: All ~100+ denominations available for targeted marketing")
    print("")
    print("  Catalog saved to: %s" % OUTPUT_CSV)

if __name__ == '__main__':
    main()
