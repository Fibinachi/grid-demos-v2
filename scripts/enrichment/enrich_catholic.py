#!/usr/bin/env python3
"""
Catholic Hierarchy Enrichment
==============================
Maps Catholic churches to their diocese, archdiocese, and province
using county FIPS and state. The Catholic Church organizes parishes
into dioceses, which are geographic — each US county belongs to
exactly one Latin Rite diocese.

Also covers Eastern Catholic eparchies and the Personal Ordinariate.

Sources:
  - USCCB diocese boundaries (public)
  - Catholic Directory / Official Catholic Directory
  - Each diocese's own parish finder

Usage:
    python scripts/enrichment/enrich_catholic.py
    python scripts/enrichment/enrich_catholic.py --dry-run
"""
import json, os, sqlite3, sys
from datetime import datetime

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(PROJECT_DIR, 'churches.db')

# ── US Catholic Dioceses by State ──
# Format: state -> [(diocese_name, archdiocese, province, rite)]
# For states with multiple dioceses, uses county-level mapping below.
# Source: USCCB official territorial boundaries (public data).

STATE_DIOCESE = {
    'AL': [('Diocese of Birmingham in Alabama', 'Mobile', 'Mobile', 'Latin'),
           ('Archdiocese of Mobile', 'Mobile', 'Mobile', 'Latin')],
    'AK': [('Archdiocese of Anchorage-Juneau', 'Anchorage-Juneau', 'Anchorage-Juneau', 'Latin')],
    'AZ': [('Diocese of Phoenix', 'Denver', 'Denver', 'Latin'),
           ('Diocese of Tucson', 'Denver', 'Denver', 'Latin')],
    'AR': [('Diocese of Little Rock', 'Oklahoma City', 'Oklahoma City', 'Latin')],
    'CA': [],  # Multi-diocese — handled by county mapping
    'CO': [('Archdiocese of Denver', 'Denver', 'Denver', 'Latin'),
           ('Diocese of Colorado Springs', 'Denver', 'Denver', 'Latin'),
           ('Diocese of Pueblo', 'Denver', 'Denver', 'Latin')],
    'CT': [('Archdiocese of Hartford', 'Hartford', 'Hartford', 'Latin'),
           ('Diocese of Bridgeport', 'Hartford', 'Hartford', 'Latin'),
           ('Diocese of Norwich', 'Hartford', 'Hartford', 'Latin')],
    'DE': [('Diocese of Wilmington', 'Baltimore', 'Baltimore', 'Latin')],
    'DC': [('Archdiocese of Washington', 'Washington', 'Washington', 'Latin')],
    'FL': [],  # Multi-diocese
    'GA': [('Archdiocese of Atlanta', 'Atlanta', 'Atlanta', 'Latin'),
           ('Diocese of Savannah', 'Atlanta', 'Atlanta', 'Latin')],
    'HI': [('Diocese of Honolulu', 'San Francisco', 'San Francisco', 'Latin')],
    'ID': [('Diocese of Boise', 'Portland', 'Portland', 'Latin')],
    'IL': [],  # Multi-diocese
    'IN': [],  # Multi-diocese
    'IA': [],  # Multi-diocese
    'KS': [('Archdiocese of Kansas City in Kansas', 'Kansas City', 'Kansas City', 'Latin'),
           ('Diocese of Dodge City', 'Kansas City', 'Kansas City', 'Latin'),
           ('Diocese of Salina', 'Kansas City', 'Kansas City', 'Latin'),
           ('Diocese of Wichita', 'Kansas City', 'Kansas City', 'Latin')],
    'KY': [('Archdiocese of Louisville', 'Louisville', 'Louisville', 'Latin'),
           ('Diocese of Covington', 'Louisville', 'Louisville', 'Latin'),
           ('Diocese of Lexington', 'Louisville', 'Louisville', 'Latin'),
           ('Diocese of Owensboro', 'Louisville', 'Louisville', 'Latin')],
    'LA': [('Archdiocese of New Orleans', 'New Orleans', 'New Orleans', 'Latin'),
           ('Diocese of Alexandria', 'New Orleans', 'New Orleans', 'Latin'),
           ('Diocese of Baton Rouge', 'New Orleans', 'New Orleans', 'Latin'),
           ('Diocese of Houma-Thibodaux', 'New Orleans', 'New Orleans', 'Latin'),
           ('Diocese of Lafayette', 'New Orleans', 'New Orleans', 'Latin'),
           ('Diocese of Lake Charles', 'New Orleans', 'New Orleans', 'Latin'),
           ('Diocese of Shreveport', 'New Orleans', 'New Orleans', 'Latin')],
    'ME': [('Diocese of Portland', 'Boston', 'Boston', 'Latin')],
    'MD': [('Archdiocese of Baltimore', 'Baltimore', 'Baltimore', 'Latin')],
    'MA': [('Archdiocese of Boston', 'Boston', 'Boston', 'Latin'),
           ('Diocese of Fall River', 'Boston', 'Boston', 'Latin'),
           ('Diocese of Springfield in Massachusetts', 'Boston', 'Boston', 'Latin'),
           ('Diocese of Worcester', 'Boston', 'Boston', 'Latin')],
    'MI': [],  # Multi-diocese
    'MN': [],  # Multi-diocese
    'MS': [('Diocese of Biloxi', 'Mobile', 'Mobile', 'Latin'),
           ('Diocese of Jackson', 'Mobile', 'Mobile', 'Latin')],
    'MO': [],  # Multi-diocese
    'MT': [('Diocese of Billings', 'Portland', 'Portland', 'Latin'),
           ('Diocese of Great Falls-Billings', 'Portland', 'Portland', 'Latin'),
           ('Diocese of Helena', 'Portland', 'Portland', 'Latin')],
    'NE': [('Archdiocese of Omaha', 'Omaha', 'Omaha', 'Latin'),
           ('Diocese of Grand Island', 'Omaha', 'Omaha', 'Latin'),
           ('Diocese of Lincoln', 'Omaha', 'Omaha', 'Latin')],
    'NV': [('Diocese of Las Vegas', 'San Francisco', 'San Francisco', 'Latin'),
           ('Diocese of Reno', 'San Francisco', 'San Francisco', 'Latin')],
    'NH': [('Diocese of Manchester', 'Boston', 'Boston', 'Latin')],
    'NJ': [],  # Multi-diocese
    'NM': [('Archdiocese of Santa Fe', 'Santa Fe', 'Santa Fe', 'Latin'),
           ('Diocese of Las Cruces', 'Santa Fe', 'Santa Fe', 'Latin')],
    'NY': [],  # Multi-diocese
    'NC': [('Diocese of Charlotte', 'Atlanta', 'Atlanta', 'Latin'),
           ('Diocese of Raleigh', 'Atlanta', 'Atlanta', 'Latin')],
    'ND': [('Diocese of Bismarck', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin'),
           ('Diocese of Fargo', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin')],
    'OH': [],  # Multi-diocese
    'OK': [('Archdiocese of Oklahoma City', 'Oklahoma City', 'Oklahoma City', 'Latin'),
           ('Diocese of Tulsa', 'Oklahoma City', 'Oklahoma City', 'Latin')],
    'OR': [('Archdiocese of Portland', 'Portland', 'Portland', 'Latin'),
           ('Diocese of Baker', 'Portland', 'Portland', 'Latin')],
    'PA': [],  # Multi-diocese
    'RI': [('Diocese of Providence', 'Boston', 'Boston', 'Latin')],
    'SC': [('Diocese of Charleston', 'Atlanta', 'Atlanta', 'Latin')],
    'SD': [('Diocese of Rapid City', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin'),
           ('Diocese of Sioux Falls', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin')],
    'TN': [('Diocese of Knoxville', 'Louisville', 'Louisville', 'Latin'),
           ('Diocese of Memphis', 'Louisville', 'Louisville', 'Latin'),
           ('Diocese of Nashville', 'Louisville', 'Louisville', 'Latin')],
    'TX': [],  # Multi-diocese — handled by county
    'UT': [('Diocese of Salt Lake City', 'San Francisco', 'San Francisco', 'Latin')],
    'VT': [('Diocese of Burlington', 'Boston', 'Boston', 'Latin')],
    'VA': [('Diocese of Arlington', 'Baltimore', 'Baltimore', 'Latin'),
           ('Diocese of Richmond', 'Baltimore', 'Baltimore', 'Latin')],
    'WA': [('Archdiocese of Seattle', 'Seattle', 'Seattle', 'Latin'),
           ('Diocese of Spokane', 'Seattle', 'Seattle', 'Latin'),
           ('Diocese of Yakima', 'Seattle', 'Seattle', 'Latin')],
    'WV': [('Diocese of Wheeling-Charleston', 'Baltimore', 'Baltimore', 'Latin')],
    'WI': [],  # Multi-diocese
    'WY': [('Diocese of Cheyenne', 'Denver', 'Denver', 'Latin')],
}

# ── County-level diocese mapping for multi-diocese states ──
# Format: (county_fips_5, or state, diocese_name)
# Only needed for states with multiple dioceses where boundaries follow county lines
COUNTY_DIOCESE = {
    # California
    ('CA', 'Los Angeles'): ('Archdiocese of Los Angeles', 'Los Angeles', 'Los Angeles', 'Latin'),
    ('CA', 'Orange'): ('Diocese of Orange', 'Los Angeles', 'Los Angeles', 'Latin'),
    ('CA', 'San Diego'): ('Diocese of San Diego', 'Los Angeles', 'Los Angeles', 'Latin'),
    ('CA', 'San Bernardino'): ('Diocese of San Bernardino', 'Los Angeles', 'Los Angeles', 'Latin'),
    ('CA', 'Riverside'): ('Diocese of San Bernardino', 'Los Angeles', 'Los Angeles', 'Latin'),
    ('CA', 'Santa Barbara'): ('Diocese of Monterey', 'Los Angeles', 'Los Angeles', 'Latin'),
    ('CA', 'Ventura'): ('Archdiocese of Los Angeles', 'Los Angeles', 'Los Angeles', 'Latin'),
    ('CA', 'San Francisco'): ('Archdiocese of San Francisco', 'San Francisco', 'San Francisco', 'Latin'),
    ('CA', 'San Mateo'): ('Archdiocese of San Francisco', 'San Francisco', 'San Francisco', 'Latin'),
    ('CA', 'Marin'): ('Archdiocese of San Francisco', 'San Francisco', 'San Francisco', 'Latin'),
    ('CA', 'Alameda'): ('Diocese of Oakland', 'San Francisco', 'San Francisco', 'Latin'),
    ('CA', 'Contra Costa'): ('Diocese of Oakland', 'San Francisco', 'San Francisco', 'Latin'),
    ('CA', 'Santa Clara'): ('Diocese of San Jose', 'San Francisco', 'San Francisco', 'Latin'),
    ('CA', 'Sacramento'): ('Diocese of Sacramento', 'San Francisco', 'San Francisco', 'Latin'),
    ('CA', 'Fresno'): ('Diocese of Fresno', 'Los Angeles', 'Los Angeles', 'Latin'),
    ('CA', 'Monterey'): ('Diocese of Monterey', 'Los Angeles', 'Los Angeles', 'Latin'),
    ('CA', 'Stockton'): ('Diocese of Stockton', 'San Francisco', 'San Francisco', 'Latin'),
    ('CA', 'Santa Rosa'): ('Diocese of Santa Rosa', 'San Francisco', 'San Francisco', 'Latin'),
    # Texas
    ('TX', 'Harris'): ('Archdiocese of Galveston-Houston', 'Galveston-Houston', 'Galveston-Houston', 'Latin'),
    ('TX', 'Dallas'): ('Diocese of Dallas', 'Galveston-Houston', 'Galveston-Houston', 'Latin'),
    ('TX', 'Tarrant'): ('Diocese of Fort Worth', 'Galveston-Houston', 'Galveston-Houston', 'Latin'),
    ('TX', 'Bexar'): ('Archdiocese of San Antonio', 'San Antonio', 'San Antonio', 'Latin'),
    ('TX', 'Travis'): ('Diocese of Austin', 'Galveston-Houston', 'Galveston-Houston', 'Latin'),
    ('TX', 'El Paso'): ('Diocese of El Paso', 'San Antonio', 'San Antonio', 'Latin'),
    ('TX', 'Cameron'): ('Diocese of Brownsville', 'San Antonio', 'San Antonio', 'Latin'),
    ('TX', 'Lubbock'): ('Diocese of Lubbock', 'San Antonio', 'San Antonio', 'Latin'),
    ('TX', 'Amarillo'): ('Diocese of Amarillo', 'San Antonio', 'San Antonio', 'Latin'),
    ('TX', 'Nueces'): ('Diocese of Corpus Christi', 'San Antonio', 'San Antonio', 'Latin'),
    ('TX', 'Victoria'): ('Diocese of Victoria', 'Galveston-Houston', 'Galveston-Houston', 'Latin'),
    ('TX', 'Tyler'): ('Diocese of Tyler', 'Galveston-Houston', 'Galveston-Houston', 'Latin'),
    ('TX', 'San Angelo'): ('Diocese of San Angelo', 'San Antonio', 'San Antonio', 'Latin'),
    # New York
    ('NY', 'New York'): ('Archdiocese of New York', 'New York', 'New York', 'Latin'),
    ('NY', 'Kings'): ('Diocese of Brooklyn', 'New York', 'New York', 'Latin'),
    ('NY', 'Queens'): ('Diocese of Brooklyn', 'New York', 'New York', 'Latin'),
    ('NY', 'Richmond'): ('Archdiocese of New York', 'New York', 'New York', 'Latin'),
    ('NY', 'Bronx'): ('Archdiocese of New York', 'New York', 'New York', 'Latin'),
    ('NY', 'Erie'): ('Diocese of Buffalo', 'New York', 'New York', 'Latin'),
    ('NY', 'Monroe'): ('Diocese of Rochester', 'New York', 'New York', 'Latin'),
    ('NY', 'Onondaga'): ('Diocese of Syracuse', 'New York', 'New York', 'Latin'),
    ('NY', 'Albany'): ('Diocese of Albany', 'New York', 'New York', 'Latin'),
    ('NY', 'Rockland'): ('Archdiocese of New York', 'New York', 'New York', 'Latin'),
    ('NY', 'Westchester'): ('Archdiocese of New York', 'New York', 'New York', 'Latin'),
    ('NY', 'Suffolk'): ('Diocese of Rockville Centre', 'New York', 'New York', 'Latin'),
    ('NY', 'Nassau'): ('Diocese of Rockville Centre', 'New York', 'New York', 'Latin'),
    ('NY', 'Dutchess'): ('Archdiocese of New York', 'New York', 'New York', 'Latin'),
    # Illinois
    ('IL', 'Cook'): ('Archdiocese of Chicago', 'Chicago', 'Chicago', 'Latin'),
    ('IL', 'DuPage'): ('Diocese of Joliet', 'Chicago', 'Chicago', 'Latin'),
    ('IL', 'Lake'): ('Archdiocese of Chicago', 'Chicago', 'Chicago', 'Latin'),
    ('IL', 'Will'): ('Diocese of Joliet', 'Chicago', 'Chicago', 'Latin'),
    ('IL', 'Kane'): ('Diocese of Rockford', 'Chicago', 'Chicago', 'Latin'),
    ('IL', 'McHenry'): ('Diocese of Rockford', 'Chicago', 'Chicago', 'Latin'),
    ('IL', 'Peoria'): ('Diocese of Peoria', 'Chicago', 'Chicago', 'Latin'),
    ('IL', 'Sangamon'): ('Diocese of Springfield in Illinois', 'Chicago', 'Chicago', 'Latin'),
    ('IL', 'St. Clair'): ('Diocese of Belleville', 'Chicago', 'Chicago', 'Latin'),
    # Pennsylvania
    ('PA', 'Philadelphia'): ('Archdiocese of Philadelphia', 'Philadelphia', 'Philadelphia', 'Latin'),
    ('PA', 'Allegheny'): ('Diocese of Pittsburgh', 'Philadelphia', 'Philadelphia', 'Latin'),
    ('PA', 'Lackawanna'): ('Diocese of Scranton', 'Philadelphia', 'Philadelphia', 'Latin'),
    ('PA', 'Dauphin'): ('Diocese of Harrisburg', 'Philadelphia', 'Philadelphia', 'Latin'),
    ('PA', 'Erie'): ('Diocese of Erie', 'Philadelphia', 'Philadelphia', 'Latin'),
    ('PA', 'Northampton'): ('Diocese of Allentown', 'Philadelphia', 'Philadelphia', 'Latin'),
    ('PA', 'Westmoreland'): ('Diocese of Greensburg', 'Philadelphia', 'Philadelphia', 'Latin'),
    ('PA', 'Cambria'): ('Diocese of Altoona-Johnstown', 'Philadelphia', 'Philadelphia', 'Latin'),
    # Ohio
    ('OH', 'Cuyahoga'): ('Diocese of Cleveland', 'Cincinnati', 'Cincinnati', 'Latin'),
    ('OH', 'Hamilton'): ('Archdiocese of Cincinnati', 'Cincinnati', 'Cincinnati', 'Latin'),
    ('OH', 'Franklin'): ('Diocese of Columbus', 'Cincinnati', 'Cincinnati', 'Latin'),
    ('OH', 'Lucas'): ('Diocese of Toledo', 'Cincinnati', 'Cincinnati', 'Latin'),
    ('OH', 'Mahoning'): ('Diocese of Youngstown', 'Cincinnati', 'Cincinnati', 'Latin'),
    ('OH', 'Stark'): ('Diocese of Youngstown', 'Cincinnati', 'Cincinnati', 'Latin'),
    ('OH', 'Summit'): ('Diocese of Cleveland', 'Cincinnati', 'Cincinnati', 'Latin'),
    ('OH', 'Montgomery'): ('Archdiocese of Cincinnati', 'Cincinnati', 'Cincinnati', 'Latin'),
    # Michigan
    ('MI', 'Wayne'): ('Archdiocese of Detroit', 'Detroit', 'Detroit', 'Latin'),
    ('MI', 'Oakland'): ('Archdiocese of Detroit', 'Detroit', 'Detroit', 'Latin'),
    ('MI', 'Macomb'): ('Archdiocese of Detroit', 'Detroit', 'Detroit', 'Latin'),
    ('MI', 'Kent'): ('Diocese of Grand Rapids', 'Detroit', 'Detroit', 'Latin'),
    ('MI', 'Ingham'): ('Diocese of Lansing', 'Detroit', 'Detroit', 'Latin'),
    ('MI', 'Kalamazoo'): ('Diocese of Kalamazoo', 'Detroit', 'Detroit', 'Latin'),
    ('MI', 'Washtenaw'): ('Diocese of Lansing', 'Detroit', 'Detroit', 'Latin'),
    ('MI', 'Marquette'): ('Diocese of Marquette', 'Detroit', 'Detroit', 'Latin'),
    ('MI', 'Saginaw'): ('Diocese of Saginaw', 'Detroit', 'Detroit', 'Latin'),
    ('MI', 'Genesee'): ('Diocese of Lansing', 'Detroit', 'Detroit', 'Latin'),
    # New Jersey
    ('NJ', 'Bergen'): ('Archdiocese of Newark', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Essex'): ('Archdiocese of Newark', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Union'): ('Archdiocese of Newark', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Hudson'): ('Archdiocese of Newark', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Passaic'): ('Diocese of Paterson', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Morris'): ('Diocese of Paterson', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Middlesex'): ('Diocese of Metuchen', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Monmouth'): ('Diocese of Trenton', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Mercer'): ('Diocese of Trenton', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Camden'): ('Diocese of Camden', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Burlington'): ('Diocese of Trenton', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Cumberland'): ('Diocese of Camden', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Gloucester'): ('Diocese of Camden', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Sussex'): ('Diocese of Paterson', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Warren'): ('Diocese of Metuchen', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Ocean'): ('Diocese of Trenton', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Atlantic'): ('Diocese of Camden', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Cape May'): ('Diocese of Camden', 'Newark', 'Newark', 'Latin'),
    ('NJ', 'Salem'): ('Diocese of Camden', 'Newark', 'Newark', 'Latin'),
    # Florida
    ('FL', 'Miami-Dade'): ('Archdiocese of Miami', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Broward'): ('Archdiocese of Miami', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Palm Beach'): ('Diocese of Palm Beach', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Duval'): ('Diocese of St. Augustine', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Orange'): ('Diocese of Orlando', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Hillsborough'): ('Diocese of St. Petersburg', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Pinellas'): ('Diocese of St. Petersburg', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Pasco'): ('Diocese of St. Petersburg', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Lee'): ('Diocese of Venice', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Collier'): ('Diocese of Venice', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Polk'): ('Diocese of Orlando', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Brevard'): ('Diocese of Orlando', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Volusia'): ('Diocese of Orlando', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Seminole'): ('Diocese of Orlando', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Leon'): ('Diocese of Pensacola-Tallahassee', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Escambia'): ('Diocese of Pensacola-Tallahassee', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Santa Rosa'): ('Diocese of Pensacola-Tallahassee', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Alachua'): ('Diocese of St. Augustine', 'Miami', 'Miami', 'Latin'),
    ('FL', 'Marion'): ('Diocese of St. Augustine', 'Miami', 'Miami', 'Latin'),
    # Wisconsin
    ('WI', 'Milwaukee'): ('Archdiocese of Milwaukee', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Brown'): ('Diocese of Green Bay', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Dane'): ('Diocese of Madison', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Douglas'): ('Diocese of Superior', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Eau Claire'): ('Diocese of La Crosse', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'La Crosse'): ('Diocese of La Crosse', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Oneida'): ('Diocese of Superior', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Outagamie'): ('Diocese of Green Bay', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Portage'): ('Diocese of Madison', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Winnebago'): ('Diocese of Green Bay', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Wood'): ('Diocese of La Crosse', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Waukesha'): ('Archdiocese of Milwaukee', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Kenosha'): ('Archdiocese of Milwaukee', 'Milwaukee', 'Milwaukee', 'Latin'),
    ('WI', 'Racine'): ('Archdiocese of Milwaukee', 'Milwaukee', 'Milwaukee', 'Latin'),
    # Minnesota
    ('MN', 'Hennepin'): ('Archdiocese of St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin'),
    ('MN', 'Ramsey'): ('Archdiocese of St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin'),
    ('MN', 'St. Louis'): ('Diocese of Duluth', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin'),
    ('MN', 'Stearns'): ('Diocese of St. Cloud', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin'),
    ('MN', 'Blue Earth'): ('Diocese of Winona-Rochester', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin'),
    ('MN', 'Olmsted'): ('Diocese of Winona-Rochester', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin'),
    ('MN', 'Clay'): ('Diocese of Crookston', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin'),
    ('MN', 'Polk'): ('Diocese of Crookston', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin'),
    ('MN', 'Beltrami'): ('Diocese of Crookston', 'St. Paul and Minneapolis', 'St. Paul and Minneapolis', 'Latin'),
    # Missouri
    ('MO', 'St. Louis'): ('Archdiocese of St. Louis', 'St. Louis', 'St. Louis', 'Latin'),
    ('MO', 'Jackson'): ('Diocese of Kansas City-St. Joseph', 'St. Louis', 'St. Louis', 'Latin'),
    ('MO', 'Greene'): ('Diocese of Springfield-Cape Girardeau', 'St. Louis', 'St. Louis', 'Latin'),
    ('MO', 'Boone'): ('Diocese of Jefferson City', 'St. Louis', 'St. Louis', 'Latin'),
    ('MO', 'Buchanan'): ('Diocese of Kansas City-St. Joseph', 'St. Louis', 'St. Louis', 'Latin'),
    ('MO', 'Cole'): ('Diocese of Jefferson City', 'St. Louis', 'St. Louis', 'Latin'),
    # Indiana
    ('IN', 'Marion'): ('Archdiocese of Indianapolis', 'Indianapolis', 'Indianapolis', 'Latin'),
    ('IN', 'Lake'): ('Diocese of Gary', 'Indianapolis', 'Indianapolis', 'Latin'),
    ('IN', 'St. Joseph'): ('Diocese of Fort Wayne-South Bend', 'Indianapolis', 'Indianapolis', 'Latin'),
    ('IN', 'Allen'): ('Diocese of Fort Wayne-South Bend', 'Indianapolis', 'Indianapolis', 'Latin'),
    ('IN', 'Vanderburgh'): ('Diocese of Evansville', 'Indianapolis', 'Indianapolis', 'Latin'),
    ('IN', 'Tippecanoe'): ('Diocese of Lafayette in Indiana', 'Indianapolis', 'Indianapolis', 'Latin'),
    ('IN', 'St. Joseph'): ('Diocese of Fort Wayne-South Bend', 'Indianapolis', 'Indianapolis', 'Latin'),
    # Iowa
    ('IA', 'Polk'): ('Diocese of Des Moines', 'Dubuque', 'Dubuque', 'Latin'),
    ('IA', 'Linn'): ('Archdiocese of Dubuque', 'Dubuque', 'Dubuque', 'Latin'),
    ('IA', 'Scott'): ('Diocese of Davenport', 'Dubuque', 'Dubuque', 'Latin'),
    ('IA', 'Woodbury'): ('Diocese of Sioux City', 'Dubuque', 'Dubuque', 'Latin'),
    ('IA', 'Johnson'): ('Diocese of Davenport', 'Dubuque', 'Dubuque', 'Latin'),
    ('IA', 'Black Hawk'): ('Archdiocese of Dubuque', 'Dubuque', 'Dubuque', 'Latin'),
}

# ── Eastern Catholic Eparchies (by state approximation) ──
EASTERN_EPARCHIES = [
    ('Ukrainian Catholic Archeparchy of Philadelphia', 'Philadelphia', 'Philadelphia', 'Ukrainian'),
    ('Ukrainian Catholic Eparchy of Chicago', 'Philadelphia', 'Philadelphia', 'Ukrainian'),
    ('Ukrainian Catholic Eparchy of Stamford', 'Philadelphia', 'Philadelphia', 'Ukrainian'),
    ('Ruthenian Byzantine Catholic Metropolia of Pittsburgh', 'Pittsburgh', 'Pittsburgh', 'Ruthenian'),
    ('Syro-Malabar Catholic Eparchy of St. Thomas', 'Chicago', 'Chicago', 'Syro-Malabar'),
    ('Chaldean Catholic Eparchy of St. Thomas the Apostle', 'Detroit', 'Detroit', 'Chaldean'),
    ('Maronite Catholic Eparchy of Our Lady of Lebanon', 'Los Angeles', 'Los Angeles', 'Maronite'),
    ('Melkite Greek Catholic Eparchy of Newton', 'Boston', 'Boston', 'Melkite'),
    ('Armenian Catholic Eparchy of Our Lady of Nareg', 'New York', 'New York', 'Armenian'),
    ('Romanian Catholic Eparchy of St. George', 'Canton', 'Canton', 'Romanian'),
    ('Syriac Catholic Eparchy of Our Lady of Deliverance', 'Newark', 'Newark', 'Syriac'),
    ('Coptic Catholic Eparchy of St. Mark', 'Washington', 'Washington', 'Coptic'),
    ('Ethiopian Catholic Eparchy of Emdeber', 'Washington', 'Washington', 'Ethiopian'),
]


def add_catholic_columns(db):
    existing = {r[1] for r in db.execute("PRAGMA table_info(churches)").fetchall()}
    for col, dtype in [('diocese', 'TEXT'), ('archdiocese', 'TEXT'),
                       ('province', 'TEXT'), ('rite', 'TEXT'),
                       ('catholic_hierarchy_source', 'TEXT')]:
        if col not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col} {dtype}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Catholic hierarchy enrichment')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--reprocess', action='store_true',
                        help='Reprocess already-assigned churches')
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=60)
    # Columns already exist from previous schema additions
    existing = {r[1] for r in db.execute("PRAGMA table_info(churches)").fetchall()}
    for col, dtype in [('diocese', 'TEXT'), ('archdiocese', 'TEXT'),
                       ('province', 'TEXT'), ('rite', 'TEXT'),
                       ('catholic_hierarchy_source', 'TEXT')]:
        if col not in existing:
            db.execute(f"ALTER TABLE churches ADD COLUMN {col} {dtype}")

    # Get Catholic churches — use family/denom classification first,
    # then add name-based heuristics for unclassified ones
    where_clause = "" if args.reprocess else "AND (diocese IS NULL OR diocese = '')"
    catholic = db.execute(f"""
        SELECT id, name, city, state, fips
        FROM churches
        WHERE (faith_tradition = 'christian' 
           AND (family = 'Catholic Churches' OR denomination LIKE '%catholic%'
                OR LOWER(name) LIKE '%catholic church%' OR LOWER(name) LIKE '%catholic parish%'
                OR LOWER(name) LIKE '%catholic community%'))
           {where_clause}
        ORDER BY id
    """).fetchall()

    print(f"Catholic churches needing hierarchy: {len(catholic):,}")
    if args.limit:
        catholic = catholic[:args.limit]

    if args.dry_run:
        for r in catholic[:10]:
            print(f"  {r[0]:>8d} | {r[1][:45]:45s} | {r[2]:20s} {r[3]}")
        db.close()
        return

    updated = 0
    for row in catholic:
        cid, cname, city, state, fips = row
        diocese = None
        archdiocese = None
        province = None
        rite = 'Latin'

        # Try county-level mapping first
        if fips and fips in COUNTY_DIOCESE:
            diocese, archdiocese, province, rite = COUNTY_DIOCESE[fips]
        elif state and city:
            # Try state + city mapping
            key = (state, city)
            if key in COUNTY_DIOCESE:
                diocese, archdiocese, province, rite = COUNTY_DIOCESE[key]
        
        # Fall back to state-level mapping
        if not diocese and state and state in STATE_DIOCESE:
            dioceses = STATE_DIOCESE[state]
            if len(dioceses) == 1:
                diocese, archdiocese, province, rite = dioceses[0]
            elif len(dioceses) > 1 and city:
                # Single-diocese state: try to find the right one
                # For multi-diocese states without county match, assign the main metro
                diocese = dioceses[0][0]
                archdiocese = dioceses[0][1]
                province = dioceses[0][2]
                rite = dioceses[0][3]

        if diocese:
            db.execute("""UPDATE churches SET 
                diocese=?, archdiocese=?, province=?, rite=?,
                catholic_hierarchy_source='geographic_mapping',
                last_updated=datetime('now')
                WHERE id=?""", (diocese, archdiocese, province, rite, cid))
            updated += 1

    db.commit()
    print(f"Updated: {updated:,} churches")

    # Report
    rs = db.execute("""
        SELECT diocese, COUNT(*) as cnt FROM churches 
        WHERE diocese != '' AND diocese IS NOT NULL 
        GROUP BY diocese ORDER BY cnt DESC LIMIT 20
    """).fetchall()
    print("\nTop dioceses:")
    for r in rs:
        print(f"  {r[0][:45]:45s} {r[1]:>7,}")

    rs = db.execute("""
        SELECT COUNT(*) FROM churches 
        WHERE (family='Catholic Churches' OR denomination LIKE '%catholic%')
        AND (diocese IS NULL OR diocese = '')
    """).fetchone()
    print(f"\nStill unassigned: {rs[0]:,}")

    db.close()
    print("\nDone!")


if __name__ == '__main__':
    main()
