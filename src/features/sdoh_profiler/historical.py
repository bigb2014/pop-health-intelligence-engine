"""Historical SDOH tracking — stores snapshots over time to prove ROI improvement.

When a patient is analyzed, the SDOH metrics for their ZIP code are saved
with a timestamp. Over time, this builds a history that shows whether
interventions are actually improving the social determinants in an area.

Usage:
    from features.sdoh_profiler.historical import SDOHHistoryTracker

    tracker = SDOHHistoryTracker(db_path="data/sdoh.db")
    tracker.snapshot(zip_code, sdoh_metrics, source="composite")
    history = tracker.get_history(zip_code, limit=12)
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from typing import Any


class SDOHHistoryTracker:
    """Stores and retrieves historical SDOH snapshots in SQLite.

    Table schema:
        sdoh_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            zip_code TEXT,
            overall_risk REAL,
            air_quality_index REAL,
            grocery_access_score REAL,
            housing_instability_score REAL,
            transportation_access_score REAL,
            crime_rate_per_100k REAL,
            education_attainment_pct REAL,
            snapshot_date TEXT,  -- ISO timestamp
            source TEXT
        )
    """

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "..", "..", "data", "sdoh.db"
        )

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self, conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sdoh_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zip_code TEXT NOT NULL,
                overall_risk REAL,
                air_quality_index REAL,
                grocery_access_score REAL,
                housing_instability_score REAL,
                transportation_access_score REAL,
                crime_rate_per_100k REAL,
                education_attainment_pct REAL,
                snapshot_date TEXT NOT NULL,
                source TEXT,
                UNIQUE(zip_code, snapshot_date)
            )
        """)
        conn.commit()

    def snapshot(
        self,
        zip_code: str,
        metrics: dict[str, float],
        source: str = "composite",
    ) -> bool:
        """Save a snapshot of SDOH metrics for a ZIP code.

        Args:
            zip_code: 5-digit ZIP code
            metrics: Dict with air_quality_index, grocery_access_score, etc.
            source: Data source identifier

        Returns:
            True if snapshot was saved, False if duplicate (same ZIP+date).
        """
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        conn = self._get_conn()
        try:
            self._ensure_table(conn)
            now = datetime.now().strftime("%Y-%m-%d")  # Daily granularity

            try:
                conn.execute("""
                    INSERT INTO sdoh_history VALUES (
                        NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                """, (
                    zip_code,
                    metrics.get("overall_risk"),
                    metrics.get("air_quality_index"),
                    metrics.get("grocery_access_score"),
                    metrics.get("housing_instability_score"),
                    metrics.get("transportation_access_score"),
                    metrics.get("crime_rate_per_100k"),
                    metrics.get("education_attainment_pct"),
                    now,
                    source,
                ))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # Duplicate (same ZIP + date) — update instead
                conn.execute("""
                    UPDATE sdoh_history SET
                        overall_risk = ?,
                        air_quality_index = ?,
                        grocery_access_score = ?,
                        housing_instability_score = ?,
                        transportation_access_score = ?,
                        crime_rate_per_100k = ?,
                        education_attainment_pct = ?,
                        source = ?
                    WHERE zip_code = ? AND snapshot_date = ?
                """, (
                    metrics.get("overall_risk"),
                    metrics.get("air_quality_index"),
                    metrics.get("grocery_access_score"),
                    metrics.get("housing_instability_score"),
                    metrics.get("transportation_access_score"),
                    metrics.get("crime_rate_per_100k"),
                    metrics.get("education_attainment_pct"),
                    source,
                    zip_code,
                    now,
                ))
                conn.commit()
                return True
        finally:
            conn.close()

    def get_history(self, zip_code: str, limit: int = 12) -> list[dict]:
        """Get historical snapshots for a ZIP code.

        Args:
            zip_code: 5-digit ZIP code
            limit: Maximum number of snapshots to return

        Returns:
            List of dicts with snapshot data, oldest first.
        """
        if not os.path.exists(self._db_path):
            return []

        conn = self._get_conn()
        try:
            rows = conn.execute("""
                SELECT * FROM sdoh_history
                WHERE zip_code = ?
                ORDER BY snapshot_date DESC
                LIMIT ?
            """, (zip_code, limit)).fetchall()

            return [dict(row) for row in reversed(rows)]
        finally:
            conn.close()

    def get_trend(self, zip_code: str, field: str, limit: int = 12) -> list[tuple[str, float]]:
        """Get trend for a specific field over time.

        Args:
            zip_code: 5-digit ZIP code
            field: Field name (e.g., 'overall_risk', 'housing_instability_score')
            limit: Max snapshots

        Returns:
            List of (date, value) tuples, oldest first.
        """
        history = self.get_history(zip_code, limit)
        return [(h["snapshot_date"], h.get(field)) for h in history]

    def get_latest(self, zip_code: str) -> dict | None:
        """Get the most recent snapshot for a ZIP code."""
        history = self.get_history(zip_code, limit=1)
        return history[0] if history else None