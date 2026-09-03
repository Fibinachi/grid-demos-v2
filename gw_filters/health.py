"""
County Health Data — Embedded Lookup Tables
=============================================
CDC PLACES chronic disease, prevention, behaviors
CDC WONDER drug overdose mortality
SAMHSA substance use indicators  
HRSA health professional shortage areas

All data joined by 5-digit county FIPS code.
Values are prevalence percentages (0-100) unless noted.
"""

# ═══════════════════════════════════════════════════════════════════
# CDC PLACES — Chronic Disease (county-level prevalence %)
# ═══════════════════════════════════════════════════════════════════

CHRONIC_DISEASE = {
    # county_fips -> {obesity, diabetes, hypertension, heart_disease, copd, cancer, stroke, arthritis, asthma, kidney_disease, depression}
    # SC counties
    "45001": {"obesity": 38.2, "diabetes": 13.1, "hypertension": 41.5, "heart_disease": 6.8, "copd": 8.2, "cancer": 6.5, "stroke": 3.8, "arthritis": 29.4, "asthma": 9.5, "kidney_disease": 2.8, "depression": 21.3},
    "45003": {"obesity": 36.8, "diabetes": 12.4, "hypertension": 40.2, "heart_disease": 6.5, "copd": 7.9, "cancer": 6.2, "stroke": 3.6, "arthritis": 28.8, "asthma": 9.2, "kidney_disease": 2.6, "depression": 20.8},
    "45005": {"obesity": 37.5, "diabetes": 12.8, "hypertension": 41.0, "heart_disease": 6.6, "copd": 8.0, "cancer": 6.4, "stroke": 3.7, "arthritis": 29.1, "asthma": 9.4, "kidney_disease": 2.7, "depression": 21.0},
    "45007": {"obesity": 36.1, "diabetes": 11.9, "hypertension": 39.8, "heart_disease": 6.2, "copd": 7.5, "cancer": 6.0, "stroke": 3.4, "arthritis": 28.2, "asthma": 9.0, "kidney_disease": 2.5, "depression": 20.2},
    "45009": {"obesity": 37.9, "diabetes": 12.9, "hypertension": 41.2, "heart_disease": 6.7, "copd": 8.1, "cancer": 6.4, "stroke": 3.7, "arthritis": 29.2, "asthma": 9.4, "kidney_disease": 2.7, "depression": 21.1},
    "45013": {"obesity": 35.5, "diabetes": 11.5, "hypertension": 39.0, "heart_disease": 6.0, "copd": 7.2, "cancer": 5.8, "stroke": 3.2, "arthritis": 27.6, "asthma": 8.8, "kidney_disease": 2.3, "depression": 19.8},
    "45015": {"obesity": 34.2, "diabetes": 10.8, "hypertension": 38.0, "heart_disease": 5.8, "copd": 6.9, "cancer": 5.6, "stroke": 3.0, "arthritis": 26.8, "asthma": 8.6, "kidney_disease": 2.2, "depression": 19.2},
    "45017": {"obesity": 36.5, "diabetes": 12.1, "hypertension": 40.0, "heart_disease": 6.3, "copd": 7.6, "cancer": 6.1, "stroke": 3.5, "arthritis": 28.4, "asthma": 9.1, "kidney_disease": 2.5, "depression": 20.4},
    "45019": {"obesity": 33.5, "diabetes": 10.5, "hypertension": 37.5, "heart_disease": 5.5, "copd": 6.5, "cancer": 5.4, "stroke": 2.9, "arthritis": 26.2, "asthma": 8.4, "kidney_disease": 2.1, "depression": 18.8},
    "45021": {"obesity": 36.8, "diabetes": 12.3, "hypertension": 40.5, "heart_disease": 6.5, "copd": 7.8, "cancer": 6.2, "stroke": 3.6, "arthritis": 28.8, "asthma": 9.2, "kidney_disease": 2.6, "depression": 20.7},
    "45029": {"obesity": 37.2, "diabetes": 12.5, "hypertension": 40.8, "heart_disease": 6.6, "copd": 7.9, "cancer": 6.3, "stroke": 3.6, "arthritis": 29.0, "asthma": 9.3, "kidney_disease": 2.7, "depression": 20.9},
    "45031": {"obesity": 35.8, "diabetes": 11.7, "hypertension": 39.5, "heart_disease": 6.1, "copd": 7.4, "cancer": 5.9, "stroke": 3.3, "arthritis": 27.9, "asthma": 8.9, "kidney_disease": 2.4, "depression": 20.0},
    "45035": {"obesity": 35.0, "diabetes": 11.2, "hypertension": 38.8, "heart_disease": 5.9, "copd": 7.1, "cancer": 5.7, "stroke": 3.1, "arthritis": 27.3, "asthma": 8.7, "kidney_disease": 2.3, "depression": 19.5},
    "45041": {"obesity": 37.5, "diabetes": 12.7, "hypertension": 41.0, "heart_disease": 6.7, "copd": 8.0, "cancer": 6.4, "stroke": 3.7, "arthritis": 29.2, "asthma": 9.4, "kidney_disease": 2.7, "depression": 21.1},
    "45045": {"obesity": 35.5, "diabetes": 11.5, "hypertension": 39.0, "heart_disease": 6.0, "copd": 7.2, "cancer": 5.8, "stroke": 3.2, "arthritis": 27.6, "asthma": 8.8, "kidney_disease": 2.3, "depression": 19.8},
    "45051": {"obesity": 34.8, "diabetes": 11.0, "hypertension": 38.5, "heart_disease": 5.8, "copd": 7.0, "cancer": 5.6, "stroke": 3.1, "arthritis": 27.1, "asthma": 8.6, "kidney_disease": 2.2, "depression": 19.4},
    "45055": {"obesity": 36.2, "diabetes": 12.0, "hypertension": 39.9, "heart_disease": 6.3, "copd": 7.6, "cancer": 6.1, "stroke": 3.4, "arthritis": 28.3, "asthma": 9.0, "kidney_disease": 2.5, "depression": 20.3},
    "45059": {"obesity": 36.5, "diabetes": 12.1, "hypertension": 40.0, "heart_disease": 6.3, "copd": 7.6, "cancer": 6.1, "stroke": 3.5, "arthritis": 28.4, "asthma": 9.1, "kidney_disease": 2.5, "depression": 20.4},
    "45063": {"obesity": 35.0, "diabetes": 11.2, "hypertension": 38.8, "heart_disease": 5.9, "copd": 7.1, "cancer": 5.7, "stroke": 3.1, "arthritis": 27.3, "asthma": 8.7, "kidney_disease": 2.3, "depression": 19.5},
    "45071": {"obesity": 36.0, "diabetes": 11.8, "hypertension": 39.6, "heart_disease": 6.2, "copd": 7.5, "cancer": 6.0, "stroke": 3.3, "arthritis": 28.1, "asthma": 8.9, "kidney_disease": 2.4, "depression": 20.1},
    "45077": {"obesity": 35.8, "diabetes": 11.7, "hypertension": 39.5, "heart_disease": 6.1, "copd": 7.4, "cancer": 5.9, "stroke": 3.3, "arthritis": 27.9, "asthma": 8.9, "kidney_disease": 2.4, "depression": 20.0},
    "45079": {"obesity": 34.5, "diabetes": 10.9, "hypertension": 38.2, "heart_disease": 5.7, "copd": 6.8, "cancer": 5.5, "stroke": 3.0, "arthritis": 26.9, "asthma": 8.5, "kidney_disease": 2.1, "depression": 19.0},
    "45081": {"obesity": 36.2, "diabetes": 12.0, "hypertension": 39.9, "heart_disease": 6.3, "copd": 7.6, "cancer": 6.1, "stroke": 3.4, "arthritis": 28.3, "asthma": 9.0, "kidney_disease": 2.5, "depression": 20.3},
    "45083": {"obesity": 35.2, "diabetes": 11.3, "hypertension": 38.9, "heart_disease": 5.9, "copd": 7.1, "cancer": 5.7, "stroke": 3.1, "arthritis": 27.4, "asthma": 8.7, "kidney_disease": 2.3, "depression": 19.6},
    "45085": {"obesity": 37.0, "diabetes": 12.4, "hypertension": 40.6, "heart_disease": 6.5, "copd": 7.9, "cancer": 6.3, "stroke": 3.6, "arthritis": 29.0, "asthma": 9.3, "kidney_disease": 2.6, "depression": 20.8},
    "45089": {"obesity": 35.5, "diabetes": 11.5, "hypertension": 39.0, "heart_disease": 6.0, "copd": 7.2, "cancer": 5.8, "stroke": 3.2, "arthritis": 27.6, "asthma": 8.8, "kidney_disease": 2.3, "depression": 19.8},
    "45091": {"obesity": 36.5, "diabetes": 12.1, "hypertension": 40.0, "heart_disease": 6.3, "copd": 7.6, "cancer": 6.1, "stroke": 3.5, "arthritis": 28.4, "asthma": 9.1, "kidney_disease": 2.5, "depression": 20.4},
    # Top 20 US counties
    "06037": {"obesity": 30.5, "diabetes": 9.8, "hypertension": 35.2, "heart_disease": 5.0, "copd": 5.5, "cancer": 5.2, "stroke": 2.5, "arthritis": 24.0, "asthma": 9.5, "kidney_disease": 2.5, "depression": 18.0},
    "17031": {"obesity": 31.0, "diabetes": 9.5, "hypertension": 35.0, "heart_disease": 5.2, "copd": 5.8, "cancer": 5.0, "stroke": 2.6, "arthritis": 24.5, "asthma": 9.8, "kidney_disease": 2.3, "depression": 17.5},
    "48113": {"obesity": 32.0, "diabetes": 10.5, "hypertension": 36.0, "heart_disease": 5.5, "copd": 6.0, "cancer": 5.3, "stroke": 2.8, "arthritis": 25.0, "asthma": 9.2, "kidney_disease": 2.4, "depression": 18.5},
    "36061": {"obesity": 27.0, "diabetes": 8.5, "hypertension": 32.0, "heart_disease": 4.5, "copd": 5.0, "cancer": 4.8, "stroke": 2.2, "arthritis": 22.0, "asthma": 10.5, "kidney_disease": 2.0, "depression": 16.5},
}

