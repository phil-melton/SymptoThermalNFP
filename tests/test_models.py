import datetime as dt

import pytest

from symptothermal_nfp.models import AppSettings, DailyObservation, build_cycle_history
from symptothermal_nfp.taxonomy import BleedingLevel


def test_daily_observation_rejects_time_without_temperature() -> None:
    with pytest.raises(ValueError):
        DailyObservation(
            observation_date=dt.date(2026, 4, 1),
            temperature_time=dt.time(6, 30),
        )


def test_settings_reject_invalid_wake_time() -> None:
    with pytest.raises(ValueError):
        AppSettings(default_wake_time="99:00")


def test_cycle_history_splits_on_new_menses_start() -> None:
    observations = [
        DailyObservation(observation_date=dt.date(2026, 4, 1), bleeding=BleedingLevel.MEDIUM),
        DailyObservation(observation_date=dt.date(2026, 4, 2), bleeding=BleedingLevel.LIGHT),
        DailyObservation(observation_date=dt.date(2026, 4, 3), bleeding=BleedingLevel.NONE),
        DailyObservation(observation_date=dt.date(2026, 4, 4), bleeding=BleedingLevel.HEAVY),
        DailyObservation(observation_date=dt.date(2026, 4, 5), bleeding=BleedingLevel.LIGHT),
    ]

    cycles = build_cycle_history(observations)

    assert len(cycles) == 2
    assert cycles[0].start_date == dt.date(2026, 4, 1)
    assert cycles[0].end_date == dt.date(2026, 4, 3)
    assert cycles[1].start_date == dt.date(2026, 4, 4)
    assert cycles[1].end_date == dt.date(2026, 4, 5)
