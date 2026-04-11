"""
Tests for the Sensiplan symptothermal algorithm.

All primary tests are driven by YAML fixture files in tests/fixtures/cycles/.
Each fixture specifies observations, expected states, and expected
evaluation results, computed by hand from the Sensiplan spec.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from symptothermal_nfp.algorithm import evaluate_cycle
from symptothermal_nfp.models import AppSettings, DailyObservation
from symptothermal_nfp.taxonomy import FertilityState, TemperatureUnit

from conftest import CycleFixture


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "cycles"


class TestEvaluateCycleFromFixtures:
    """Run evaluate_cycle against every YAML fixture and verify outputs."""

    def test_states(self, cycle_fixture: CycleFixture) -> None:
        """Per-day fertility states must match expected."""
        result = evaluate_cycle(
            observations=cycle_fixture.observations,
            settings=cycle_fixture.settings,
            prior_cycles=cycle_fixture.prior_cycles,
        )
        expected_states = [
            FertilityState(s) for s in cycle_fixture.expected["states"]
        ]
        actual_states = list(result.states)
        assert actual_states == expected_states, (
            f"Fixture '{cycle_fixture.name}': state mismatch.\n"
            f"Expected: {[s.value for s in expected_states]}\n"
            f"Actual:   {[s.value for s in actual_states]}"
        )

    def test_t_shift_day(self, cycle_fixture: CycleFixture) -> None:
        result = evaluate_cycle(
            cycle_fixture.observations,
            cycle_fixture.settings,
            cycle_fixture.prior_cycles,
        )
        assert result.t_shift_day == cycle_fixture.expected["t_shift_day"], (
            f"Fixture '{cycle_fixture.name}': t_shift_day mismatch"
        )

    def test_coverline(self, cycle_fixture: CycleFixture) -> None:
        result = evaluate_cycle(
            cycle_fixture.observations,
            cycle_fixture.settings,
            cycle_fixture.prior_cycles,
        )
        expected = cycle_fixture.expected["coverline_celsius"]
        if expected is None:
            assert result.coverline_celsius is None
        else:
            assert result.coverline_celsius is not None
            assert abs(result.coverline_celsius - expected) < 0.015, (
                f"Fixture '{cycle_fixture.name}': coverline mismatch. "
                f"Expected ~{expected}, got {result.coverline_celsius}"
            )

    def test_peak_day(self, cycle_fixture: CycleFixture) -> None:
        result = evaluate_cycle(
            cycle_fixture.observations,
            cycle_fixture.settings,
            cycle_fixture.prior_cycles,
        )
        assert result.peak_day == cycle_fixture.expected["peak_day"], (
            f"Fixture '{cycle_fixture.name}': peak_day mismatch"
        )

    def test_temp_confirmed_day(self, cycle_fixture: CycleFixture) -> None:
        result = evaluate_cycle(
            cycle_fixture.observations,
            cycle_fixture.settings,
            cycle_fixture.prior_cycles,
        )
        assert result.temp_confirmed_day == cycle_fixture.expected["temp_confirmed_day"], (
            f"Fixture '{cycle_fixture.name}': temp_confirmed_day mismatch"
        )

    def test_peak_confirmed_day(self, cycle_fixture: CycleFixture) -> None:
        result = evaluate_cycle(
            cycle_fixture.observations,
            cycle_fixture.settings,
            cycle_fixture.prior_cycles,
        )
        assert result.peak_confirmed_day == cycle_fixture.expected["peak_confirmed_day"], (
            f"Fixture '{cycle_fixture.name}': peak_confirmed_day mismatch"
        )

    def test_infertile_from_day(self, cycle_fixture: CycleFixture) -> None:
        result = evaluate_cycle(
            cycle_fixture.observations,
            cycle_fixture.settings,
            cycle_fixture.prior_cycles,
        )
        assert result.infertile_from_day == cycle_fixture.expected["infertile_from_day"], (
            f"Fixture '{cycle_fixture.name}': infertile_from_day mismatch"
        )

    def test_slow_rise_flag(self, cycle_fixture: CycleFixture) -> None:
        result = evaluate_cycle(
            cycle_fixture.observations,
            cycle_fixture.settings,
            cycle_fixture.prior_cycles,
        )
        assert result.slow_rise_applied == cycle_fixture.expected["slow_rise_applied"], (
            f"Fixture '{cycle_fixture.name}': slow_rise_applied mismatch"
        )

    def test_drop_back_flag(self, cycle_fixture: CycleFixture) -> None:
        result = evaluate_cycle(
            cycle_fixture.observations,
            cycle_fixture.settings,
            cycle_fixture.prior_cycles,
        )
        assert result.drop_back_applied == cycle_fixture.expected["drop_back_applied"], (
            f"Fixture '{cycle_fixture.name}': drop_back_applied mismatch"
        )

    def test_day_traces_present(self, cycle_fixture: CycleFixture) -> None:
        """Every day must have a rule trace."""
        result = evaluate_cycle(
            cycle_fixture.observations,
            cycle_fixture.settings,
            cycle_fixture.prior_cycles,
        )
        assert len(result.day_traces) == len(cycle_fixture.observations), (
            f"Fixture '{cycle_fixture.name}': expected {len(cycle_fixture.observations)} "
            f"traces, got {len(result.day_traces)}"
        )

    def test_disqualifiers(self, cycle_fixture: CycleFixture) -> None:
        result = evaluate_cycle(
            cycle_fixture.observations,
            cycle_fixture.settings,
            cycle_fixture.prior_cycles,
        )
        expected_disq = cycle_fixture.expected.get("disqualifiers", [])
        if expected_disq:
            assert len(result.disqualifiers) > 0, (
                f"Fixture '{cycle_fixture.name}': expected disqualifiers but got none"
            )
        else:
            assert len(result.disqualifiers) == 0, (
                f"Fixture '{cycle_fixture.name}': unexpected disqualifiers: {result.disqualifiers}"
            )


class TestEdgeCases:
    """Edge cases not covered by YAML fixtures."""

    def test_empty_cycle(self) -> None:
        """Empty observation list should return empty result."""
        result = evaluate_cycle([], AppSettings())
        assert result.states == []
        assert result.t_shift_day is None

    def test_single_day(self) -> None:
        """Single observation should be fertile."""
        obs = DailyObservation(
            observation_date=date(2024, 1, 1),
            waking_temperature=36.5,
            temperature_unit=TemperatureUnit.CELSIUS,
        )
        result = evaluate_cycle([obs], AppSettings())
        assert len(result.states) == 1
        assert result.states[0] == FertilityState.FERTILE
