"""Scrape Wikipedia US Catholic universities, import into churches."""
import sqlite3, re, time

# Full extraction from Wikipedia page
UNIVERSITIES = [
    # Benedictine
    ("Belmont Abbey College", "Belmont, NC"), ("Benedictine College", "Atchison, KS"),
    ("Benedictine University", "Lisle, IL"), ("College of Saint Benedict", "St. Joseph, MN"),
    ("The College of St. Scholastica", "Duluth, MN"), ("Mount Marty University", "Yankton, SD"),
    ("Saint Anselm College", "Manchester, NH"), ("Saint John's University", "Collegeville, MN"),
    ("Saint Leo University", "St. Leo, FL"), ("Saint Martin's University", "Lacey, WA"),
    ("Saint Vincent College", "Latrobe, PA"), ("University of Mary", "Bismarck, ND"),
    ("Thomas More University", "Crestview Hills, KY"), ("Wimmer Priory and College", "Latrobe, PA"),
    # Christian Brothers / Lasallian
    ("Christian Brothers University", "Memphis, TN"), ("La Salle University", "Philadelphia, PA"),
    ("Lewis University", "Romeoville, IL"), ("Manhattan University", "Riverdale, NY"),
    ("Saint Mary's College of California", "Moraga, CA"), ("Saint Mary's University of Minnesota", "Winona, MN"),
    # Diocesan
    ("Carroll College", "Helena, MT"), ("Catholic International University", "Charles Town, WV"),
    ("Donnelly College", "Kansas City, KS"), ("Gannon University", "Erie, PA"),
    ("Loras College", "Dubuque, IA"), ("Newman University", "Wichita, KS"),
    ("Our Lady of Holy Cross College", "New Orleans, LA"), ("St. Ambrose University", "Davenport, IA"),
    ("St. Thomas University", "Miami Gardens, FL"), ("Seton Hill University", "Greensburg, PA"),
    ("Thomas More College of Liberal Arts", "Merrimack, NH"), ("University of Saint Mary", "Leavenworth, KS"),
    # Dominican
    ("Albertus Magnus College", "New Haven, CT"), ("Aquinas College", "Grand Rapids, MI"),
    ("Aquinas College", "Nashville, TN"), ("Aquinas Institute of Theology", "St. Louis, MO"),
    ("Barry University", "Miami, FL"), ("Dominican University", "River Forest, IL"),
    ("Dominican University of California", "San Rafael, CA"), ("Molloy University", "Rockville Centre, NY"),
    ("Mount Saint Mary College", "Newburgh, NY"), ("Ohio Dominican University", "Columbus, OH"),
    ("Providence College", "Providence, RI"), ("Siena Heights University", "Adrian, MI"),
    ("St. Thomas Aquinas College", "Sparkill, NY"), ("Xavier University of Louisiana", "New Orleans, LA"),
    # Franciscan
    ("Franciscan School of Theology", "Oceanside, CA"), ("Quincy University", "Quincy, IL"),
    ("St. Bonaventure University", "Olean, NY"), ("Siena College", "Loudonville, NY"),
    # Franciscan - Sisters
    ("Alvernia University", "Reading, PA"), ("Alverno College", "Milwaukee, WI"),
    ("Briar Cliff University", "Sioux City, IA"), ("Felician University", "Lodi, NJ"),
    ("Franciscan Missionaries of Our Lady University", "Baton Rouge, LA"),
    ("Hilbert College", "Hamburg, NY"), ("Lourdes University", "Sylvania, OH"),
    ("Madonna University", "Livonia, MI"), ("Marian University", "Indianapolis, IN"),
    ("Neumann University", "Aston, PA"), ("St. Francis College", "Brooklyn, NY"),
    ("University of Saint Francis", "Fort Wayne, IN"), ("Viterbo University", "La Crosse, WI"),
    # Holy Cross
    ("Holy Cross College", "Notre Dame, IN"), ("King's College", "Wilkes-Barre, PA"),
    ("St. Edward's University", "Austin, TX"), ("Saint Mary's College", "Notre Dame, IN"),
    ("Stonehill College", "Easton, MA"), ("University of Holy Cross", "New Orleans, LA"),
    ("University of Notre Dame", "Notre Dame, IN"), ("University of Portland", "Portland, OR"),
    # Jesuit
    ("Boston College", "Chestnut Hill, MA"), ("Canisius University", "Buffalo, NY"),
    ("College of the Holy Cross", "Worcester, MA"), ("Creighton University", "Omaha, NE"),
    ("Fairfield University", "Fairfield, CT"), ("Fordham University", "New York, NY"),
    ("Georgetown University", "Washington, DC"), ("Gonzaga University", "Spokane, WA"),
    ("John Carroll University", "University Heights, OH"), ("Le Moyne College", "Syracuse, NY"),
    ("Loyola Marymount University", "Los Angeles, CA"), ("Loyola University Chicago", "Chicago, IL"),
    ("Loyola University Maryland", "Baltimore, MD"), ("Loyola University New Orleans", "New Orleans, LA"),
    ("Marquette University", "Milwaukee, WI"), ("Regis University", "Denver, CO"),
    ("Rockhurst University", "Kansas City, MO"), ("Saint Joseph's University", "Philadelphia, PA"),
    ("Saint Louis University", "St. Louis, MO"), ("Saint Peter's University", "Jersey City, NJ"),
    ("Santa Clara University", "Santa Clara, CA"), ("Seattle University", "Seattle, WA"),
    ("Spring Hill College", "Mobile, AL"), ("University of Detroit Mercy", "Detroit, MI"),
    ("University of San Francisco", "San Francisco, CA"), ("University of Scranton", "Scranton, PA"),
    ("Xavier University", "Cincinnati, OH"),
    # Marianist
    ("Chaminade University of Honolulu", "Honolulu, HI"), ("University of Dayton", "Dayton, OH"),
    ("St. Mary's University", "San Antonio, TX"),
    # Mercy
    ("Carlow University", "Pittsburgh, PA"), ("College of Saint Mary", "Omaha, NE"),
    ("Georgian Court University", "Lakewood, NJ"), ("Gwynedd Mercy University", "Gwynedd Valley, PA"),
    ("Misericordia University", "Dallas, PA"), ("Mount Aloysius College", "Cresson, PA"),
    ("Saint Joseph's College of Maine", "Standish, ME"), ("Salve Regina University", "Newport, RI"),
    ("Trocaire College", "Buffalo, NY"), ("University of Saint Joseph", "West Hartford, CT"),
    # Norbertine
    ("St. Norbert College", "De Pere, WI"),
    # Oblate
    ("Oblate School of Theology", "San Antonio, TX"),
    # Paulist
    ("Paulist Fathers House of Mission and Studies", "Washington, DC"),
    # Sacred Heart
    ("Sacred Heart Major Seminary", "Detroit, MI"),
    # Salesian
    ("Don Bosco College", "Newton, NJ"), ("Don Bosco Cristo Rey High School and Corporate Work Study Program", "Takoma Park, MD"),
    # Servite
    ("Servite College", "?, IL"),  # unconfirmed
    # Spiritan
    ("Duquesne University of the Holy Spirit", "Pittsburgh, PA"),
    # Sulpician
    ("St. Patrick's Seminary and University", "Menlo Park, CA"),
    ("Theological College", "Washington, DC"),
    # Ursuline
    ("College of New Rochelle", "New Rochelle, NY"), ("Ursuline College", "Pepper Pike, OH"),
    # Vincentian
    ("DePaul University", "Chicago, IL"), ("Niagara University", "Niagara University, NY"),
    ("St. John's University", "New York, NY"),
    # Sisters of Charity
    ("College of Mount Saint Vincent", "New York, NY"), ("Mount St. Joseph University", "Cincinnati, OH"),
    ("Saint Elizabeth University", "Morristown, NJ"), ("Seton Hall University", "South Orange, NJ"),
    ("University of the Incarnate Word", "San Antonio, TX"),
    # Sisters of St. Joseph
    ("Chestnut Hill College", "Philadelphia, PA"), ("Elms College", "Chicopee, MA"),
    ("Fontbonne University", "St. Louis, MO"), ("Regis College", "Weston, MA"),
    ("St. Catherine University", "St. Paul, MN"), ("University of St. Francis", "Joliet, IL"),
    # Other
    ("Assumption University", "Worcester, MA"), ("Augustine Institute", "Greenwood Village, CO"),
    ("Ave Maria University", "Ave Maria, FL"), ("Benedictine College of Florida", "Tampa, FL"),
    ("Cabrini University", "Radnor, PA"), ("Caldwell University", "Caldwell, NJ"),
    ("Calumet College of St. Joseph", "Whiting, IN"), ("Catholic Distance University", "Charles Town, WV"),
    ("Catholic University of America", "Washington, DC"), ("Cristo Rey Jesuit College Preparatory School of Houston", "Houston, TX"),
    ("D'Youville University", "Buffalo, NY"), ("DeSales University", "Center Valley, PA"),
    ("Divine Word College", "Epworth, IA"), ("Emmanuel College", "Boston, MA"),
    ("Franciscan University of Steubenville", "Steubenville, OH"), ("Holy Apostles College and Seminary", "Cromwell, CT"),
    ("Holy Family University", "Philadelphia, PA"), ("Immaculata University", "Immaculata, PA"),
    ("Institute of World Politics", "Washington, DC"), ("John Paul the Great Catholic University", "Escondido, CA"),
    ("La Roche University", "Pittsburgh, PA"), ("Magdalen College of the Liberal Arts", "Warner, NH"),
    ("Marymount University", "Arlington, VA"), ("Marywood University", "Scranton, PA"),
    ("Mercyhurst University", "Erie, PA"), ("Merrimack College", "North Andover, MA"),
    ("Mount St. Mary's University", "Emmitsburg, MD"), ("Nazareth University", "Rochester, NY"),
    ("Notre Dame College", "South Euclid, OH"), ("Notre Dame of Maryland University", "Baltimore, MD"),
    ("Notre Dame Seminary Graduate School of Theology", "New Orleans, LA"),
    ("Our Lady of the Lake University", "San Antonio, TX"), ("Pontifical College Josephinum", "Columbus, OH"),
    ("Rivier University", "Nashua, NH"), ("Rosemont College", "Rosemont, PA"),
    ("Sacred Heart University", "Fairfield, CT"), ("Saint Elizabeth College of Nursing", "Utica, NY"),
    ("Saint Francis University", "Loretto, PA"), ("Saint Gregory the Great Seminary", "Seward, NE"),
    ("Saint Joseph's Seminary", "Yonkers, NY"), ("Saint Mary's College", "South Bend, IN"),
    ("Saint Meinrad Seminary and School of Theology", "St. Meinrad, IN"),
    ("Saint Paul School of Theology", "Leawood, KS"), ("Saint Vincent de Paul Regional Seminary", "Boynton Beach, FL"),
    ("SS. Cyril and Methodius Seminary", "Orchard Lake, MI"), ("St. John Vianney College Seminary", "Miami, FL"),
    ("St. Joseph's Seminary and College", "Yonkers, NY"), ("St. Mary's Seminary and University", "Baltimore, MD"),
    ("St. Mary's University School of Law", "San Antonio, TX"),
    ("University of Dallas", "Irving, TX"), ("University of St. Thomas", "Houston, TX"),
    ("University of St. Thomas", "St. Paul, MN"), ("Villanova University", "Villanova, PA"),
    ("Walsh University", "North Canton, OH"), ("Wyoming Catholic College", "Lander, WY"),
]

