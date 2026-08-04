import datetime as dt
import sqlite3

from symptothermal_nfp.models import (
    AppSettings,
    CervicalPositionObservation,
    DailyObservation,
    FluidObservation,
)
from symptothermal_nfp.storage import LocalStore
from symptothermal_nfp.taxonomy import (
    BleedingLevel,
    CervixFirmness,
    CervixHeight,
    CervixOpening,
    FluidQuantity,
    FluidSensation,
    MucusColor,
    MucusTexture,
    RuleContext,
    TemperatureDisturbance,
    TemperatureUnit,
    TrackingGoal,
)


def test_settings_round_trip(tmp_path) -> None:
    store = LocalStore(tmp_path / "local.db")
    store.initialize()

    expected = AppSettings(
        temperature_unit=TemperatureUnit.FAHRENHEIT,
        default_wake_time="07:15",
        track_cervical_position=True,
        rule_context=RuleContext.POST_HORMONAL,
        transition_cycle_count=2,
        use_doering_rule=True,
        use_rotzer_rule=True,
        bip_enabled=True,
        tracking_goal=TrackingGoal.AVOID_PREGNANCY,
        setup_complete=True,
    )

    store.save_settings(expected)
    actual = store.load_settings()
    assert actual == expected


def test_observation_round_trip(tmp_path) -> None:
    store = LocalStore(tmp_path / "local.db")
    store.initialize()

    expected = DailyObservation(
        observation_date=dt.date(2026, 4, 6),
        waking_temperature=36.45,
        temperature_unit=TemperatureUnit.CELSIUS,
        temperature_time=dt.time(6, 20),
        temperature_disturbed=True,
        temperature_disturbances=[
            TemperatureDisturbance.POOR_SLEEP,
            TemperatureDisturbance.LATER_THAN_USUAL,
        ],
        fluid=FluidObservation(
            sensation=FluidSensation.WATERY,
            quantity=FluidQuantity.HIGH,
            color=MucusColor.CLEAR,
            texture=MucusTexture.STRETCHY,
            amount=5,
            peak_quality=True,
        ),
        cervical_position=CervicalPositionObservation(
            height=CervixHeight.HIGH,
            firmness=CervixFirmness.SOFT,
            opening=CervixOpening.OPEN,
        ),
        bleeding=BleedingLevel.NONE,
        notes="Good sleep",
    )

    store.upsert_observation(expected, TemperatureUnit.CELSIUS)
    actual = store.get_observation(expected.observation_date.isoformat())

    assert actual == expected


def test_cycle_snapshots_from_storage(tmp_path) -> None:
    store = LocalStore(tmp_path / "local.db")
    store.initialize()

    store.upsert_observation(
        DailyObservation(observation_date=dt.date(2026, 4, 1), bleeding=BleedingLevel.MEDIUM),
        TemperatureUnit.CELSIUS,
    )
    store.upsert_observation(
        DailyObservation(observation_date=dt.date(2026, 4, 2), bleeding=BleedingLevel.NONE),
        TemperatureUnit.CELSIUS,
    )
    store.upsert_observation(
        DailyObservation(observation_date=dt.date(2026, 4, 3), bleeding=BleedingLevel.HEAVY),
        TemperatureUnit.CELSIUS,
    )

    cycles = store.list_cycle_snapshots()

    assert len(cycles) == 2
    assert cycles[0].start_date == dt.date(2026, 4, 1)
    assert cycles[0].end_date == dt.date(2026, 4, 2)
    assert cycles[1].start_date == dt.date(2026, 4, 3)


def test_schema_v1_database_migrates_to_latest(tmp_path) -> None:
    db_path = tmp_path / "local.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        connection.execute(
            """
            CREATE TABLE settings (
                setting_key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE observations (
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
            "INSERT INTO schema_migrations(version, applied_at) VALUES (1, '2026-04-01T00:00:00Z')"
        )
        connection.execute(
            """
            INSERT INTO observations(
                observation_date, waking_temperature, temperature_unit,
                temperature_disturbed, fluid_sensation, fluid_quantity,
                fluid_peak_quality, bleeding, notes, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-04-06",
                36.45,
                "celsius",
                0,
                "sticky",
                "low",
                0,
                "none",
                "",
                "2026-04-06T00:00:00Z",
                "2026-04-06T00:00:00Z",
            ),
        )

    store = LocalStore(db_path)
    store.initialize()
    observation = store.get_observation("2026-04-06")

    assert observation is not None
    assert observation.fluid is not None
    assert observation.fluid.color == MucusColor.NONE
    assert observation.fluid.texture == MucusTexture.NONE
    assert observation.temperature_unit == TemperatureUnit.CELSIUS
    assert observation.temperature_disturbances == []
