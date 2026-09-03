"""
Extract Catholic university/college → religious order mapping from Wikipedia page.
Imports into churches.db: updates denomination_affiliation with the order name.
"""
import re, sqlite3, json
from datetime import datetime, timezone

# The raw text from the Wikipedia page — manually extracted structure
# Format: ORDER_NAME | ALTERNATE_NAME | [UNIVERSITY, CITY, STATE, SUB_ORDER, STATUS]
# Each entry: (name, city, state, sub_order, status)

# Status: active, formerly_catholic, defunct

DATA = """
Adorers of the Blood of Christ||Newman University|Wichita|Kansas||active
Assumptionists|Augustinians of the Assumption|Assumption University|Worcester|Massachusetts||active
Augustinian|Order of Saint Augustine|Merrimack College|North Andover|Massachusetts||active
Augustinian|Order of Saint Augustine|Villanova University|Villanova|Pennsylvania||active
Basilian|Congregation of St. Basil|University of St. Thomas|Houston|Texas||active
Benedictine|Order of Saint Benedict|Belmont Abbey College|Belmont|North Carolina||active
Benedictine|Order of Saint Benedict|Benedictine College|Atchison|Kansas||active
Benedictine|Order of Saint Benedict|Benedictine University|Lisle|Illinois||active
Benedictine|Order of Saint Benedict|College of Saint Benedict|St. Joseph|Minnesota||active
Benedictine|Order of Saint Benedict|The College of St. Scholastica|Duluth|Minnesota||active
Benedictine|Order of Saint Benedict|Donnelly College|Kansas City|Kansas||active
Benedictine|Order of Saint Benedict|Mount Marty University|Yankton|South Dakota||active
Benedictine|Order of Saint Benedict|Saint Anselm College|Goffstown|New Hampshire||active
Benedictine|Order of Saint Benedict|Saint John's University|Collegeville|Minnesota||active
Benedictine|Order of Saint Benedict|Saint Joseph Seminary College|Saint Benedict|Louisiana||active
Benedictine|Order of Saint Benedict|Saint Leo University|St. Leo|Florida||active
Benedictine|Order of Saint Benedict|Saint Martin's University|Lacey|Washington||active
Benedictine|Order of Saint Benedict|Saint Vincent College|Latrobe|Pennsylvania||active
Benedictine|Order of Saint Benedict|University of Mary|Bismarck|North Dakota||active
Brothers of Christian Instruction||Walsh University|North Canton|Ohio||active
Christian Brothers|Congregation of Christian Brothers|Iona University|New Rochelle|New York||active
Congregation of Sisters of St. Agnes||Marian University|Fond du Lac|Wisconsin||active
De La Salle Christian Brothers|Institute of the Brothers of the Christian Schools|Christian Brothers University|Memphis|Tennessee||active
De La Salle Christian Brothers|Institute of the Brothers of the Christian Schools|La Salle University|Philadelphia|Pennsylvania||active
De La Salle Christian Brothers|Institute of the Brothers of the Christian Schools|Lewis University|Romeoville|Illinois||active
De La Salle Christian Brothers|Institute of the Brothers of the Christian Schools|Manhattan University|Riverdale|New York||active
De La Salle Christian Brothers|Institute of the Brothers of the Christian Schools|Saint Mary's College of California|Moraga|California||active
De La Salle Christian Brothers|Institute of the Brothers of the Christian Schools|Saint Mary's University of Minnesota|Winona|Minnesota||active
Diocesan||Carroll College|Helena|Montana||active
Diocesan||Catholic International University|Charles Town|West Virginia||active
Diocesan||Gannon University|Erie|Pennsylvania||active
Diocesan||Loras College|Dubuque|Iowa||active
Diocesan||Mount St. Mary's University|Emmitsburg|Maryland||active
Diocesan||St. Ambrose University|Davenport|Iowa||active
Diocesan||St. Thomas University|Miami|Florida||active
Diocesan||Seton Hall University|South Orange|New Jersey||active
Diocesan||Thomas More University|Crestview Hills|Kentucky||active
Diocesan||University of Saint Mary of the Lake|Mundelein|Illinois||active
Diocesan||University of St. Thomas|Saint Paul|Minnesota||active
Dominican|Order of Preachers|Albertus Magnus College|New Haven|Connecticut||active
Dominican|Order of Preachers|Aquinas College|Grand Rapids|Michigan||active
Dominican|Order of Preachers|Aquinas College|Nashville|Tennessee||active
Dominican|Order of Preachers|Aquinas Institute of Theology|St. Louis|Missouri||active
Dominican|Order of Preachers|Barry University|Miami|Florida||active
Dominican|Order of Preachers|Bayamon Central University|Bayamon|Puerto Rico||active
Dominican|Order of Preachers|Caldwell University|Caldwell|New Jersey||active
Dominican|Order of Preachers|Dominican School of Philosophy and Theology|Berkeley|California||active
Dominican|Order of Preachers|Dominican University|River Forest|Illinois||active
Dominican|Order of Preachers|Dominican University|Orangeburg|New York||active
Dominican|Order of Preachers|Dominican University of California|San Rafael|California||active
Dominican|Order of Preachers|Edgewood University|Madison|Wisconsin||active
Dominican|Order of Preachers|Molloy University|Rockville Centre|New York||active
Dominican|Order of Preachers|Mount Saint Mary College|Newburgh|New York||active
Dominican|Order of Preachers|Ohio Dominican University|Columbus|Ohio||active
Dominican|Order of Preachers|Providence College|Providence|Rhode Island||active
Dominican|Order of Preachers|St. Thomas Aquinas College|Sparkill|New York||active
Edmundite|Society of Saint Edmund|Saint Michael's College|Colchester|Vermont||active
Franciscan|Order of Friars Minor|Franciscan School of Theology|Oceanside|California||active
Franciscan|Order of Friars Minor|Quincy University|Quincy|Illinois||active
Franciscan|Order of Friars Minor|St. Bonaventure University|Olean|New York||active
Franciscan|Order of Friars Minor|Siena University|Loudonville|New York||active
Franciscan|Third Order of Saint Francis|Alvernia University|Reading|Pennsylvania|Bernardine Sisters of St. Francis|active
Franciscan|Third Order of Saint Francis|Alverno College|Milwaukee|Wisconsin|School Sisters of St. Francis|active
Franciscan|Third Order of Saint Francis|Briar Cliff University|Sioux City|Iowa|Sisters of St. Francis of Dubuque|active
Franciscan|Third Order of Saint Francis|Felician University|Lodi|New Jersey|Felician Sisters|active
Franciscan|Third Order of Saint Francis|Franciscan Missionaries of Our Lady University|Baton Rouge|Louisiana||active
Franciscan|Third Order of Saint Francis|Franciscan University of Steubenville|Steubenville|Ohio|Franciscan Friars of the Third Order Regular|active
Franciscan|Third Order of Saint Francis|Hilbert College|Hamburg|New York|Franciscan Sisters of St. Joseph|active
Franciscan|Third Order of Saint Francis|Madonna University|Livonia|Michigan|Felician Sisters of Livonia|active
Franciscan|Third Order of Saint Francis|Marian University|Indianapolis|Indiana|Sisters of St. Francis Oldenburg|active
Franciscan|Third Order of Saint Francis|Neumann University|Aston|Pennsylvania|Sisters of St. Francis of Philadelphia|active
Franciscan|Third Order of Saint Francis|St. Francis College|Brooklyn Heights|New York|Franciscan Brothers of Brooklyn|active
Franciscan|Third Order of Saint Francis|Saint Francis University|Loretto|Pennsylvania|Franciscan Friars of the Third Order Regular|active
Franciscan|Third Order of Saint Francis|University of Saint Francis|Fort Wayne|Indiana|Sisters of St. Francis of Perpetual Adoration|active
Franciscan|Third Order of Saint Francis|University of St. Francis|Joliet|Illinois|Sisters of St. Francis of Mary Immaculate|active
Franciscan|Third Order of Saint Francis|Villa Maria College|Buffalo|New York|Felician Sisters|active
Franciscan|Third Order of Saint Francis|Viterbo University|La Crosse|Wisconsin|Franciscan Sisters of Perpetual Adoration|active
Grey Nuns||D'Youville University|Buffalo|New York||active
Holy Cross|Congregation of Holy Cross|Holy Cross College|Notre Dame|Indiana||active
Holy Cross|Congregation of Holy Cross|King's College|Wilkes-Barre|Pennsylvania||active
Holy Cross|Congregation of Holy Cross|St. Edward's University|Austin|Texas||active
Holy Cross|Congregation of Holy Cross|Saint Mary's College|Notre Dame|Indiana|Sisters of the Holy Cross|active
Holy Cross|Congregation of Holy Cross|Stonehill College|Easton|Massachusetts||active
Holy Cross|Congregation of Holy Cross|University of Holy Cross|New Orleans|Louisiana||active
Holy Cross|Congregation of Holy Cross|University of Notre Dame|Notre Dame|Indiana||active
Holy Cross|Congregation of Holy Cross|University of Portland|Portland|Oregon||active
Jesuit|Society of Jesus|Boston College|Chestnut Hill|Massachusetts||active
Jesuit|Society of Jesus|Canisius University|Buffalo|New York||active
Jesuit|Society of Jesus|College of the Holy Cross|Worcester|Massachusetts||active
Jesuit|Society of Jesus|Creighton University|Omaha|Nebraska||active
Jesuit|Society of Jesus|Fairfield University|Fairfield|Connecticut||active
Jesuit|Society of Jesus|Fordham University|Bronx|New York||active
Jesuit|Society of Jesus|Georgetown University|Washington|District of Columbia||active
Jesuit|Society of Jesus|Gonzaga University|Spokane|Washington||active
Jesuit|Society of Jesus|John Carroll University|University Heights|Ohio||active
Jesuit|Society of Jesus|Le Moyne College|DeWitt|New York||active
Jesuit|Society of Jesus|Loyola Marymount University|Los Angeles|California||active
Jesuit|Society of Jesus|Loyola University Chicago|Chicago|Illinois||active
Jesuit|Society of Jesus|Loyola University Maryland|Baltimore|Maryland||active
Jesuit|Society of Jesus|Loyola University New Orleans|New Orleans|Louisiana||active
Jesuit|Society of Jesus|Marquette University|Milwaukee|Wisconsin||active
Jesuit|Society of Jesus|Regis University|Denver|Colorado||active
Jesuit|Society of Jesus|Rockhurst University|Kansas City|Missouri||active
Jesuit|Society of Jesus|Saint Joseph's University|Philadelphia|Pennsylvania||active
Jesuit|Society of Jesus|Saint Louis University|St. Louis|Missouri||active
Jesuit|Society of Jesus|Saint Peter's University|Jersey City|New Jersey||active
Jesuit|Society of Jesus|Santa Clara University|Santa Clara|California||active
Jesuit|Society of Jesus|Seattle University|Seattle|Washington||active
Jesuit|Society of Jesus|Spring Hill College|Mobile|Alabama||active
Jesuit|Society of Jesus|University of Detroit Mercy|Detroit|Michigan||active
Jesuit|Society of Jesus|University of San Francisco|San Francisco|California||active
Jesuit|Society of Jesus|University of Scranton|Scranton|Pennsylvania||active
Jesuit|Society of Jesus|Wheeling University|Wheeling|West Virginia||active
Jesuit|Society of Jesus|Xavier University|Cincinnati|Ohio||active
Missionaries of the Precious Blood||Calumet College of St. Joseph|Whiting|Indiana||active
Missionaries of the Precious Blood||Saint Joseph's College|Rensselaer|Indiana||active
Norbertine|Order of Canons Regular of Premontre|St. Norbert College|De Pere|Wisconsin||active
Oblates of St. Francis de Sales||DeSales University|Center Valley|Pennsylvania||active
Pontifical||The Catholic University of America|Washington|District of Columbia||active
Pontifical||Pontifical Catholic University of Puerto Rico|Ponce|Puerto Rico||active
School Sisters of Notre Dame||Mount Mary University|Milwaukee|Wisconsin||active
School Sisters of Notre Dame||Notre Dame of Maryland University|Baltimore|Maryland||active
Sinsinawa Dominican Sisters||Dominican University|River Forest|Illinois||active
Sinsinawa Dominican Sisters||Edgewood University|Madison|Wisconsin||active
Sisters of Charity||Clarke University|Dubuque|Iowa|Sisters of Charity of the Blessed Virgin Mary|active
Sisters of Charity||University of Mount Saint Vincent|Riverdale|New York|Sisters of Charity of New York|active
Sisters of Charity||Mount St. Joseph University|Cincinnati|Ohio|Sisters of Charity of Ohio|active
Sisters of Charity||Saint Elizabeth University|Morristown|New Jersey|Sisters of Charity of Saint Elizabeth of New Jersey|active
Sisters of Charity||Seton Hill University|Greensburg|Pennsylvania|Sisters of Charity of Seton Hill of Greensburg|active
Sisters of Charity||Spalding University|Louisville|Kentucky|Sisters of Charity of Nazareth|active
Sisters of Charity||University of the Incarnate Word|San Antonio|Texas|Sisters of Charity of the Incarnate Word|active
Sisters of Charity||University of Saint Mary|Leavenworth|Kansas|Sisters of Charity of Leavenworth|active
Sisters of Christian Charity||Assumption College for Sisters|Denville|New Jersey||active
Sisters of Divine Providence|Congregation of Divine Providence|La Roche University|McCandless|Pennsylvania||active
Sisters of Divine Providence|Congregation of Divine Providence|Our Lady of the Lake University|San Antonio|Texas||active
Sisters of the Holy Family of Nazareth||Holy Family University|Philadelphia|Pennsylvania||active
Sisters of Mercy||Carlow University|Pittsburgh|Pennsylvania||active
Sisters of Mercy||College of Saint Mary|Omaha|Nebraska||active
Sisters of Mercy||Georgian Court University|Lakewood|New Jersey||active
Sisters of Mercy||Gwynedd Mercy University|Gwynedd Valley|Pennsylvania||active
Sisters of Mercy||Maria College|Albany|New York||active
Sisters of Mercy||Mercy College of Health Sciences|Des Moines|Iowa||active
Sisters of Mercy||Mercy College of Ohio|Toledo|Ohio||active
Sisters of Mercy||Mercyhurst University|Erie|Pennsylvania||active
Sisters of Mercy||Misericordia University|Dallas|Pennsylvania||active
Sisters of Mercy||Mount Aloysius College|Cresson|Pennsylvania||active
Sisters of Mercy||Mount Mercy University|Cedar Rapids|Iowa||active
Sisters of Mercy||Saint Joseph's College of Maine|Standish|Maine||active
Sisters of Mercy||Saint Xavier University|Chicago|Illinois||active
Sisters of Mercy||Salve Regina University|Newport|Rhode Island||active
Sisters of Mercy||Trocaire College|Buffalo|New York||active
Sisters of Mercy||University of Saint Joseph|West Hartford|Connecticut||active
Sisters of Notre Dame de Namur||Emmanuel College|Boston|Massachusetts||active
Sisters of Notre Dame de Namur||Notre Dame de Namur University|Belmont|California||active
Sisters of Notre Dame de Namur||Trinity Washington University|Washington|District of Columbia||active
Sisters of the Presentation of Mary||Rivier University|Nashua|New Hampshire||active
Sisters of Providence (Montreal)||University of Providence|Great Falls|Montana||active
Sisters of Providence of Saint Mary-of-the-Woods||Saint Mary-of-the-Woods College|Terre Haute|Indiana||active
Sisters of St. Basil the Great|Ukrainian Catholic|Manor College|Jenkintown|Pennsylvania||active
Sisters of St. Joseph||Avila University|Kansas City|Missouri||active
Sisters of St. Joseph||Chestnut Hill College|Philadelphia|Pennsylvania||active
Sisters of St. Joseph||Elms College|Chicopee|Massachusetts||active
Sisters of St. Joseph||Mount St. Mary's University|Los Angeles|California||active
Sisters of St. Joseph||Regis College|Weston|Massachusetts||active
Sisters of St. Joseph||St. Catherine University|St. Paul|Minnesota||active
Sisters of St. Joseph||St. Joseph's University|Brooklyn|New York||active
Sisters, Servants of the Immaculate Heart of Mary||Immaculata University|Malvern|Pennsylvania||active
Sisters, Servants of the Immaculate Heart of Mary||Marywood University|Scranton|Pennsylvania||active
Society of the Divine Word||Divine Word College|Epworth|Iowa||active
Society of the Holy Child Jesus||Rosemont College|Rosemont|Pennsylvania||active
Society of Mary (Marianists)||Chaminade University of Honolulu|Honolulu|Hawaii||active
Society of Mary (Marianists)||St. Mary's University|San Antonio|Texas||active
Society of Mary (Marianists)||University of Dayton|Dayton|Ohio||active
Spiritans|Congregation of the Holy Spirit|Duquesne University|Pittsburgh|Pennsylvania||active
Ursuline|Sisters of Mount Saint Joseph|Brescia University|Owensboro|Kentucky||active
Vincentian|Congregation of the Mission|DePaul University|Chicago|Illinois||active
Vincentian|Congregation of the Mission|Niagara University|Lewiston|New York||active
Vincentian|Congregation of the Mission|St. John's University|Jamaica|New York||active
Independent||Augustine Institute|Florissant|Missouri||active
Independent||Ave Maria University|Ave Maria|Florida||active
Independent||Bellarmine University|Louisville|Kentucky||active
Independent||Christendom College|Front Royal|Virginia||active
Independent||Divine Mercy University|Sterling|Virginia||active
Independent||Holy Apostles College and Seminary|Cromwell|Connecticut||active
Independent||Holy Spirit College|Atlanta|Georgia||active
Independent||John Paul the Great Catholic University|San Diego|California||active
Independent||Marymount University|Arlington|Virginia||active
Independent||Maryville University|St. Louis|Missouri||active
Independent||Mexican American Catholic College|San Antonio|Texas||active
Independent||Sacred Heart University|Fairfield|Connecticut||active
Independent||Thomas Aquinas College|Santa Paula|California||active
Independent||Thomas More College of Liberal Arts|Merrimack|New Hampshire||active
Independent||Universidad del Sagrado Corazon|San Juan|Puerto Rico||active
Independent||University of Dallas|Irving|Texas||active
Independent||University of San Diego|San Diego|California||active
Independent||Ursuline College|Pepper Pike|Ohio||active
Independent||Wyoming Catholic College|Lander|Wyoming||active
Independent||Xavier University of Louisiana|New Orleans|Louisiana||active
"""

