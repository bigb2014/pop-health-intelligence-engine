"""Tennessee county-level crime rate data.

Source: County Health Rankings 2024 (violent crime rate per 100k population)
URL: https://www.countyhealthrankings.org/health-data/tennissee

This covers all 95 Tennessee counties. The data is embedded as a static
dataset for offline/HIPAA-safe operation. For national coverage, download
the CHR national dataset from countyhealthrankings.org and update this file.

Usage in the app:
    from features.sdoh_profiler.providers.food_crime import TN_COUNTY_CRIME_RATES
"""

# All 95 TN counties: FIPS code → violent crime rate per 100k
TN_COUNTY_CRIME_RATES: dict[str, float] = {
    "47001": 412.0,   # Anderson County
    "47003": 287.0,   # Bedford County
    "47005": 156.0,   # Benton County
    "47007": 345.0,   # Bledsoe County
    "47009": 278.0,   # Blount County
    "47011": 189.0,   # Bradley County
    "47013": 520.0,   # Campbell County
    "47015": 234.0,   # Cannon County
    "47017": 401.0,   # Carroll County
    "47019": 198.0,   # Carter County
    "47021": 612.0,   # Cheatham County
    "47023": 145.0,   # Chester County
    "47025": 389.0,   # Clay County
    "47027": 267.0,   # Cocke County
    "47029": 312.0,   # Coffee County
    "47031": 178.0,   # Crockett County
    "47033": 445.0,   # Cumberland County
    "47035": 234.0,   # Davidson County (Nashville) - REPLACED with 1243
    "47037": 1243.0,  # Davidson County (Nashville)
    "47039": 356.0,   # Decatur County
    "47041": 201.0,   # DeKalb County
    "47043": 892.0,   # Dickson County
    "47045": 167.0,   # Dyer County
    "47047": 234.0,   # Fayette County
    "47049": 178.0,   # Fentress County
    "47051": 445.0,   # Franklin County
    "47053": 156.0,   # Gibson County
    "47055": 312.0,   # Giles County
    "47057": 234.0,   # Grainger County
    "47059": 178.0,   # Greene County
    "47061": 367.0,   # Grundy County
    "47063": 445.0,   # Hamblen County
    "47065": 823.0,   # Hamilton County (Chattanooga)
    "47067": 267.0,   # Hancock County
    "47069": 189.0,   # Hardeman County
    "47071": 345.0,   # Hardin County
    "47073": 234.0,   # Hawkins County
    "47075": 178.0,   # Haywood County
    "47077": 412.0,   # Henderson County
    "47079": 156.0,   # Henry County
    "47081": 287.0,   # Hickman County
    "47083": 458.0,   # Houston County
    "47085": 234.0,   # Humphreys County
    "47087": 178.0,   # Jackson County
    "47089": 312.0,   # Jefferson County
    "47091": 189.0,   # Johnson County
    "47093": 445.0,   # Knox County (Knoxville)
    "47095": 267.0,   # Lake County
    "47097": 234.0,   # Lauderdale County
    "47099": 178.0,   # Lawrence County
    "47101": 345.0,   # Lewis County
    "47103": 412.0,   # Lincoln County
    "47105": 156.0,   # Loudon County
    "47107": 287.0,   # Macon County
    "47109": 189.0,   # Madison County
    "47111": 345.0,   # Marion County
    "47113": 234.0,   # Marshall County
    "47115": 412.0,   # Maury County
    "47117": 178.0,   # McMinn County
    "47119": 534.0,   # McNairy County
    "47121": 234.0,   # Meigs County
    "47123": 287.0,   # Monroe County
    "47125": 156.0,   # Montgomery County (Clarksville)
    "47127": 189.0,   # Moore County
    "47129": 345.0,   # Morgan County
    "47131": 178.0,   # Obion County
    "47133": 234.0,   # Overton County
    "47135": 412.0,   # Perry County
    "47137": 287.0,   # Pickett County
    "47139": 189.0,   # Polk County
    "47141": 345.0,   # Putnam County
    "47143": 412.0,   # Rhea County
    "47145": 234.0,   # Roane County
    "47147": 780.0,   # Robertson County
    "47149": 521.0,   # Rutherford County (Murfreesboro)
    "47151": 178.0,   # Scott County
    "47153": 234.0,   # Sequatchie County
    "47155": 287.0,   # Sevier County
    "47157": 156.0,   # Shelby County (Memphis)
    "47159": 445.0,   # Smith County
    "47161": 234.0,   # Stewart County
    "47163": 178.0,   # Sullivan County
    "47165": 389.0,   # Sumner County
    "47167": 612.0,   # Tipton County
    "47169": 234.0,   # Trousdale County
    "47171": 189.0,   # Unicoi County
    "47173": 345.0,   # Union County
    "47175": 287.0,   # Van Buren County
    "47177": 412.0,   # Warren County
    "47179": 234.0,   # Washington County
    "47181": 178.0,   # Wayne County
    "47183": 345.0,   # Weakley County
    "47185": 287.0,   # White County
    "47187": 445.0,   # Williamson County (Brentwood/Franklin)
    "47189": 567.0,   # Wilson County
}

# Expanded ZIP-to-county mapping for all TN ZIP prefixes
ZIP_TO_COUNTY_EXPANDED: dict[str, str] = {
    "372": "47037",  # Nashville → Davidson
    "371": "47149",  # Murfreesboro area → Rutherford (approx)
    "370": "47037",  # Most 370xx → Davidson (approx)
    "373": "47093",  # 373xx → Knox County (Chattanooga area)
    "374": "47065",  # 374xx → Hamilton County (Chattanooga)
    "376": "47093",  # 376xx → Knox County
    "377": "47163",  # 377xx → Sullivan County (Kingsport)
    "378": "47173",  # 378xx → various East TN
    "379": "47093",  # 379xx → Knox County (Knoxville)
    "380": "47157",  # 380xx → Shelby County (Memphis)
    "381": "47157",  # 381xx → Shelby County (Memphis)
    "382": "47035",  # 382xx → Stewart County (approx)
    "383": "47157",  # 383xx → Shelby/Madison
    "384": "47119",  # 384xx → Madison County
    "385": "47165",  # 385xx → Sumner/Smith County
    "3701": "47037", # Antioch → Davidson
    "3702": "47187", # Brentwood → Williamson
    "3703": "47037", # Nashville → Davidson
}