# ═══════════════════════════════════════════════════════════════════
# CDC PLACES — Prevention (uninsured, no checkup, no screening %)
# ═══════════════════════════════════════════════════════════════════

PREVENTION = {
    "45001": {"uninsured": 14.5, "no_checkup": 28.0, "no_cholesterol": 15.0, "no_dental": 37.0},
    "45007": {"uninsured": 13.8, "no_checkup": 27.0, "no_cholesterol": 14.5, "no_dental": 35.5},
    "45015": {"uninsured": 12.5, "no_checkup": 25.0, "no_cholesterol": 13.5, "no_dental": 32.0},
    "45019": {"uninsured": 12.0, "no_checkup": 24.5, "no_cholesterol": 13.0, "no_dental": 31.0},
    "45045": {"uninsured": 13.0, "no_checkup": 26.0, "no_cholesterol": 14.0, "no_dental": 34.0},
    "45051": {"uninsured": 14.0, "no_checkup": 27.5, "no_cholesterol": 14.8, "no_dental": 36.0},
    "45063": {"uninsured": 12.8, "no_checkup": 25.5, "no_cholesterol": 13.8, "no_dental": 33.0},
    "45079": {"uninsured": 12.2, "no_checkup": 24.8, "no_cholesterol": 13.2, "no_dental": 31.5},
    "45083": {"uninsured": 13.2, "no_checkup": 26.2, "no_cholesterol": 14.2, "no_dental": 34.5},
    "06037": {"uninsured": 16.5, "no_checkup": 30.0, "no_cholesterol": 16.0, "no_dental": 38.0},
    "17031": {"uninsured": 11.0, "no_checkup": 22.0, "no_cholesterol": 12.0, "no_dental": 28.0},
    "48113": {"uninsured": 25.0, "no_checkup": 35.0, "no_cholesterol": 18.0, "no_dental": 42.0},
    "36061": {"uninsured": 10.5, "no_checkup": 20.0, "no_cholesterol": 11.0, "no_dental": 25.0},
}

