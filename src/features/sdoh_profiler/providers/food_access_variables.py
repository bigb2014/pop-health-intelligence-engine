"""USDA Food Access Research Atlas — variable definitions reference.

This file maps every field in the Food Access Research Atlas to its
human-readable name and description. Used by the UI to explain data
fields to users and by the ingestion scripts to validate column mappings.

Source: 2019 VariableLookup.csv (148 variables)
Older datasets (2006, 2010, 2015) have similar but not identical columns.

Format: field_code → (long_name, description)
"""

FOOD_ACCESS_VARIABLES_2019: dict[str, tuple[str, str]] = {
    "CensusTract": ("Census tract", "Census tract number (11-digit FIPS)"),
    "State": ("State", "State name"),
    "County": ("County", "County name"),
    "Urban": ("Urban tract", "Flag for urban tract"),
    "POP2010": ("Population, tract total", "Population count from 2010 census"),
    "OHU2010": ("Housing units, total", "Occupied housing unit count from 2010 census"),
    "GroupQuartersFlag": ("Group quarters, tract with high share", "Flag for tract where >=67%"),
    "NUMGQTRS": ("Group quarters, tract population residing in, number", "Count of tract population residing in group quarters"),
    "PCTGQTRS": ("Group quarters, tract population residing in, share", "Percent of tract population residing in group quarters"),
    # --- Food Desert Flags (the key fields for our engine) ---
    "LILATracts_1And10": ("Low income and low access tract at 1/10 miles", "Flag for low-income and low access at 1 mile urban, 10 miles rural"),
    "LILATracts_halfAnd10": ("Low income and low access tract at 1/2/10 miles", "Flag for low-income and low access at 1/2 mile urban, 10 miles rural"),
    "LILATracts_1And20": ("Low income and low access tract at 1/2/20 miles", "Flag for low-income and low access at 1 mile urban, 20 miles rural"),
    "LILATracts_Vehicle": ("Low income and low access tract using vehicle access", "Flag for low-income and low access considering vehicle access or 20 miles"),
    "HUNVFlag": ("Vehicle access, tract with low vehicle access", "Flag for tract where >=100 households do not have a vehicle and beyond 1/2 mile from supermarket"),
    "LowIncomeTracts": ("Low income tract", "Flag for low income tract"),
    "PovertyRate": ("Tract poverty rate", "Share of the tract population living at or below Federal poverty level"),
    "MedianFamilyIncome": ("Tract median family income", "Tract median family income"),
    # --- Low Access Flags ---
    "LA1and10": ("Low access tract at 1/10 miles", "Flag for low access at 1 mile urban or 10 miles rural"),
    "LAhalfand10": ("Low access tract at 1/2/10 miles", "Flag for low access at 1/2 mile urban or 10 miles rural"),
    "LA1and20": ("Low access tract at 1/2/20 miles", "Flag for low access at 1 mile urban or 20 miles rural"),
    "LATracts_half": ("Low access tract at 1/2 mile", "Flag for low access at 1/2 mile distance"),
    "LATracts1": ("Low access tract at 1 mile", "Flag for low access at 1 mile distance"),
    "LATracts10": ("Low access tract at 10 miles", "Flag for low access at 10 mile distance"),
    "LATracts20": ("Low access tract at 20 miles", "Flag for low access at 20 mile distance"),
    "LATractsVehicle_20": ("Low access tract using vehicle access and 20 miles", "Flag for tract with low vehicle access and beyond 1/2 mile, or beyond 20 miles"),
    # --- Population Counts (by distance and demographic) ---
    "lapophalf": ("Low access population at 1/2 mile, number", "Population count beyond 1/2 mile from supermarket"),
    "lapophalfshare": ("Low access population at 1/2 mile, share", "Share of tract population beyond 1/2 mile from supermarket"),
    "lalowihalf": ("Low access low-income population at 1/2 mile, number", "Low income population beyond 1/2 mile from supermarket"),
    "lalowihalfshare": ("Low access low-income population at 1/2 mile, share", "Share of low income population beyond 1/2 mile"),
    "lakidshalf": ("Low access children age 0-17 at 1/2 mile, number", "Kids population beyond 1/2 mile from supermarket"),
    "lakidshalfshare": ("Low access children at 1/2 mile, share", "Share of tract population that are kids beyond 1/2 mile"),
    "laseniorshalf": ("Low access seniors age 65+ at 1/2 mile, number", "Seniors population beyond 1/2 mile from supermarket"),
    "laseniorshalfshare": ("Low access seniors at 1/2 mile, share", "Share of tract population that are seniors beyond 1/2 mile"),
    # --- Demographic Breakdowns at 1/2 mile ---
    "lawhitehalf": ("Low access White population at 1/2 mile, number", "White population beyond 1/2 mile"),
    "lablackhalf": ("Low access Black population at 1/2 mile, number", "Black/African American population beyond 1/2 mile"),
    "laasianhalf": ("Low access Asian population at 1/2 mile, number", "Asian population beyond 1/2 mile"),
    "lanhopihalf": ("Low access Native Hawaiian/Other Pacific Islander at 1/2 mile, number", "NHOPI population beyond 1/2 mile"),
    "laaianhalf": ("Low access American Indian/Alaska Native at 1/2 mile, number", "AIAN population beyond 1/2 mile"),
    "laomultirhalf": ("Low access Other/multiracial at 1/2 mile, number", "Other/multiracial population beyond 1/2 mile"),
    "lahisphalf": ("Low access Hispanic population at 1/2 mile, number", "Hispanic population beyond 1/2 mile"),
    "lahunvhalf": ("Low access households with no vehicle at 1/2 mile, number", "Households without vehicle beyond 1/2 mile"),
    "lasnaphalf": ("Low access SNAP recipients at 1/2 mile, number", "SNAP recipients beyond 1/2 mile from supermarket"),
    # --- Tract Totals ---
    "TractLOWI": ("Tract low-income population, total", "Total low-income population in tract"),
    "TractKids": ("Tract children age 0-17, total", "Total children in tract"),
    "TractSeniors": ("Tract seniors age 65+, total", "Total seniors in tract"),
    "TractWhite": ("Tract White population, total", "Total White population in tract"),
    "TractBlack": ("Tract Black population, total", "Total Black/African American population in tract"),
    "TractAsian": ("Tract Asian population, total", "Total Asian population in tract"),
    "TractNHOPI": ("Tract NHOPI population, total", "Total Native Hawaiian/Other Pacific Islander in tract"),
    "TractAIAN": ("Tract AIAN population, total", "Total American Indian/Alaska Native in tract"),
    "TractOMultir": ("Tract Other/multiracial population, total", "Total other/multiracial in tract"),
    "TractHispanic": ("Tract Hispanic population, total", "Total Hispanic population in tract"),
    "TractHUNV": ("Tract households with no vehicle, total", "Total households without vehicle in tract"),
    "TractSNAP": ("Tract SNAP recipients, total", "Total SNAP recipients in tract"),
}