def parse_data():
    """Parse the pipe-delimited data into structured records."""
    records = []
    for line in DATA.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        parts = line.split('|')
        if len(parts) < 6:
            continue
        order, alt_name, name, city, state, sub_order, status = parts[:7]
        records.append({
            'order': order,
            'alt_name': alt_name,
            'university': name,
            'city': city,
            'state': state,
            'sub_order': sub_order or None,
            'status': status,
        })
    return records


def main():
    records = parse_data()
    print(f"Parsed {len(records)} Catholic university/college records")
    
    # Summary by order
    from collections import Counter
    order_counts = Counter(r['order'] for r in records)
    print("\nBy order:")
    for order, cnt in order_counts.most_common():
        print(f'  {order:45s}: {cnt:>3d}')
    
    # Summary by status
    status_counts = Counter(r['status'] for r in records)
    print(f"\nBy status: {dict(status_counts)}")
    
    # Save as JSON for reference
    with open('data/catholic_universities_by_order.json', 'w') as f:
        json.dump(records, f, indent=2)
    print("\nSaved to data/catholic_universities_by_order.json")
    
    # Now try to match to churches.db
    db = sqlite3.connect('churches.db')
    cur = db.cursor()
    
    # Check existing matches
    matched = 0
    unmatched = []
    
    for rec in records:
        name = rec['university']
        city = rec['city']
        state = rec['state']
        
        # Try exact match on name
        cur.execute("""
            SELECT rowid, name, city, state FROM churches 
            WHERE name LIKE ? AND city LIKE ? AND state LIKE ?
            LIMIT 3
        """, (f'%{name}%', f'%{city}%', f'%{state}%'))
        results = cur.fetchall()
        
        if results:
            matched += 1
            if len(results) == 1:
                # Update denomination_affiliation
                cur.execute("""
                    UPDATE churches SET denomination_affiliation = ?
                    WHERE rowid = ?
                """, (rec['order'], results[0][0]))
        else:
            unmatched.append(f"{name} ({city}, {state}) -> {rec['order']}")
    
    db.commit()
    
    print(f"\nMatched in DB: {matched}/{len(records)}")
    print(f"Unmatched: {len(unmatched)}")
    if unmatched:
        print("\nFirst 10 unmatched:")
        for u in unmatched[:10]:
            print(f'  {u}')
    
    # Show some matches
    cur.execute("""
        SELECT name, city, state, denomination_affiliation 
        FROM churches 
        WHERE denomination_affiliation IN ('Jesuit', 'Dominican', 'Benedictine', 'Franciscan', 'Holy Cross', 'Vincentian')
        LIMIT 15
    """)
    print("\nSample matches:")
    for r in cur.fetchall():
        print(f'  {r[0][:45]:45s} {r[1]:20s} {r[2]:15s} -> {r[3]}')
    
    db.close()

if __name__ == '__main__':
    main()