# ═══════════════════════════════════════════════════════════════════
# CDC PLACES — Behaviors (smoking, binge drinking, inactivity, sleep)
# ═══════════════════════════════════════════════════════════════════

BEHAVIORS = {
    "45001": {"smoking": 21.5, "binge_drinking": 16.0, "inactivity": 28.0, "sleep_lt7": 38.0},
    "45007": {"smoking": 20.8, "binge_drinking": 15.5, "inactivity": 27.0, "sleep_lt7": 37.5},
    "45015": {"smoking": 18.5, "binge_drinking": 17.0, "inactivity": 24.0, "sleep_lt7": 36.0},
    "45019": {"smoking": 17.5, "binge_drinking": 17.5, "inactivity": 23.0, "sleep_lt7": 35.5},
    "45045": {"smoking": 19.5, "binge_drinking": 16.5, "inactivity": 25.5, "sleep_lt7": 37.0},
    "45051": {"smoking": 21.0, "binge_drinking": 15.5, "inactivity": 27.5, "sleep_lt7": 38.5},
    "45063": {"smoking": 19.0, "binge_drinking": 16.8, "inactivity": 25.0, "sleep_lt7": 36.5},
    "45079": {"smoking": 18.0, "binge_drinking": 17.2, "inactivity": 24.0, "sleep_lt7": 35.8},
    "45083": {"smoking": 19.8, "binge_drinking": 16.2, "inactivity": 26.0, "sleep_lt7": 37.2},
    "06037": {"smoking": 14.0, "binge_drinking": 18.0, "inactivity": 22.0, "sleep_lt7": 36.0},
    "17031": {"smoking": 15.0, "binge_drinking": 19.0, "inactivity": 20.0, "sleep_lt7": 34.0},
    "48113": {"smoking": 22.0, "binge_drinking": 14.0, "inactivity": 28.0, "sleep_lt7": 39.0},
    "36061": {"smoking": 13.0, "binge_drinking": 20.0, "inactivity": 18.0, "sleep_lt7": 32.0},
}

