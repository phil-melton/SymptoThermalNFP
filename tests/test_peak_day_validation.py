import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "validate_peak_day_accuracy.py"
SPEC = importlib.util.spec_from_file_location("peak_day_validation", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
validation = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validation
SPEC.loader.exec_module(validation)


def test_statistical_population_is_deterministic_and_source_shaped() -> None:
    first = validation.generate_statistical_population(
        validation.STATISTICAL_CYCLE_COUNT,
        seed=validation.STATISTICAL_SEED,
    )
    second = validation.generate_statistical_population(
        validation.STATISTICAL_CYCLE_COUNT,
        seed=validation.STATISTICAL_SEED,
    )

    first_shape = [(case.cycle_length, case.true_peak_cycle_day) for case in first]
    second_shape = [(case.cycle_length, case.true_peak_cycle_day) for case in second]

    assert first_shape == second_shape

    results = validation.run_validation(first)
    metrics = validation.summarize_results(results)

    assert abs(metrics["statistical_cycle_length_mean"] - 28.5) <= 0.5
    assert abs(metrics["statistical_cycle_length_sd"] - 3.18) <= 0.5
    assert abs(metrics["statistical_peak_day_mean"] - 15.0) <= 0.5
    assert abs(metrics["statistical_peak_day_sd"] - 2.6) <= 0.5
    assert metrics["exact_peak_rate"] == 1.0


def test_curveball_validation_hits_expected_peak_and_exception_signals() -> None:
    results = {
        result.case.case_id: result
        for result in validation.run_validation(validation.generate_curveball_cases())
    }

    assert all(result.status == "pass" for result in results.values())
    assert results["repeat-false-peaks"].delta_days == 0
    assert results["late-long-cycle"].delta_days == 0
    assert results["slow-staircase-rise"].detected_fourth_day_exception is True
    assert results["exact-threshold"].detected_fourth_day_exception is False
    assert results["disturbed-high"].detected_temperature_shift is False
    assert results["missing-calendar-day"].detected_temperature_shift is False
    assert "elevated_temperature" in results["fever-warning"].warning_codes
    assert results["unclear-no-mucus"].detected_peak_day is None
    assert results["unclear-no-mucus"].detected_unclear_mucus_exception is True
    assert "temperature_unclear_mucus_exception" in results["unclear-no-mucus"].trace_codes
    assert "premature_temperature_rise_ignored" in results["premature-temp-rise"].trace_codes
    assert "possible_anovulatory_bleeding" in results["breakthrough-bleeding"].warning_codes
    assert results["open-ended-peak"].detected_peak_day is None


def test_full_validation_summary_has_no_accuracy_failures() -> None:
    results = validation.run_validation(validation.build_validation_cases())
    metrics = validation.summarize_results(results)

    assert metrics["case_count"] == 171
    assert metrics["peak_expected_count"] == 168
    assert metrics["exact_peak_count"] == 168
    assert metrics["within_4_day_count"] == 168
    assert metrics["false_negative_count"] == 0
    assert metrics["false_positive_count"] == 0
    assert metrics["warning_hits"] == metrics["warning_expectations"]
    assert metrics["trace_hits"] == metrics["trace_expectations"]
    assert metrics["exception_hits"] == metrics["exception_expectations"]
    assert metrics["failed_case_count"] == 0


def test_report_artifacts_are_written_with_svg_figures(tmp_path: Path) -> None:
    results = validation.run_validation(validation.build_validation_cases())
    metrics = validation.summarize_results(results)
    report_path = tmp_path / "report.md"
    results_path = tmp_path / "results.json"
    figure_dir = tmp_path / "figures"

    validation.write_artifacts(
        results,
        metrics,
        report_path=report_path,
        results_path=results_path,
        figure_dir=figure_dir,
    )

    assert report_path.exists()
    assert results_path.exists()
    assert (figure_dir / "temperature-history.svg").exists()
    assert (figure_dir / "symptom-history.svg").exists()
    assert (figure_dir / "curveball-panels.svg").exists()
    assert (figure_dir / "accuracy-summary.svg").exists()

    report = report_path.read_text(encoding="utf-8")
    assert "Peak-Day Accuracy Validation Report" in report
    assert "![Temperature history with Peak Day and coverline](figures/temperature-history.svg)" in report
    assert "WHO multicentre ovulation method study" in report
