"""Shared test fixtures and YAML fixture loader for cycle test data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pytest
import yaml

from symptothermal_nfp.models import (
    AppSettings,
    DailyObservation,
    FluidObservation,
    PriorCycleSummary,
)
from symptothermal_nfp.taxonomy import (
    BleedingLevel,
    FertilityState,
    FluidSensation,
    TemperatureUnit,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "cycles"


@dataclass
class CycleFixture:
    """Parsed cycle fixture from YAML."""
    name: str
    description: str
    settings: AppSettings
    prior_cycles: list[PriorCycleSummary]
    observations: list[DailyObservation]
    expected: dict[str, Any]


def _parse_observation(raw: dict[str, Any]) -> DailyObservation:
    """Parse a single observation dict from YAML into a DailyObservation."""
    fluid = None
    if "fluid" in raw and raw["fluid"]:
        fluid_data = raw["fluid"]
        fluid = FluidObservation(
            sensation=FluidSensation(fluid_data["sensation"]),
            peak_quality=bool(fluid_data.get("peak_quality", False)),
        )

    bleeding = BleedingLevel.NONE
    if "bleeding" in raw:
        bleeding = BleedingLevel(raw["bleeding"])

    tu = TemperatureUnit(raw["temperature_unit"]) if raw.get("temperature_unit") else None

    return DailyObservation(
        observation_date=date.fromisoformat(raw["date"]),
        waking_temperature=raw.get("temperature"),
        temperature_disturbed=bool(raw.get("temperature_disturbed", False)),
        temperature_unit=tu,
        fluid=fluid,
        bleeding=bleeding,
    )


def _parse_prior_cycle(raw: dict[str, Any]) -> PriorCycleSummary:
    return PriorCycleSummary(
        cycle_length=raw["cycle_length"],
        t_shift_day=raw.get("t_shift_day"),
        confirmed_post_ov=bool(raw.get("confirmed_post_ov", False)),
    )


def load_fixture(path: Path) -> CycleFixture:
    """Load and parse a single YAML cycle fixture file."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    settings_raw = data.get("settings", {})
    settings = AppSettings(
        temperature_unit=TemperatureUnit(settings_raw.get("temperature_unit", "celsius")),
    )

    prior_cycles = [
        _parse_prior_cycle(pc) for pc in data.get("prior_cycles", [])
    ]

    observations = [_parse_observation(obs) for obs in data["observations"]]

    return CycleFixture(
        name=data["name"],
        description=data.get("description", ""),
        settings=settings,
        prior_cycles=prior_cycles,
        observations=observations,
        expected=data["expected"],
    )


def get_fixture_files() -> list[Path]:
    """Return all YAML fixture files sorted by name."""
    return sorted(FIXTURES_DIR.glob("*.yaml"))


@pytest.fixture(params=get_fixture_files(), ids=lambda p: p.stem)
def cycle_fixture(request: pytest.FixtureRequest) -> CycleFixture:
    """Parametrized fixture that yields each YAML cycle fixture."""
    return load_fixture(request.param)
