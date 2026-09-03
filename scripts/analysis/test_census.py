"""Test Census API for church demographic enrichment"""
import urllib.request, json, csv

# American Community Survey 5-year estimates (most recent)
# Variables available at ZIP code level
CENSUS_URL = "https://api.census.gov/data/2022/acs/acs5"

# Key demographic variables for ZCTA5 (ZIP code tabulation area)
# We can get: income, population, race, education, housing, poverty
VARS = {
    "B01001_001E": "total_population",
    "B19013_001E": "median_household_income",
    "B17001_002E": "poverty_count",  # below poverty level
    "B15003_022E": "bachelors_degree_count",
    "B15003_023E": "masters_degree_count",
    "B15003_024E": "professional_degree_count",
    "B15003_025E": "doctorate_degree_count",
    "B25077_001E": "median_home_value",
    "B25064_001E": "median_gross_rent",
    "B02001_002E": "white_population",
    "B02001_003E": "black_population",
    "B02001_004E": "native_american_population",
    "B02001_005E": "asian_population",
    "B02001_006E": "pacific_islander_population",
    "B02001_007E": "other_race_population",
    "B02001_008E": "two_or_more_races_population",
}

def get_zip_demographics(zipcode):
    """Get demographic data for a ZIP code from Census ACS."""
    vars_str = ",".join(VARS.keys())
    url = f"{CENSUS_URL}?get={vars_str}&for=zip%20code%20tabulation%20area:{zipcode}&key=b5a1e77b4d8a5f6c6e58798f7c3a0e2f1d4b9c8a"
    
    # Actually, Census API can be used without a key for basic queries
    url = f"{CENSUS_URL}?get={vars_str}&for=zip%20code%20tabulation%20area:{zipcode}"
    
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        
        if len(data) < 2:
            return None
        
        # First row is headers, second is data
        headers = data[0]
        values = data[1]
        
        result = {}
        for i, var in enumerate(headers):
            if var in VARS:
                label = VARS[var]
                try:
                    result[label] = int(values[i])
                except:
                    result[label] = 0
        
        # Calculate derived metrics
        pop = result.get("total_population", 0)
        if pop > 0:
            result["poverty_rate"] = round(result.get("poverty_count", 0) / pop * 100, 1)
            result["bachelors_plus"] = result.get("bachelors_degree_count", 0) + result.get("masters_degree_count", 0) + result.get("professional_degree_count", 0) + result.get("doctorate_degree_count", 0)
            result["college_rate"] = round(result["bachelors_plus"] / pop * 100, 1) if pop > 0 else 0
            result["white_pct"] = round(result.get("white_population", 0) / pop * 100, 1)
            result["black_pct"] = round(result.get("black_population", 0) / pop * 100, 1)
            result["asian_pct"] = round(result.get("asian_population", 0) / pop * 100, 1)
        
        return result
    except Exception as e:
        return {"error": str(e)}

# Test with a few well-known zip codes
test_zips = ["92630", "60021", "75201", "10001", "30303"]  # Lake Forest, South Barrington, Dallas, NYC, Atlanta
for z in test_zips:
    print(f"\n=== ZIP {z} ===")
    d = get_zip_demographics(z)
    if d:
        if "error" in d:
            print(f"  Error: {d['error']}")
        else:
            print(f"  Population: {d.get('total_population', 0):,}")
            print(f"  Median Income: ${d.get('median_household_income', 0):,}")
            print(f"  Median Home Value: ${d.get('median_home_value', 0):,}")
            print(f"  Poverty Rate: {d.get('poverty_rate', 0)}%")
            print(f"  College Degree+: {d.get('college_rate', 0)}%")
            print(f"  White: {d.get('white_pct', 0)}% / Black: {d.get('black_pct', 0)}% / Asian: {d.get('asian_pct', 0)}%")