# Available datasets by year
DATASETS = {
    2006: {
        "name": "Food Desert Locator (archived)",
        "folder": "Archived_2006_Food_Desert_Locator",
        "filename": "FoodDesertLocatorData2006.xls",
        "format": "xls",
        "doc": "FoodDesertLocatorDocumentation2006.pdf",
        "notes": "Original Food Desert Locator — predecessor to Food Access Research Atlas. Different variable definitions.",
    },
    2010: {
        "name": "Food Access Research Atlas 2010",
        "folder": "2010_Food_Access_Research_Atlas",
        "filename": "FoodAccessResearchAtlasData2010.xlsx",
        "format": "xlsx",
        "doc": "FoodAccessResearchAtlasDocumentation2010.pdf",
        "notes": "Based on 2010 Census tract data.",
    },
    2015: {
        "name": "Food Access Research Atlas 2015",
        "folder": "2015_Food_Access_Research_Atlas",
        "filename": "FoodAccessResearchAtlasData2015.xlsx",
        "format": "xlsx",
        "doc": "FoodAccessResearchAtlasDocumentation2015.pdf",
        "notes": "Based on 2010 Census tracts with 2015 supermarket data.",
    },
    2019: {
        "name": "Food Access Research Atlas 2019",
        "folder": "2019_Food_Access_Research_Atlas_Data",
        "filename": "Food Access Research Atlas.csv",
        "format": "csv",
        "doc": None,
        "notes": "Latest release (April 2021, using 2019 data). Includes VariableLookup.csv and ReadMe.csv.",
    },
}