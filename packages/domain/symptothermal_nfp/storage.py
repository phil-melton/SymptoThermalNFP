from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .models import AppSettings, CervicalPositionObservation, DailyObservation, FluidObservation, build_cycle_history, parse_hhmm_time, parse_iso_date
from .taxonomy import (
    BleedingLevel,
    CervixFirmness,
    CervixHeight,
    CervixOpening,
    FluidQuantity,
    FluidSensation,
    TemperatureUnit,
)

SCHEMA_VERSION = 1


class LocalStore:
    """SQLite-backed local store for observations, settings, and cycle snapshots."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )

            applied_versions = {
                row["version"] for row in connection.execute("SELECT version FROM schema_migrations")
            }

            if SCHEMA_VERSION not in applied_versions:
                self._apply_schema_v1(connection)
                connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, _utc_now_iso()),
                )
                connection.commit()

    def save_settings(self, settings: AppSettings) -> None:
        payload = json.dumps(settings.as_dict(), sort_keys=True)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO settings(setting_key, value_json, updated_at)
                VALUES ('app_settings', ?, ?)
                ON CONFLICT(setting_key)
                DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (payload, _utc_now_iso()),
            )
            connection.commit()

    def load_settings(self) -> AppSettings:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value_json FROM settings WHERE setting_key = 'app_settings'"
            ).fetchone()

        if row is None:
            return AppSettings()

        try:
            payload = json.loads(row["value_json"])
        except json.JSONDecodeError:
            return AppSettings()

        return AppSettings.from_dict(payload)

    def upsert_observation(self, observation: DailyObservation, temperature_unit: TemperatureUnit) -> None:
        now = _utc_now_iso()
        payload = self._observation_to_db_values(observation, temperature_unit)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO observations(
                    observation_date,
                    waking_temperature,
                    temperature_unit,
                    temperature_time,
                    temperature_disturbed,
                    fluid_sensation,
                    fluid_quantity,
                    fluid_peak_quality,
                    cervix_height,
                    cervix_firmness,
                    cervix_opening,
                    bleeding,
                    notes,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(observation_date)
                DO UPDATE SET
                    waking_temperature = excluded.waking_temperature,
                    temperature_unit = excluded.temperature_unit,
                    temperature_time = excluded.temperature_time,
                    temperature_disturbed = excluded.temperature_disturbed,
                    fluid_sensation = excluded.fluid_sensation,
                    fluid_quantity = excluded.fluid_quantity,
                    fluid_peak_quality = excluded.fluid_peak_quality,
                    cervix_height = excluded.cervix_height,
                    cervix_firmness = excluded.cervix_firmness,
                    cervix_opening = excluded.cervix_opening,
                    bleeding = excluded.bleeding,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    payload["observation_date"],
                    payload["waking_temperature"],
                    payload["temperature_unit"],
                    payload["temperature_time"],
                    payload["temperature_disturbed"],
                    payload["fluid_sensation"],
                    payload["fluid_quantity"],
                    payload["fluid_peak_quality"],
                    payload["cervix_height"],
                    payload["cervix_firmness"],
                    payload["cervix_opening"],
                    payload["bleeding"],
                    payload["notes"],
                    now,
                    now,
                ),
            )
            connection.commit()

    def get_observation(self, observation_date: str) -> DailyObservation | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM observations WHERE observation_date = ?",
                (observation_date,),
            ).fetchone()

        if row is None:
            return None
        return self._db_row_to_observation(row)

    def list_observations(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[DailyObservation]:
        clauses: list[str] = []
        params: list[str] = []

        if start_date:
            clauses.append("observation_date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("observation_date <= ?")
            params.append(end_date)

        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT * FROM observations {where_clause} ORDER BY observation_date"

        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [self._db_row_to_observation(row) for row in rows]

    def list_cycle_snapshots(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ):
        observations = self.list_observations(start_date=start_date, end_date=end_date)
        return build_cycle_history(observations)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _apply_schema_v1(connection: sqlite3.Connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                setting_key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS observations (
                observation_date TEXT PRIMARY KEY,
                waking_temperature REAL,
                temperature_unit TEXT,
                temperature_time TEXT,
                temperature_disturbed INTEGER NOT NULL DEFAULT 0,
                fluid_sensation TEXT,
                fluid_quantity TEXT,
                fluid_peak_quality INTEGER NOT NULL DEFAULT 0,
                cervix_height TEXT,
                cervix_firmness TEXT,
                cervix_opening TEXT,
                bleeding TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_observations_date ON observations(observation_date)"
        )

    @staticmethod
    def _observation_to_db_values(
        observation: DailyObservation,
        temperature_unit: TemperatureUnit,
    ) -> dict[str, object | None]:
        return {
            "observation_date": observation.observation_date.isoformat(),
            "waking_temperature": observation.waking_temperature,
            "temperature_unit": temperature_unit.value if observation.waking_temperature is not None else None,
            "temperature_time": observation.temperature_time.strftime("%H:%M") if observation.temperature_time else None,
            "temperature_disturbed": int(observation.temperature_disturbed),
            "fluid_sensation": observation.fluid.sensation.value if observation.fluid else None,
            "fluid_quantity": observation.fluid.quantity.value if observation.fluid else None,
            "fluid_peak_quality": int(observation.fluid.peak_quality) if observation.fluid else 0,
            "cervix_height": observation.cervical_position.height.value if observation.cervical_position else None,
            "cervix_firmness": observation.cervical_position.firmness.value if observation.cervical_position else None,
            "cervix_opening": observation.cervical_position.opening.value if observation.cervical_position else None,
            "bleeding": observation.bleeding.value,
            "notes": observation.notes,
        }

    @staticmethod
    def _db_row_to_observation(row: sqlite3.Row) -> DailyObservation:
        fluid = None
        if row["fluid_sensation"]:
            fluid = FluidObservation(
                sensation=FluidSensation(row["fluid_sensation"]),
                quantity=FluidQuantity(row["fluid_quantity"] or FluidQuantity.NONE.value),
                peak_quality=bool(row["fluid_peak_quality"]),
            )

        cervical_position = None
        if row["cervix_height"] and row["cervix_firmness"] and row["cervix_opening"]:
            cervical_position = CervicalPositionObservation(
                height=CervixHeight(row["cervix_height"]),
                firmness=CervixFirmness(row["cervix_firmness"]),
                opening=CervixOpening(row["cervix_opening"]),
            )

        tu = row["temperature_unit"] if row["waking_temperature"] is not None else None
        return DailyObservation(
            observation_date=parse_iso_date(row["observation_date"]),
            waking_temperature=row["waking_temperature"],
            temperature_time=parse_hhmm_time(row["temperature_time"]) if row["temperature_time"] else None,
            temperature_disturbed=bool(row["temperature_disturbed"]),
            temperature_unit=TemperatureUnit(tu) if tu else None,
            fluid=fluid,
            cervical_position=cervical_position,
            bleeding=BleedingLevel(row["bleeding"]),
            notes=row["notes"] or "",
        )


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
