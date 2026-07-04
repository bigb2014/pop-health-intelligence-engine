"""USDA Food Access Research Atlas ingestion script.

Downloads the USDA Food Access Research Atlas Excel file, processes it,
joins Census tract data to ZIP codes via the HUD crosswalk, and stores
food desert flags in the local SQLite database.

Prerequisites:
    1. Download the Excel file from:
       https://www.ers.usda.gov/data-products/food-access-research-atlas/download-the-data/
    2. Save as: data/FoodAccessResearchAtlasData2019.xlsx
    3. Run: python scripts/ingest_food_access.py

Requires:
    HUD_API_TOKEN in .env (for ZIP→tract crosswalk)
    pip install openpyxl (for Excel reading)
"""

import sys, os, sqlite3, json, urllib.request, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from features.sdoh_profiler.providers.hud import HUDCrosswalkProvider

NASHVILLE_ZCTAS = [
    "37115", "37138", "37201", "37203", "37204", "37205", "37206",
    "37207", "37208", "37209", "37210", "37211", "37212", "37213",
    "37214", "37215", "37216", "37217", "37218", "37219", "37220",
    "37221", "37227", "37228", "37229", "37230", "37235",
    "37236", "37237", "37238", "37240", "37241", "37242", "37243",
    "37244", "37245", "37246", "37247", "37248", "37249", "37250",
    "37013", "37027", "37055", "37064", "37067", "37069", "37072",
    "37075", "37076", "37080", "37082", "37086", "37090",
]


def read_food_atlas(excel_path: str) -> dict[str, dict]:
    """Read the USDA Food Access Research Atlas Excel file.

    Returns a dict mapping Census tract FIPS → food desert flags.
    """
    try:
        import openpyxl
    except ImportError:
        print("ERROR: openpyxl not installed. Run: pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.load_workbook(excel_path, read_only=True)
    # The data is in a sheet called "Food Access Research Atlas" or similar
    ws = wb.worksheets[0]  # First sheet

    # Read header row to find column indices
    headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]

    # Find column indices (varies by version)
    col_map = {}
    for i, h in enumerate(headers):
        if h:
            h_lower = str(h).lower().strip()
            if "census" in h_lower and "tract" in h_lower:
                col_map["tract"] = i
            elif "lahalf" in h_lower or "half" in h_lower and "mile" in h_lower:
                col_map["low_access_halfmi"] = i
            elif "la1" in h_lower and "mile" in h_lower:
                col_map["low_access_1mi"] = i
            elif "la10" in h_lower or "10" in h_lower and "mile" in h_lower:
                col_map["low_access_10mi"] = i
            elif "li" in h_lower and "la" in h_lower:
                col_map["low_income"] = i
            elif "lapop" in h_lower or "laland" in h_lower:
                col_map["low_access_pop"] = i

    print(f"Found columns: {col_map}")

    tracts = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        tract_fips = str(row[col_map["tract"]]) if "tract" in col_map else None
        if not tract_fips:
            continue

        # Determine if this tract is a food desert
        # USDA defines food desert as: low-income AND low-access
        is_low_income = bool(row[col_map.get("low_income", -1)]) if "low_income" in col_map else False
        is_low_access_1mi = bool(row[col_map.get("low_access_1mi", -1)]) if "low_access_1mi" in col_map else False
        is_low_access_halfmi = bool(row[col_map.get("low_access_halfmi", -1)]) if "low_access_halfmi" in col_map else False
        is_low_access_10mi = bool(row[col_map.get("low_access_10mi", -1)]) if "low_access_10mi" in col_map else False

        # A food desert is: low-income tract with low access (at any distance)
        is_food_desert = is_low_income and (is_low_access_1mi or is_low_access_halfmi or is_low_access_10mi)

        tracts[tract_fips] = {
            "is_food_desert": int(is_food_desert),
            "low_income": int(is_low_income),
            "low_access_1mi": int(is_low_access_1mi),
            "low_access_10mi": int(is_low_access_10mi),
            "low_access_halfmi": int(is_low_access_halfmi),
        }

    wb.close()
    print(f"Loaded {len(tracts)} Census tracts from Food Access Atlas")
    return tracts


def ingest_to_db(tracts: dict, db_path: str):
    """Store food desert flags in the local SQLite database."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS food_access (
                tract_geoid TEXT PRIMARY KEY,
                is_food_desert INTEGER,
                low_income INTEGER,
                low_access_1mi INTEGER,
                low_access_10mi INTEGER,
                low_access_halfmi INTEGER,
                source TEXT,
                updated_at TEXT
            )
        """)
        from datetime import datetime
        now = datetime.now().isoformat()

        for geoid, flags in tracts.items():
            conn.execute("""
                INSERT OR REPLACE INTO food_access VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                geoid,
                flags["is_food_desert"],
                flags["low_income"],
                flags["low_access_1mi"],
                flags["low_access_10mi"],
                flags["low_access_halfmi"],
                "usda_fara_2019",
                now,
            ))
        conn.commit()
        print(f"Stored {len(tracts)} tract records in {db_path}")
    finally:
        conn.close()


def main():
    project_root = os.path.join(os.path.dirname(__file__), "..")
    excel_path = os.path.abspath(os.path.join(project_root, "data", "FoodAccessResearchAtlasData2019.xlsx"))
    db_path = os.path.abspath(os.path.join(project_root, "data", "sdoh.db"))

    if not os.path.exists(excel_path):
        print("ERROR: Food Access Atlas Excel file not found.")
        print(f"  Expected: {excel_path}")
        print("  Download from: https://www.ers.usda.gov/data-products/food-access-research-atlas/download-the-data/")
        print("  Save the file as: data/FoodAccessResearchAtlasData2019.xlsx")
        sys.exit(1)

    print(f"Reading Food Access Atlas: {excel_path}")
    tracts = read_food_atlas(excel_path)

    if not tracts:
        print("ERROR: No tracts loaded from Excel file.")
        sys.exit(1)

    print(f"\nIngesting {len(tracts)} tracts into database...")
    ingest_to_db(tracts, db_path)

    # Optionally verify with HUD crosswalk for a sample ZIP
    hud_token = os.environ.get("HUD_API_TOKEN", "")
    if hud_token:
        print("\nVerifying with HUD crosswalk for ZIP 37208...")
        hud = HUDCrosswalkProvider(api_token=hud_token)
        zip_tracts = hud.get_tracts_for_zip("37208")

        conn = sqlite3.connect(db_path)
        food_desert_count = 0
        for t in zip_tracts:
            row = conn.execute(
                "SELECT is_food_desert FROM food_access WHERE tract_geoid = ?",
                (t["geoid"],),
            ).fetchone()
            if row and row[0]:
                food_desert_count += 1
        conn.close()
        print(f"  ZIP 37208: {len(zip_tracts)} tracts, {food_desert_count} are food deserts")
    else:
        print("\n(Skipping HUD verification — no HUD_API_TOKEN set)")

    print("\nDone! FoodAccessCrimeProvider will now use real food desert data.")


if __name__ == "__main__":
    main()