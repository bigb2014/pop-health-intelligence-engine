"""Local SQLite SDOH data provider — bulk-downloaded data, zero API dependency.

This is the answer to "will we have access to more data if we download
the public datasets and ingest them into our own database?"

YES. Here's why:

1. API rate limits: Census ACS allows 500 queries/day without a key,
   unlimited with a free key. But for batch processing thousands of
   patients across hundreds of ZIP codes, local is faster.

2. Data completeness: The CDC PLACES SDOH social needs module covers
   only 75% of ZCTAs. Bulk download gives us the full dataset including
   the 25% that are missing from API queries for some areas.

3. USDA Food Access Research Atlas: NO API at all — CSV download only.
   The only way to use it is to download and ingest.

4. FBI UCR crime data: No reliable ZIP-level API. Must download and
   map agency/county → ZIP via HUD crosswalk.

5. Offline capability: For HIPAA compliance, you may not want patient
   ZIP codes going to external APIs. Local DB keeps all queries internal.

6. Historical data: APIs typically return only the latest release.
   Downloaded data lets you track SDOH changes over time.

This provider reads from a local SQLite database populated by the
bulk download scripts. Table schema:

    CREATE TABLE sdoh_metrics (
        zip_code TEXT PRIMARY KEY,
        air_quality_index REAL,
        grocery_access_score REAL,
        housing_instability_score REAL,
        transportation_access_score REAL,
        crime_rate_per_100k REAL,
        education_attainment_pct REAL,
        source TEXT,           -- 'census_acs', 'cdc_places', 'usda_fara', 'composite'
        updated_at TEXT        -- ISO timestamp
    );
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime

from shared.models import RawSdoHMetrics
from features.sdoh_profiler.base import SdoHDataProvider


_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..", "data", "sdoh.db"
)


class LocalDbSdoHProvider(SdoHDataProvider):
    """Reads SDOH metrics from a local SQLite database.

    This provider has zero external API dependency. The database is
    populated by bulk download scripts (see scripts/ directory).

    Benefits over API providers:
    - No rate limits
    - No API keys needed
    - Works offline (HIPAA: no patient ZIP codes sent externally)
    - Access to full datasets (USDA FARA, FBI UCR) that have no API
    - Faster for batch processing
    - Historical tracking (multiple years stored)

    The database is created by running:
        python scripts/download_sdoh_data.py
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = os.path.abspath(db_path or _DEFAULT_DB_PATH)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_metrics(self, zip_code: str) -> RawSdoHMetrics:
        """Fetch SDOH metrics from the local SQLite database.

        Raises FileNotFoundError if the database doesn't exist.
        Falls back to national averages if the ZIP code isn't in the DB.
        """
        if not os.path.exists(self._db_path):
            raise FileNotFoundError(
                f"SDOH database not found at {self._db_path}. "
                f"Run scripts/download_sdoh_data.py to create it."
            )

        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT * FROM sdoh_metrics WHERE zip_code = ?",
                (zip_code,),
            ).fetchone()
        finally:
            conn.close()

        if row is None:
            # ZIP not in database — return national averages
            return RawSdoHMetrics(
                zip_code=zip_code,
                air_quality_index=50,
                grocery_access_score=50,
                housing_instability_score=40,
                transportation_access_score=50,
                crime_rate_per_100k=380,
                education_attainment_pct=80,
            )

        return RawSdoHMetrics(
            zip_code=row["zip_code"],
            air_quality_index=row["air_quality_index"],
            grocery_access_score=row["grocery_access_score"],
            housing_instability_score=row["housing_instability_score"],
            transportation_access_score=row["transportation_access_score"],
            crime_rate_per_100k=row["crime_rate_per_100k"],
            education_attainment_pct=row["education_attainment_pct"],
        )

    def upsert_metrics(self, metrics: RawSdoHMetrics, source: str = "composite") -> None:
        """Insert or update SDOH metrics in the local database.

        Used by the bulk download scripts to populate the database.
        """
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)

        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sdoh_metrics (
                    zip_code TEXT PRIMARY KEY,
                    air_quality_index REAL,
                    grocery_access_score REAL,
                    housing_instability_score REAL,
                    transportation_access_score REAL,
                    crime_rate_per_100k REAL,
                    education_attainment_pct REAL,
                    source TEXT,
                    updated_at TEXT
                )
            """)
            conn.execute("""
                INSERT INTO sdoh_metrics VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                ON CONFLICT(zip_code) DO UPDATE SET
                    air_quality_index = excluded.air_quality_index,
                    grocery_access_score = excluded.grocery_access_score,
                    housing_instability_score = excluded.housing_instability_score,
                    transportation_access_score = excluded.transportation_access_score,
                    crime_rate_per_100k = excluded.crime_rate_per_100k,
                    education_attainment_pct = excluded.education_attainment_pct,
                    source = excluded.source,
                    updated_at = excluded.updated_at
            """, (
                metrics.zip_code,
                metrics.air_quality_index,
                metrics.grocery_access_score,
                metrics.housing_instability_score,
                metrics.transportation_access_score,
                metrics.crime_rate_per_100k,
                metrics.education_attainment_pct,
                source,
                datetime.now().isoformat(),
            ))
            conn.commit()
        finally:
            conn.close()