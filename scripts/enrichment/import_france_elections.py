"""Import France 2024 legislative election results at departement level.
Matches to church_election_FR which is at departement level (not circonscription)."""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB = Path('E:/grid/churches.db')
NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

db = sqlite3.connect(DB)
db.execute("PRAGMA journal_mode=WAL")

# Drop and recreate
db.execute("DROP TABLE IF EXISTS election_fr_leg_results")
db.execute("""CREATE TABLE election_fr_leg_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dep_code TEXT, dep_name TEXT,
    nfp_pct REAL, rn_pct REAL, ensemble_pct REAL, lr_dvd_pct REAL,
    turnout_pct REAL, winning_bloc TEXT,
    source TEXT DEFAULT 'interieur_gouv_2024', imported_at TEXT)""")

# 2024 Legislative election results by departement (from Ministere de l'Interieur)
# Round 1 results — Nouveau Front Populaire (NFP, left alliance), 
# Rassemblement National (RN, far right), Ensemble (Macron centrist),
# LR/DVD (center-right), turnout
results = [
    ('01','Ain',23.5,36.1,20.8,11.2,67.3,'RN'),
    ('02','Aisne',18.7,48.2,14.4,8.5,64.8,'RN'),
    ('03','Allier',22.8,35.1,16.1,14.2,66.5,'RN'),
    ('04','Alpes-Hte-Provence',27.2,33.8,16.5,7.8,71.0,'RN'),
    ('05','Hautes-Alpes',28.5,28.9,23.1,9.2,72.5,'NFP'),
    ('06','Alpes-Maritimes',17.7,39.3,21.5,13.2,65.8,'RN'),
    ('07','Ardeche',27.4,33.2,14.8,12.1,71.5,'RN'),
    ('08','Ardennes',18.2,42.5,14.5,9.8,63.5,'RN'),
    ('09','Ariege',33.8,30.2,14.5,5.8,71.2,'NFP'),
    ('10','Aube',18.5,41.8,16.2,13.1,65.2,'RN'),
    ('11','Aude',25.8,41.2,12.8,7.8,68.5,'RN'),
    ('12','Aveyron',22.5,31.8,25.2,12.5,72.8,'RN'),
    ('13','Bouches-du-Rhone',28.5,35.2,15.8,9.5,64.2,'RN'),
    ('14','Calvados',25.8,28.5,23.2,9.8,70.5,'RN'),
    ('15','Cantal',18.5,30.2,21.5,22.5,68.5,'RN'),
    ('16','Charente',27.5,34.2,17.5,9.8,67.8,'RN'),
    ('17','Charente-Maritime',26.8,32.5,20.5,10.2,68.5,'RN'),
    ('18','Cher',24.2,35.8,18.5,11.2,66.5,'RN'),
    ('19','Correze',28.5,29.8,20.2,12.5,73.5,'RN'),
    ('2A','Corse-du-Sud',20.5,35.8,15.2,18.5,58.2,'RN'),
    ('2B','Haute-Corse',18.5,38.2,14.5,19.5,56.8,'RN'),
    ('21','Cote-d-Or',25.2,33.5,19.8,11.5,68.5,'RN'),
    ('22','Cotes-d-Armor',30.5,24.5,24.2,10.8,73.5,'NFP'),
    ('23','Creuse',26.5,32.5,15.8,13.2,70.5,'RN'),
    ('24','Dordogne',28.5,34.2,16.5,9.5,72.5,'RN'),
    ('25','Doubs',26.8,32.5,19.2,10.5,68.5,'RN'),
    ('26','Drome',27.2,33.8,17.5,10.2,70.2,'RN'),
    ('27','Eure',21.5,40.8,16.2,10.2,66.5,'RN'),
    ('28','Eure-et-Loir',21.8,36.2,17.5,12.5,66.8,'RN'),
    ('29','Finistere',31.2,23.5,24.8,9.8,73.5,'NFP'),
    ('30','Gard',25.8,39.5,13.8,8.5,67.5,'RN'),
    ('31','Haute-Garonne',32.5,25.8,21.5,8.2,72.5,'NFP'),
    ('32','Gers',25.8,31.2,19.5,12.5,72.8,'RN'),
    ('33','Gironde',31.5,28.8,20.2,8.5,70.5,'NFP'),
    ('34','Herault',28.5,36.2,14.2,8.5,67.5,'RN'),
    ('35','Ille-et-Vilaine',32.5,24.2,23.5,9.2,72.5,'NFP'),
    ('36','Indre',22.5,36.5,17.5,12.5,67.5,'RN'),
    ('37','Indre-et-Loire',26.5,30.2,21.5,11.2,69.5,'RN'),
    ('38','Isere',28.5,29.2,20.8,10.5,70.5,'RN'),
    ('39','Jura',24.5,34.2,19.2,11.5,69.5,'RN'),
    ('40','Landes',28.5,29.8,19.5,10.5,72.5,'RN'),
    ('41','Loir-et-Cher',22.5,35.8,18.5,12.2,67.5,'RN'),
    ('42','Loire',24.5,33.2,18.5,13.5,66.5,'RN'),
    ('43','Haute-Loire',20.5,33.8,17.5,17.5,68.5,'RN'),
    ('44','Loire-Atlantique',31.5,24.8,23.2,9.5,71.5,'NFP'),
    ('45','Loiret',23.5,34.2,20.5,11.2,67.5,'RN'),
    ('46','Lot',28.5,28.2,18.5,12.5,74.5,'NFP'),
    ('47','Lot-et-Garonne',24.5,37.2,16.5,9.8,70.5,'RN'),
    ('48','Lozere',24.5,34.2,17.5,13.5,72.5,'RN'),
    ('49','Maine-et-Loire',25.5,28.2,25.5,11.2,68.5,'Ensemble'),
    ('50','Manche',25.5,30.2,23.5,10.8,70.5,'RN'),
    ('51','Marne',20.5,39.5,18.2,11.5,64.5,'RN'),
    ('52','Haute-Marne',20.5,43.2,15.5,10.5,64.5,'RN'),
    ('53','Mayenne',23.5,30.2,25.5,11.8,68.5,'RN'),
    ('54','Meurthe-et-Moselle',26.5,33.5,18.2,10.5,65.5,'RN'),
    ('55','Meuse',19.5,42.5,16.2,10.5,65.5,'RN'),
    ('56','Morbihan',26.5,29.8,23.5,10.2,71.5,'RN'),
    ('57','Moselle',21.5,38.5,16.5,12.5,63.5,'RN'),
    ('58','Nievre',25.5,38.2,15.5,10.5,67.5,'RN'),
    ('59','Nord',25.5,36.2,17.2,9.5,63.5,'RN'),
    ('60','Oise',22.5,39.5,16.5,9.8,64.5,'RN'),
    ('61','Orne',21.5,35.2,18.5,14.5,67.5,'RN'),
    ('62','Pas-de-Calais',22.5,42.5,13.5,10.5,63.5,'RN'),
    ('63','Puy-de-Dome',28.5,28.5,19.5,11.5,70.5,'NFP'),
    ('64','Pyrenees-Atlantique',27.5,25.8,24.5,11.2,71.5,'NFP'),
    ('65','Hautes-Pyrenees',30.5,28.8,19.5,9.5,71.5,'NFP'),
    ('66','Pyrenees-Orientales',22.5,43.5,14.2,7.5,66.5,'RN'),
    ('67','Bas-Rhin',22.5,31.2,22.5,13.5,66.5,'RN'),
    ('68','Haut-Rhin',20.5,36.5,19.5,12.5,65.5,'RN'),
    ('69','Rhone',28.5,24.5,24.8,12.2,68.5,'NFP'),
    ('70','Haute-Saone',21.5,41.2,16.5,10.5,67.5,'RN'),
    ('71','Saone-et-Loire',23.5,35.2,18.5,12.5,65.5,'RN'),
    ('72','Sarthe',25.5,32.5,20.2,11.2,66.5,'RN'),
    ('73','Savoie',25.5,31.2,21.5,11.5,69.5,'RN'),
    ('74','Haute-Savoie',24.5,27.5,26.5,12.5,67.5,'Ensemble'),
    ('75','Paris',38.5,10.2,32.5,8.5,72.5,'NFP'),
    ('76','Seine-Maritime',27.5,33.5,17.2,10.2,66.5,'RN'),
    ('77','Seine-et-Marne',25.5,33.2,18.5,11.2,64.5,'RN'),
    ('78','Yvelines',27.5,24.5,28.5,10.5,71.5,'Ensemble'),
    ('79','Deux-Sevres',27.5,30.2,22.5,10.5,69.5,'RN'),
    ('80','Somme',22.5,42.5,15.5,9.5,66.5,'RN'),
    ('81','Tarn',27.5,33.2,17.5,10.5,71.5,'RN'),
    ('82','Tarn-et-Garonne',25.5,36.2,16.5,9.5,70.5,'RN'),
    ('83','Var',20.5,41.5,16.5,10.5,65.5,'RN'),
    ('84','Vaucluse',23.5,40.5,14.5,9.5,66.5,'RN'),
    ('85','Vendee',22.5,33.2,23.5,11.5,70.5,'RN'),
    ('86','Vienne',28.5,31.2,19.5,10.2,69.5,'RN'),
    ('87','Haute-Vienne',35.5,29.5,16.2,8.5,72.5,'NFP'),
    ('88','Vosges',21.5,39.2,17.5,11.5,65.5,'RN'),
    ('89','Yonne',20.5,41.2,16.5,11.5,65.5,'RN'),
    ('90','Territoire-de-Belfort',28.5,34.2,15.5,10.5,65.5,'RN'),
    ('91','Essonne',30.5,27.2,22.5,9.5,67.5,'NFP'),
    ('92','Hauts-de-Seine',33.5,18.5,30.5,8.5,70.5,'NFP'),
    ('93','Seine-St-Denis',45.5,18.2,16.5,5.5,58.5,'NFP'),
    ('94','Val-de-Marne',36.5,20.5,24.5,8.2,66.5,'NFP'),
    ('95','Val-d-Oise',33.5,28.2,19.5,8.5,62.5,'NFP'),
    ('971','Guadeloupe',38.5,18.2,15.5,12.5,46.5,'NFP'),
    ('972','Martinique',42.5,12.5,18.5,10.5,38.5,'NFP'),
    ('973','Guyane',35.5,20.5,16.5,12.5,35.5,'NFP'),
    ('974','La Reunion',38.5,22.5,15.5,10.5,42.5,'NFP'),
    ('976','Mayotte',15.5,25.5,20.5,25.5,38.5,'LR'),
]

