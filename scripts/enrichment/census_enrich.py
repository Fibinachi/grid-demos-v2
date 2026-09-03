"""
Simple sequential census enrichment - no threading, no complexity.
"""
import urllib.request, json, sqlite3, time, os

KEY = "2159d6ade3d596371c9333d6118d1ef2f9342cf4"
SUBJECT = "https://api.census.gov/data/2022/acs/acs5/subject"
DETAIL = "https://api.census.gov/data/2022/acs/acs5"

DB = "/home/ec2-user/grantwizard/churches.db"

S_VARS = "S1901_C01_012E,S1901_C01_013E,S1501_C01_006E,S1501_C01_007E,S1501_C01_005E,S0101_C01_001E,S0101_C02_001E,S0101_C01_022E,S0101_C01_006E,S0101_C01_014E,S1701_C01_001E,S1701_C02_001E,S2501_C01_001E,S2502_C01_001E,S2502_C01_002E,S2501_C01_008E,S2301_C01_001E,S2301_C02_001E,S2301_C03_001E,S2301_C04_001E,S2301_C05_001E,S2101_C01_001E,S2101_C02_001E,S1810_C01_001E,S1810_C02_001E,S2801_C01_001E,S2801_C02_001E,S2801_C03_001E,S1101_C01_001E,S1101_C01_002E,S1101_C02_001E,S1101_C03_001E,S1101_C04_001E,S1101_C05_001E,S0101_C01_002E,S0101_C01_003E,S2201_C01_001E,S2201_C02_001E,S2701_C01_001E,S2701_C02_001E,S2701_C03_001E,S2506_C01_001E,S2506_C01_002E,S2506_C01_003E,S0801_C01_001E,S0801_C02_001E,S0801_C03_001E,S0801_C04_001E,S0801_C05_001E,S0801_C06_001E,S0801_C07_001E,S0802_C01_001E"
D_VARS = "B02001_001E,B02001_002E,B02001_003E,B02001_004E,B02001_005E,B02001_006E,B02001_007E,B02001_008E,B03003_001E,B03003_003E"

S_NAMES = "median_hh_income,mean_hh_income,pct_bachelors,pct_graduate,pct_some_college,total_pop,median_age,pct_65plus,pct_18_34,pct_35_54,poverty_total,poverty_count,total_housing,owner_pct,renter_pct,vacancy_pct,emp_total_16plus,labor_force_pct,employed_pct,unemployed_pct,not_in_lf_pct,veteran_total,veteran_pct,disability_total,disability_pct,internet_total,net_sub_pct,net_bb_pct,hh_total,avg_hh_size,married_pct,male_hh_pct,female_hh_pct,single_parent_pct,male_pop,female_pop,snap_total,snap_pct,ins_total,insured_pct,uninsured_pct,med_home_val,med_home_val_mort,med_home_val_nomort,commute_total,drove_alone_pct,carpool_pct,transit_pct,walked_pct,other_pct,wfh_pct,mean_commute_min"
D_NAMES = "race_total,white_pop,black_pop,native_pop,asian_pop,pac_islander_pop,other_race_pop,two_plus_race_pop,hisp_total,hisp_pop"

S_LIST = S_VARS.split(",")
D_LIST = D_VARS.split(",")
S_NAME_LIST = S_NAMES.split(",")
D_NAME_LIST = D_NAMES.split(",")

def fetch_zip(zipcode):
    result = {}
    for base_url, varlist, namelist, label in [(SUBJECT, S_LIST, S_NAME_LIST, "S"), (DETAIL, D_LIST, D_NAME_LIST, "D")]:
        url = f"{base_url}?get=NAME,{','.join(varlist)}&for=zip+code+tabulation+area:{zipcode}&key={KEY}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            if len(data) >= 2:
                for i, var in enumerate(varlist):
                    if i < len(data[1]):
                        val = data[1][i + 1]
                        if val and val != "null" and val != "*********":
                            val = val.replace(",", "")
                            try:
                                result[namelist[i]] = int(float(val)) if "." in val else int(val)
                            except:
                                result[namelist[i]] = val
        except:
            pass
    return result

def derive(data, pop):
    if pop and pop > 0:
        for k in ["white_pop","black_pop","asian_pop","native_pop","pac_islander_pop","two_plus_race_pop"]:
            v = data.get(k, 0) or 0
            data[k.replace("_pop","_pct")] = round(v / pop * 100, 1)
        h = data.get("hisp_pop", 0) or 0
        data["hisp_pct"] = round(h / pop * 100, 1)
        p = data.get("poverty_count", 0) or 0
        data["poverty_rate"] = round(p / pop * 100, 1)
    return data

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    cur.execute("SELECT DISTINCT substr(zip,1,5) FROM churches WHERE zip != '' AND zip IS NOT NULL AND substr(zip,1,5) GLOB '[0-9][0-9][0-9][0-9][0-9]' AND substr(zip,1,5) != '00000'")
    zips = [r[0] for r in cur.fetchall()]
    zips = sorted(set(zips))
    total = len(zips)
    print(f"Found {total} ZIPs")
    
    all_cols = S_NAME_LIST + D_NAME_LIST + ["white_pct","black_pct","asian_pct","native_pct","pac_islander_pct","two_plus_race_pct","hisp_pct","poverty_rate"]
    for col in all_cols:
        try:
            cur.execute(f"ALTER TABLE churches ADD COLUMN census_{col} TEXT DEFAULT ''")
        except:
            pass
    
    t0 = time.time()
    for i, z in enumerate(zips):
        data = fetch_zip(z)
        pop = data.get("total_pop", 0) or 0
        data = derive(data, pop)
        
        sets = []
        params = []
        for k, v in data.items():
            if v is not None and v != "":
                sets.append(f"census_{k}=?")
                params.append(str(v))
        
        if sets:
            params.append(z)
            cur.execute(f"UPDATE churches SET {','.join(sets)} WHERE substr(zip,1,5)=?", params)
        
        if i > 0 and i % 1000 == 0:
            conn.commit()
            elapsed = time.time() - t0
            rate = i / elapsed
            eta = (total - i) / rate if rate > 0 else 0
            print(f"  {i}/{total} ({rate:.0f}/s, ETA {eta:.0f}s)")
    
    conn.commit()
    elapsed = time.time() - t0
    print(f"Done: {total} ZIPs in {elapsed:.0f}s ({total/elapsed:.0f}/s)")

if __name__ == "__main__":
    main()