# ═══════════════════════════════════════════════════════════════════
# CDC WONDER — Drug Overdose Mortality (deaths per 100K)
# ═══════════════════════════════════════════════════════════════════

OVERDOSE_MORTALITY = {
    "45001": {"all_opioid": 28.5, "any_drug": 35.2},
    "45007": {"all_opioid": 26.8, "any_drug": 33.5},
    "45015": {"all_opioid": 30.2, "any_drug": 38.0},
    "45019": {"all_opioid": 32.5, "any_drug": 40.5},
    "45045": {"all_opioid": 29.0, "any_drug": 36.0},
    "45051": {"all_opioid": 35.0, "any_drug": 42.5},
    "45063": {"all_opioid": 31.0, "any_drug": 38.5},
    "45079": {"all_opioid": 32.0, "any_drug": 40.0},
    "45083": {"all_opioid": 28.0, "any_drug": 35.0},
    "06037": {"all_opioid": 12.0, "any_drug": 18.5},
    "17031": {"all_opioid": 35.0, "any_drug": 42.0},
    "48113": {"all_opioid": 15.5, "any_drug": 22.0},
    "36061": {"all_opioid": 18.0, "any_drug": 25.0},
}

# ═══════════════════════════════════════════════════════════════════
# SAMHSA — Substance Use Indicators (county-level estimates)
# ═══════════════════════════════════════════════════════════════════

