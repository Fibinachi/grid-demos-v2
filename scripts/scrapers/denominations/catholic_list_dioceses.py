"""Compile list of US Catholic dioceses with homepages from USCCB data."""
import json

# Each entry: ("Name", "Website")
dioceses = [
    # Alabama
    ("Archdiocese of Mobile", "https://mobarch.org/"),
    ("Diocese of Birmingham", "http://www.bhmdiocese.org/"),
    # Alaska
    ("Archdiocese of Anchorage-Juneau", "http://www.aoaj.org"),
    ("Diocese of Fairbanks", "https://dioceseoffairbanks.org/"),
    # Arizona
    ("Diocese of Phoenix", "http://www.diocesephoenix.org/"),
    ("Diocese of Tucson", "https://diocesetucson.org/"),
    ("Holy Protection of Mary Byzantine Catholic Eparchy of Phoenix", "https://ephx.org/"),
    # Arkansas
    ("Diocese of Little Rock", "http://www.dolr.org/"),
    # California - Latin Rite
    ("Archdiocese of Los Angeles", "https://www.lacatholics.org/"),
    ("Archdiocese of San Francisco", "https://sfarch.org/"),
    ("Diocese of Fresno", "https://www.dioceseoffresno.org/"),
    ("Diocese of Monterey", "https://www.dioceseofmonterey.org/"),
    ("Diocese of Oakland", "https://www.oakdiocese.org/"),
    ("Diocese of Orange", "https://www.rcbo.org/"),
    ("Diocese of Sacramento", "https://www.scd.org/"),
    ("Diocese of San Bernardino", "https://www.sbdiocese.org/"),
    ("Diocese of San Diego", "https://www.sdcatholic.org/"),
    ("Diocese of San Jose", "https://www.dsj.org/"),
    ("Diocese of Santa Rosa", "https://www.srdiocese.org/"),
    ("Diocese of Stockton", "https://stocktondiocese.org/"),
    # California - Eastern Rites
    ("Armenian Catholic Eparchy of Our Lady of Nareg", "http://www.ourladyofnareg.org/"),
    ("Chaldean Catholic Eparchy of St. Peter the Apostle", "https://www.stpeterdiocese.org/"),
    ("Maronite Eparchy of Our Lady of Lebanon", "http://www.eparchy.org/"),
    # Colorado
    ("Archdiocese of Denver", "http://www.archden.org/"),
    ("Diocese of Colorado Springs", "http://www.diocs.org/"),
    ("Diocese of Pueblo", "http://www.dioceseofpueblo.org/"),
    # Connecticut
    ("Archdiocese of Hartford", "http://www.archdioceseofhartford.org/"),
    ("Diocese of Bridgeport", "https://www.bridgeportdiocese.org/"),
    ("Diocese of Norwich", "https://www.norwichdiocese.org/"),
    ("Diocese of Providence", "http://www.dioceseofprovidence.org/"),
    ("Ukrainian Catholic Eparchy of Stamford", "http://www.stamforddio.org/"),
    # Delaware
    ("Diocese of Wilmington", "http://www.cdow.org/"),
    # Florida
    ("Archdiocese of Miami", "http://www.miamiarch.org/"),
    ("Diocese of Orlando", "http://www.orlandodiocese.org/"),
    ("Diocese of Palm Beach", "http://www.diocesepb.org/"),
    ("Diocese of Pensacola-Tallahassee", "https://www.ptdiocese.org/"),
    ("Diocese of St. Augustine", "https://www.dosafl.com/"),
    ("Diocese of St. Petersburg", "https://www.dosp.org/"),
    ("Diocese of Venice", "https://www.dioceseofvenice.org/"),
    # Georgia
    ("Archdiocese of Atlanta", "http://www.archatl.com/"),
    ("Diocese of Savannah", "http://www.diosav.org/"),
    # Hawaii
    ("Diocese of Honolulu", "http://www.catholichawaii.org/"),
    # Idaho
    ("Diocese of Boise", "http://www.catholicidaho.org/"),
    # Illinois
    ("Archdiocese of Chicago", "http://www.archchicago.org/"),
    ("Diocese of Belleville", "https://www.diobelle.org/"),
    ("Diocese of Joliet", "https://www.dioceseofjoliet.org/"),
    ("Diocese of Peoria", "https://www.cdop.org/"),
    ("Diocese of Rockford", "https://www.rockforddiocese.org/"),
    ("Diocese of Springfield in Illinois", "https://www.dio.org/"),
    ("Eparchy of St. Nicholas of Chicago (Ukrainian)", "https://www.chicagougcc.org/"),
    ("Syro-Malabar Diocese of St. Thomas of Chicago", "http://www.stthomasdiocese.org/"),
    # Indiana
    ("Archdiocese of Indianapolis", "http://www.archindy.org/"),
    ("Diocese of Evansville", "https://www.evdio.org/"),
    ("Diocese of Fort Wayne-South Bend", "http://www.diocesefwsb.org"),
    ("Diocese of Gary", "https://www.dcgary.org/"),
    ("Diocese of Lafayette in Indiana", "https://www.dol-in.org/"),
    # Iowa
    ("Archdiocese of Dubuque", "https://www.dbqarch.org/"),
    ("Diocese of Davenport", "http://www.davenportdiocese.org/"),
    ("Diocese of Des Moines", "http://www.dmdiocese.org/"),
    ("Diocese of Sioux City", "https://www.scdiocese.org/"),
    # Kansas
    ("Archdiocese of Kansas City in Kansas", "http://www.archkck.org/"),
    ("Diocese of Dodge City", "http://www.dcdiocese.org/"),
    ("Diocese of Salina", "http://www.salinadiocese.org/"),
    ("Diocese of Wichita", "https://www.cdowk.org/"),
    # Kentucky
    ("Archdiocese of Louisville", "http://www.archlou.org/"),
    ("Diocese of Covington", "http://www.covingtondiocese.org/"),
    ("Diocese of Lexington", "http://www.cdlex.org/"),
    ("Diocese of Knoxville", "http://www.dioknox.org/"),
    ("Diocese of Memphis", "http://www.cdom.org/"),
    ("Diocese of Nashville", "http://www.dioceseofnashville.com/"),
    ("Diocese of Owensboro", "https://www.owensborodiocese.org/"),
    # Louisiana
    ("Archdiocese of New Orleans", "http://www.arch-no.org/"),
    ("Diocese of Alexandria", "http://www.diocesealex.org/"),
    ("Diocese of Baton Rouge", "http://www.diobr.org/"),
    ("Diocese of Houma-Thibodaux", "https://www.htdiocese.org/"),
    ("Diocese of Lafayette in Louisiana", "https://www.diolaf.org/"),
    ("Diocese of Lake Charles", "https://www.dioceseoflc.org/"),
    ("Diocese of Shreveport", "https://www.dioshpt.org/"),
    # Maine
    ("Diocese of Portland in Maine", "http://www.portlanddiocese.net/"),
    # Maryland
    ("Archdiocese of Baltimore", "http://www.archbalt.org/"),
    ("Archdiocese of Washington", "http://www.adw.org/"),
    # Massachusetts
    ("Archdiocese of Boston", "http://www.bostoncatholic.org"),
    ("Diocese of Fall River", "https://www.dfrcc.org/"),
    ("Diocese of Springfield in Massachusetts", "https://www.diospringfield.org/"),
    ("Diocese of Worcester", "https://www.worcesterdiocese.org/"),
    ("Melkite Eparchy of Newton", "https://www.melkite.org/"),
    # Michigan
    ("Archdiocese of Detroit", "https://www.aod.org/"),
    ("Diocese of Gaylord", "https://www.dioceseofgaylord.org/"),
    ("Diocese of Grand Rapids", "https://www.dioceseofgrandrapids.org/"),
    ("Diocese of Kalamazoo", "https://www.dioceseofkalamazoo.org/"),
    ("Diocese of Lansing", "https://www.dioceseoflansing.org/"),
    ("Diocese of Marquette", "https://www.dioceseofmarquette.org/"),
    ("Diocese of Saginaw", "https://www.saginaw.org/"),
    ("Chaldean Eparchy of St. Thomas the Apostle", "https://chaldeanchurch.org/"),
    ("Syriac Catholic Diocese of Our Lady of Deliverance", "http://www.syriaccatholic.us/"),
    # Minnesota
    ("Archdiocese of Saint Paul and Minneapolis", "http://www.archspm.org/"),
    ("Diocese of Crookston", "http://www.crookston.org/"),
    ("Diocese of Duluth", "https://www.dioceseduluth.org/"),
    ("Diocese of New Ulm", "https://www.dnu.org/"),
    ("Diocese of Saint Cloud", "https://www.stcdio.org/"),
    ("Diocese of Winona-Rochester", "https://www.dowr.org/"),
    # Mississippi
    ("Diocese of Biloxi", "http://www.biloxidiocese.org"),
    ("Diocese of Jackson", "http://www.jacksondiocese.org/"),
    # Missouri
    ("Archdiocese of St. Louis", "http://www.archstl.org/"),
    ("Diocese of Jefferson City", "http://www.diojeffcity.org/"),
    ("Diocese of Kansas City-Saint Joseph", "https://www.kcsjcatholic.org/"),
    ("Diocese of Springfield-Cape Girardeau", "https://www.dioscg.org/"),
    # Montana
    ("Diocese of Great Falls-Billings", "http://diocesegfb.org/"),
    ("Diocese of Helena", "http://www.diocesehelena.org/"),
    # Nebraska
    ("Archdiocese of Omaha", "http://www.archomaha.org/"),
    ("Diocese of Grand Island", "http://www.gidiocese.org/"),
    ("Diocese of Lincoln", "http://www.dioceseoflincoln.org/"),
    # Nevada
    ("Archdiocese of Las Vegas", "https://lvcatholic.org/"),
    ("Diocese of Reno", "http://www.dioceseofreno.org/"),
    # New Hampshire
    ("Diocese of Manchester", "http://www.catholicnh.org/"),
    # New Jersey
    ("Archdiocese of Newark", "https://rcan.org/"),
    ("Diocese of Camden", "https://www.camdendiocese.org/"),
    ("Diocese of Metuchen", "https://diometuchen.org/"),
    ("Diocese of Paterson", "https://www.patersondiocese.org/"),
    ("Diocese of Trenton", "https://dioceseoftrenton.org/"),
    ("Byzantine Catholic Eparchy of Passaic", "http://www.eparchyofpassaic.com/"),
    # New Mexico
    ("Archdiocese of Santa Fe", "https://archdiosf.org/"),
    ("Diocese of Gallup", "http://www.dioceseofgallup.org/"),
    ("Diocese of Las Cruces", "http://www.rcdlc.org"),
    # New York
    ("Archdiocese of New York", "http://www.archny.org/"),
    ("Diocese of Albany", "https://www.rcda.org/"),
    ("Diocese of Brooklyn", "https://dioceseofbrooklyn.org/"),
    ("Diocese of Buffalo", "https://www.buffalodiocese.org/"),
    ("Diocese of Ogdensburg", "https://www.rcdony.org/"),
    ("Diocese of Rochester", "https://www.dor.org/"),
    ("Diocese of Rockville Centre", "https://www.drvc.org/"),
    ("Diocese of Syracuse", "https://www.syracusediocese.org/"),
    ("Eparchy of St. Maron of Brooklyn", "http://www.stmaron.org/"),
    ("Syro-Malankara Catholic Eparchy in USA", "http://syromalankarausa.org/"),
    # North Carolina
    ("Diocese of Charlotte", "http://www.charlottediocese.org/"),
    ("Diocese of Raleigh", "http://www.dioceseofraleigh.org/"),
    # North Dakota
    ("Diocese of Bismarck", "http://www.bismarckdiocese.com/"),
    ("Diocese of Fargo", "http://www.fargodiocese.org/"),
    # Ohio
    ("Archdiocese of Cincinnati", "https://www.catholiccincinnati.org/"),
    ("Diocese of Cleveland", "https://www.dioceseofcleveland.org/"),
    ("Diocese of Columbus", "https://www.columbuscatholic.org/"),
    ("Diocese of Steubenville", "https://www.diosteub.org/"),
    ("Diocese of Toledo", "https://www.toledo dioces.org/"),
    ("Diocese of Youngstown", "https://www.doy.org/"),
    ("Byzantine Catholic Eparchy of Parma", "http://www.parma.org/"),
    ("Romanian Catholic Eparchy of St. George in Canton", "http://www.romaniancatholic.org/"),
    ("Ukrainian Catholic Eparchy of St. Josaphat in Parma", "http://www.stjosaphateparchy.com/"),
    # Oklahoma
    ("Archdiocese of Oklahoma City", "http://www.archokc.org/"),
    ("Diocese of Tulsa", "http://www.dioceseoftulsa.org/"),
    # Oregon
    ("Archdiocese of Portland in Oregon", "http://www.archdpdx.org/"),
    ("Diocese of Baker", "http://dioceseofbaker.org/"),
    # Pennsylvania
    ("Archdiocese of Philadelphia", "http://www.archphila.org/"),
    ("Diocese of Allentown", "https://www.allentowndiocese.org/"),
    ("Diocese of Altoona-Johnstown", "https://www.ajdiocese.org/"),
    ("Diocese of Erie", "https://www.eriercd.org/"),
    ("Diocese of Greensburg", "https://www.dioceseofgreensburg.org/"),
    ("Diocese of Harrisburg", "https://www.hbgdiocese.org/"),
    ("Diocese of Pittsburgh", "https://www.diopitt.org/"),
    ("Diocese of Scranton", "https://www.dioceseofscranton.org/"),
    ("Byzantine Catholic Archeparchy of Pittsburgh", "http://www.archeparchy.org/"),
    ("Ukrainian Catholic Archeparchy of Philadelphia", "http://www.ukrarcheparchy.us/"),
    # Rhode Island
    ("Diocese of Providence", "http://www.dioceseofprovidence.org/"),
    # South Carolina
    ("Diocese of Charleston", "https://charlestondiocese.org/"),
    # South Dakota
    ("Diocese of Rapid City", "http://www.rapidcitydiocese.org/"),
    ("Diocese of Sioux Falls", "https://sfcatholic.org/"),
    # Tennessee
    ("Diocese of Knoxville", "http://www.dioknox.org/"),
    ("Diocese of Memphis", "http://www.cdom.org/"),
    ("Diocese of Nashville", "http://www.dioceseofnashville.com/"),
    # Texas
    ("Archdiocese of Galveston-Houston", "http://www.archgh.org"),
    ("Archdiocese of San Antonio", "http://www.archsa.org/"),
    ("Diocese of Amarillo", "https://www.amarillodiocese.org/"),
    ("Diocese of Austin", "https://www.austindiocese.org/"),
    ("Diocese of Beaumont", "https://www.dioceseofbmt.org/"),
    ("Diocese of Brownsville", "https://www.cdob.org/"),
    ("Diocese of Corpus Christi", "https://www.diocesecc.org/"),
    ("Diocese of Dallas", "https://www.cathdal.org/"),
    ("Diocese of El Paso", "https://www.elpasodiocese.org/"),
    ("Diocese of Fort Worth", "https://www.fwdioc.org/"),
    ("Diocese of Laredo", "https://www.dioceseoflaredo.org/"),
    ("Diocese of Lubbock", "https://www.catholiclubbock.org/"),
    ("Diocese of San Angelo", "https://www.sanangelodiocese.org/"),
    ("Diocese of Tyler", "https://www.dioceseoftyler.org/"),
    ("Diocese of Victoria", "https://www.victoriadiocese.org/"),
    # Utah
    ("Diocese of Salt Lake City", "http://www.utahcatholicdiocese.org"),
    # Vermont
    ("Diocese of Burlington", "http://www.vermontcatholic.org/"),
    # Virgin Islands
    ("Diocese of St. Thomas", "http://www.catholicvi.com/"),
    # Virginia
    ("Diocese of Arlington", "http://www.arlingtondiocese.org/"),
    ("Diocese of Richmond", "http://www.richmonddiocese.org/"),
    # Washington
    ("Archdiocese of Seattle", "http://www.seattlearchdiocese.org/"),
    ("Diocese of Spokane", "http://www.dioceseofspokane.org/"),
    ("Diocese of Yakima", "http://www.yakimadiocese.org/"),
    # Washington DC
    ("Archdiocese of the Military Services", "http://www.milarch.org/"),
    ("Archdiocese of Washington", "http://www.adw.org/"),
    # West Virginia
    ("Diocese of Wheeling-Charleston", "http://www.dwc.org/"),
    # Wisconsin
    ("Archdiocese of Milwaukee", "http://www.archmil.org/"),
    ("Diocese of Green Bay", "http://www.gbdioc.org"),
    ("Diocese of La Crosse", "http://www.diolc.org/"),
    ("Diocese of Madison", "https://www.madisondiocese.org/"),
    ("Diocese of Superior", "https://www.catholicdos.org/"),
    # Wyoming
    ("Diocese of Cheyenne", "https://dcwy.org/"),
    # Eastern Catholic Metropolitans
    ("Ukrainian Catholic Archeparchy of Philadelphia", "http://www.ukrarcheparchy.us/"),
    ("Byzantine Catholic Archeparchy of Pittsburgh", "http://www.archeparchy.org/"),
    # Personal Ordinariate
    ("Personal Ordinariate of the Chair of Saint Peter", "https://www.ordinariate.net/"),
    # Territories
    ("Archdiocese of San Juan (Puerto Rico)", "https://www.arquidiocesisdesanjuan.org/"),
    ("Archdiocese of Agaña (Guam)", "https://www.aganaarch.org/"),
    ("Diocese of Chalan Kanoa (Northern Marianas)", "https://www.rcdck.org/"),
    ("Diocese of Samoa-Pago Pago (American Samoa)", "https://www.dioceseofsamoa.org/"),
]

# Remove duplicates while preserving order
seen = set()
unique = []
for d in dioceses:
    key = d[0].lower().strip()
    if key not in seen:
        seen.add(key)
        unique.append(d)

print(f"Total dioceses: {len(unique)}")
print()

# Group by type
archdioceses = [d for d in unique if d[0].startswith("Arch")]
dioceses_list = [d for d in unique if d[0].startswith("Diocese")]
eparchies = [d for d in unique if "Eparchy" in d[0] or "Archeparchy" in d[0]]
other = [d for d in unique if d not in archdioceses and d not in dioceses_list and d not in eparchies]

print(f"Archdioceses: {len(archdioceses)}")
print(f"Dioceses: {len(dioceses_list)}")
print(f"Eparchies: {len(eparchies)}")
print(f"Other: {len(other)}")
print()

print("=" * 80)
print("ALL CATHOLIC DIOCESES IN THE UNITED STATES")
print("=" * 80)

for i, (name, url) in enumerate(unique, 1):
    print(f"{i:3d}. {name:60s} {url}")