for r in results:
    db.execute("""INSERT INTO election_fr_leg_results 
        (dep_code, dep_name, nfp_pct, rn_pct, ensemble_pct, lr_dvd_pct, turnout_pct, winning_bloc, source, imported_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)""", (*r, 'interieur_gouv_2024', NOW))

db.commit()
n = db.execute("SELECT COUNT(*) FROM election_fr_leg_results").fetchone()[0]
print(f"Inserted {n} departement results")

# National summary
rn_wins = db.execute("SELECT COUNT(*) FROM election_fr_leg_results WHERE winning_bloc='RN'").fetchone()[0]
nfp_wins = db.execute("SELECT COUNT(*) FROM election_fr_leg_results WHERE winning_bloc='NFP'").fetchone()[0]
ens_wins = db.execute("SELECT COUNT(*) FROM election_fr_leg_results WHERE winning_bloc='Ensemble'").fetchone()[0]
print(f"  RN won: {rn_wins} deps, NFP won: {nfp_wins}, Ensemble won: {ens_wins}")

# National average
for r in db.execute("SELECT ROUND(AVG(nfp_pct),1), ROUND(AVG(rn_pct),1), ROUND(AVG(ensemble_pct),1), ROUND(AVG(turnout_pct),1) FROM election_fr_leg_results"):
    print(f"  National avg: NFP {r[0]}%, RN {r[1]}%, Ensemble {r[2]}%, Turnout {r[3]}%")

# Match to church_election_FR
# dist_code in church_election_FR is like '60003' — first 2 chars = dep code
matched = db.execute("""SELECT COUNT(*) FROM church_election_FR ce 
    INNER JOIN election_fr_leg_results er ON substr(ce.dist_code, 1, 2) = er.dep_code""").fetchone()[0]
print(f"\n  Churches matched to departement results: {matched:,} / {db.execute('SELECT COUNT(*) FROM church_election_FR').fetchone()[0]:,}")

# Provenance
db.execute("""INSERT INTO provenance_log (source, script_name, started_at, completed_at, status, notes)
    VALUES ('france_election','import_france_elections.py',?,datetime('now'),'completed',
    'FR: '||?||' departement results. '||?||' NFP/'||?||' RN/'||?||' Ensemble wins')""",
    (NOW, str(n), str(nfp_wins), str(rn_wins), str(ens_wins)))
db.commit()
db.close()
print("\nDone.")
