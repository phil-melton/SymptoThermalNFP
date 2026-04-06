import datetime as dt

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
    TemperatureUnit,
)


def test_settings_round_trip(tmp_path) -> None:
    store = LocalStore(tmp_path / "local.db")
    store.initialize()

    expected = AppSettings(
        temperature_unit=TemperatureUnit.FAHRENHEIT,
        default_wake_time="07:15",
        track_cervical_position=True,
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
        temperature_time=dt.time(6, 20),
        temperature_disturbed=False,
        fluid=FluidObservation(
            sensation=FluidSensation.WATERY,
            quantity=FluidQuantity.HIGH,
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