print(f"Total universities: {len(UNIVERSITIES)}")

# Import into DB with entity_type = 'catholic_university'
db = sqlite3.connect('E:/grid/churches.db', timeout=30)

# Check existing
existing_names = set(r[0].lower() for r in db.execute(
    "SELECT lower(name) FROM churches WHERE name IN (" + ",".join("?" * len(UNIVERSITIES)) + ")",
    [u[0] for u in UNIVERSITIES]
).fetchall())
print(f"Existing names to skip: {len(existing_names)}")

imported = 0
skipped = 0
for name, location in UNIVERSITIES:
    if name.lower() in existing_names:
        skipped += 1
        continue
    
    # Parse city, state from location
    parts = location.split(",")
    city = parts[0].strip() if parts else ""
    state = parts[1].strip() if len(parts) > 1 else ""
    
    db.execute("""
        INSERT INTO churches (name, city, state, country,
                             source, tradition, faith, landmark_type)
        VALUES (?, ?, ?, 'US', 
                'wikipedia_catholic_uni', 'Catholic', 'Christian', 'university')
    """, (name, city, state))
    imported += 1
    imported += 1

db.commit()
total = db.execute("SELECT COUNT(*) FROM churches WHERE landmark_type = 'university' AND source = 'wikipedia_catholic_uni'").fetchone()[0]
print(f"Imported: {imported}, Skipped: {skipped}")
print(f"Total catholic_university: {total:,}")
db.close()