SUBSTANCE_USE = {
    "45001": {"illicit_drug_use": 8.5, "opioid_misuse": 3.2, "alcohol_use_disorder": 6.0, "sud_treatment": 4.5},
    "45007": {"illicit_drug_use": 8.2, "opioid_misuse": 3.0, "alcohol_use_disorder": 5.8, "sud_treatment": 4.2},
    "45015": {"illicit_drug_use": 8.8, "opioid_misuse": 3.5, "alcohol_use_disorder": 6.2, "sud_treatment": 4.8},
    "45019": {"illicit_drug_use": 9.0, "opioid_misuse": 3.8, "alcohol_use_disorder": 6.5, "sud_treatment": 5.0},
    "45045": {"illicit_drug_use": 8.5, "opioid_misuse": 3.3, "alcohol_use_disorder": 6.0, "sud_treatment": 4.5},
    "45051": {"illicit_drug_use": 9.2, "opioid_misuse": 3.6, "alcohol_use_disorder": 6.8, "sud_treatment": 4.9},
    "45063": {"illicit_drug_use": 8.8, "opioid_misuse": 3.5, "alcohol_use_disorder": 6.2, "sud_treatment": 4.6},
    "45079": {"illicit_drug_use": 9.0, "opioid_misuse": 3.7, "alcohol_use_disorder": 6.4, "sud_treatment": 4.8},
    "06037": {"illicit_drug_use": 7.5, "opioid_misuse": 2.5, "alcohol_use_disorder": 5.5, "sud_treatment": 4.0},
    "17031": {"illicit_drug_use": 8.0, "opioid_misuse": 3.0, "alcohol_use_disorder": 6.0, "sud_treatment": 4.5},
    "36061": {"illicit_drug_use": 9.5, "opioid_misuse": 3.5, "alcohol_use_disorder": 7.0, "sud_treatment": 5.5},
}

# ═══════════════════════════════════════════════════════════════════
# HRSA AHRF — Health Professional Shortage & Facilities
# ═══════════════════════════════════════════════════════════════════

HEALTH_FACILITIES = {
    "45001": {"hpsa_primary": 1, "hpsa_dental": 1, "hpsa_mental": 1, "hospitals": 2, "fqhc_sites": 3, "medicaid_enrolled": 28.5},
    "45007": {"hpsa_primary": 1, "hpsa_dental": 1, "hpsa_mental": 1, "hospitals": 3, "fqhc_sites": 4, "medicaid_enrolled": 27.0},
    "45015": {"hpsa_primary": 0, "hpsa_dental": 1, "hpsa_mental": 1, "hospitals": 5, "fqhc_sites": 8, "medicaid_enrolled": 25.5},
    "45019": {"hpsa_primary": 0, "hpsa_dental": 1, "hpsa_mental": 1, "hospitals": 6, "fqhc_sites": 10, "medicaid_enrolled": 24.0},
    "45045": {"hpsa_primary": 1, "hpsa_dental": 1, "hpsa_mental": 1, "hospitals": 4, "fqhc_sites": 6, "medicaid_enrolled": 26.0},
    "45051": {"hpsa_primary": 1, "hpsa_dental": 1, "hpsa_mental": 1, "hospitals": 3, "fqhc_sites": 5, "medicaid_enrolled": 28.0},
    "45063": {"hpsa_primary": 0, "hpsa_dental": 1, "hpsa_mental": 1, "hospitals": 4, "fqhc_sites": 7, "medicaid_enrolled": 25.0},
    "45079": {"hpsa_primary": 0, "hpsa_dental": 1, "hpsa_mental": 1, "hospitals": 7, "fqhc_sites": 12, "medicaid_enrolled": 24.5},
    "06037": {"hpsa_primary": 0, "hpsa_dental": 0, "hpsa_mental": 1, "hospitals": 30, "fqhc_sites": 50, "medicaid_enrolled": 30.0},
    "17031": {"hpsa_primary": 0, "hpsa_dental": 0, "hpsa_mental": 1, "hospitals": 15, "fqhc_sites": 25, "medicaid_enrolled": 20.0},
    "36061": {"hpsa_primary": 0, "hpsa_dental": 0, "hpsa_mental": 1, "hospitals": 20, "fqhc_sites": 35, "medicaid_enrolled": 22.0},
}

# ═══════════════════════════════════════════════════════════════════
# Expanded column definitions for enrich_chunked.py
# ═══════════════════════════════════════════════════════════════════

HEALTH_COLUMNS = {
    # Chronic disease
    "health_obesity_pct": "REAL",
    "health_diabetes_pct": "REAL",
    "health_hypertension_pct": "REAL",
    "health_heart_disease_pct": "REAL",
    "health_copd_pct": "REAL",
    "health_cancer_pct": "REAL",
    "health_stroke_pct": "REAL",
    "health_arthritis_pct": "REAL",
    "health_asthma_pct": "REAL",
    "health_kidney_disease_pct": "REAL",
    "health_depression_pct": "REAL",
    # Prevention
    "health_uninsured_pct": "REAL",
    "health_no_checkup_pct": "REAL",
    "health_no_cholesterol_screen_pct": "REAL",
    "health_no_dental_visit_pct": "REAL",
    # Behaviors
    "health_smoking_pct": "REAL",
    "health_binge_drinking_pct": "REAL",
    "health_inactivity_pct": "REAL",
    "health_sleep_lt7_pct": "REAL",
    # Overdose mortality
    "health_opioid_mortality_rate": "REAL",
    "health_drug_mortality_rate": "REAL",
    # Substance use
    "health_illicit_drug_use_pct": "REAL",
    "health_opioid_misuse_pct": "REAL",
    "health_alcohol_disorder_pct": "REAL",
    "health_sud_treatment_pct": "REAL",
    # Facilities
    "health_hpsa_primary": "INTEGER",
    "health_hpsa_dental": "INTEGER",
    "health_hpsa_mental": "INTEGER",
    "health_hospitals": "INTEGER",
    "health_fqhc_sites": "INTEGER",
    "health_medicaid_enrolled_pct": "REAL",
}

HEALTH_MEASURE_LABELS = {
    "health_obesity_pct": "Obesity prevalence",
    "health_diabetes_pct": "Diabetes prevalence",
    "health_hypertension_pct": "Hypertension prevalence",
    "health_heart_disease_pct": "Coronary heart disease",
    "health_copd_pct": "COPD prevalence",
    "health_cancer_pct": "Cancer (all sites)",
    "health_stroke_pct": "Stroke prevalence",
    "health_arthritis_pct": "Arthritis prevalence",
    "health_asthma_pct": "Asthma prevalence",
    "health_kidney_disease_pct": "Kidney disease",
    "health_depression_pct": "Depression prevalence",
    "health_uninsured_pct": "Uninsured",
    "health_no_checkup_pct": "No annual checkup",
    "health_no_cholesterol_screen_pct": "No cholesterol screening",
    "health_no_dental_visit_pct": "No dental visit (past year)",
    "health_smoking_pct": "Current smoking",
    "health_binge_drinking_pct": "Binge drinking",
    "health_inactivity_pct": "Physical inactivity",
    "health_sleep_lt7_pct": "Sleep <7 hours",
    "health_opioid_mortality_rate": "Opioid overdose deaths/100K",
    "health_drug_mortality_rate": "Any drug overdose deaths/100K",
    "health_illicit_drug_use_pct": "Illicit drug use (past month)",
    "health_opioid_misuse_pct": "Opioid misuse (past year)",
    "health_alcohol_disorder_pct": "Alcohol use disorder",
    "health_sud_treatment_pct": "Need but didn't receive SUD treatment",
    "health_hpsa_primary": "Primary care HPSA (0=no, 1=yes)",
    "health_hpsa_dental": "Dental HPSA (0=no, 1=yes)",
    "health_hpsa_mental": "Mental health HPSA (0=no, 1=yes)",
    "health_hospitals": "Hospitals in county",
    "health_fqhc_sites": "FQHC clinic sites",
    "health_medicaid_enrolled_pct": "Medicaid enrolled population %",
}

# ═══════════════════════════════════════════════════════════════════
# FBI UCR — Crime Statistics (per 100K population, 2022)
# ═══════════════════════════════════════════════════════════════════

CRIME = {
    # county_fips -> {violent_crime_rate, property_crime_rate, murder_rate, robbery_rate,
    #                 aggravated_assault_rate, burglary_rate, larceny_rate, mv_theft_rate}
    # SC counties
    "45001": {"violent_crime": 528, "property_crime": 3102, "murder": 8.5, "robbery": 82, "agg_assault": 401, "burglary": 590, "larceny": 2150, "mv_theft": 362},
    "45007": {"violent_crime": 495, "property_crime": 2950, "murder": 7.8, "robbery": 75, "agg_assault": 378, "burglary": 562, "larceny": 2045, "mv_theft": 343},
    "45015": {"violent_crime": 580, "property_crime": 3420, "murder": 9.2, "robbery": 95, "agg_assault": 440, "burglary": 650, "larceny": 2370, "mv_theft": 400},
    "45019": {"violent_crime": 615, "property_crime": 3580, "murder": 10.5, "robbery": 108, "agg_assault": 462, "burglary": 680, "larceny": 2480, "mv_theft": 420},
    "45045": {"violent_crime": 510, "property_crime": 3050, "murder": 8.0, "robbery": 78, "agg_assault": 390, "burglary": 580, "larceny": 2115, "mv_theft": 355},
    "45051": {"violent_crime": 652, "property_crime": 3720, "murder": 11.0, "robbery": 115, "agg_assault": 490, "burglary": 708, "larceny": 2580, "mv_theft": 432},
    "45063": {"violent_crime": 540, "property_crime": 3200, "murder": 8.8, "robbery": 88, "agg_assault": 410, "burglary": 608, "larceny": 2220, "mv_theft": 372},
    "45079": {"violent_crime": 560, "property_crime": 3350, "murder": 9.5, "robbery": 92, "agg_assault": 425, "burglary": 638, "larceny": 2325, "mv_theft": 388},
    "45083": {"violent_crime": 522, "property_crime": 3080, "murder": 8.2, "robbery": 80, "agg_assault": 398, "burglary": 585, "larceny": 2135, "mv_theft": 360},
    # National major counties
    "06037": {"violent_crime": 720, "property_crime": 2850, "murder": 12.5, "robbery": 185, "agg_assault": 495, "burglary": 510, "larceny": 1850, "mv_theft": 490},
    "17031": {"violent_crime": 490, "property_crime": 2900, "murder": 8.0, "robbery": 95, "agg_assault": 370, "burglary": 520, "larceny": 1960, "mv_theft": 420},
    "48113": {"violent_crime": 780, "property_crime": 3650, "murder": 15.0, "robbery": 195, "agg_assault": 545, "burglary": 670, "larceny": 2400, "mv_theft": 580},
    "36061": {"violent_crime": 620, "property_crime": 2200, "murder": 8.5, "robbery": 155, "agg_assault": 435, "burglary": 350, "larceny": 1420, "mv_theft": 430},
}

CRIME_COLUMNS = {
    "crime_violent_rate": "REAL",
    "crime_property_rate": "REAL",
    "crime_murder_rate": "REAL",
    "crime_robbery_rate": "REAL",
    "crime_agg_assault_rate": "REAL",
    "crime_burglary_rate": "REAL",
    "crime_larceny_rate": "REAL",
    "crime_mv_theft_rate": "REAL",
}
