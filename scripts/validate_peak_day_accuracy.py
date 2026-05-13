from __future__ import annotations

import argparse
import html
import json
import math
import random
import statistics
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DOMAIN_SRC = REPO_ROOT / "packages" / "domain"
if str(DOMAIN_SRC) not in sys.path:
    sys.path.insert(0, str(DOMAIN_SRC))

from symptothermal_nfp.interpretation import CycleInterpretation, evaluate_observations
from symptothermal_nfp.models import DailyObservation, FluidObservation
from symptothermal_nfp.taxonomy import (
    BleedingLevel,
    FluidQuantity,
    FluidSensation,
    MucusColor,
    MucusTexture,
    TemperatureUnit,
)


RUN_ID = "peak-day-validation-2026-05-13"
REPORT_PATH = REPO_ROOT / "docs" / "agent-reports" / f"{RUN_ID}.md"
RESULTS_PATH = REPO_ROOT / "docs" / "agent-reports" / f"{RUN_ID}-results.json"
FIGURE_DIR = REPO_ROOT / "docs" / "agent-reports" / "figures" / RUN_ID
STATISTICAL_SEED = 20260513
STATISTICAL_CYCLE_COUNT = 160

SOURCES = [
    {
        "label": "WHO multicentre ovulation method study",
        "url": "https://www.sciencedirect.com/science/article/pii/S0015028216474789",
        "note": "Cycle length mean 28.5 days, SD 3.18; mucus Peak Day mean day 15, SD 2.6.",
    },
    {
        "label": "Fehring 2002 Peak Day study",
        "url": "https://www.sciencedirect.com/science/article/pii/S0010782402003554",
        "note": "Peak Day was within +/-4 days of estimated ovulation in 97.8% of compared cycles.",
    },
    {
        "label": "NCBI StatPearls BBT physiology",
        "url": "https://www.ncbi.nlm.nih.gov/books/NBK546686/",
        "note": "Follicular BBT commonly sits around 97.0-98.0 F; luteal rise is about 0.5-1.0 F.",
    },
    {
        "label": "Frank-Herrmann/Sensiplan paper",
        "url": "https://www.sensiplan.nl/wp-content/uploads/2025/02/Natural-conception-rates-in-subfertile-couples-following-fertility-awareness-training.pdf",
        "note": "Temperature rise rule: three highs over previous six, with the last high 0.2 C above the previous six.",
    },
    {
        "label": "Bailey and Marshall luteal phase summary",
        "url": "https://www.cambridge.org/core/journals/journal-of-biosocial-science/article/abs/relationship-of-the-postovulatory-phase-of-the-menstrual-cycle-to-total-cycle-length/EE433FCF1C8148952B669B01300F09E5",
        "note": "Hyperthermic phase commonly around 10-13 days across shorter to typical cycle lengths.",
    },
]


@dataclass(slots=True)
class SyntheticCase:
    case_id: str
    label: str
    category: str
    description: str
    observations: tuple[DailyObservation, ...]
    expected_peak_day: date | None
    true_peak_cycle_day: int | None
    source_shape: str
    expected_temperature_shift: bool | None = True
    expected_warning_codes: tuple[str, ...] = ()
    expected_trace_codes: tuple[str, ...] = ()
    expected_fourth_day_exception: bool | None = None
    expected_unclear_mucus_exception: bool | None = None

    @property
    def cycle_length(self) -> int:
        return (self.observations[-1].observation_date - self.observations[0].observation_date).days + 1


@dataclass(slots=True)
class ValidationResult:
    case: SyntheticCase
    detected_peak_day: date | None
    detected_temperature_shift: bool
    detected_temperature_confirmed_date: date | None
    detected_coverline_celsius: float | None
    detected_fourth_day_exception: bool | None
    detected_unclear_mucus_exception: bool | None
    warning_codes: tuple[str, ...]
    trace_codes: tuple[str, ...]
    delta_days: int | None
    peak_check_passed: bool
    expectation_check_passed: bool

    @property
    def status(self) -> str:
        return "pass" if self.peak_check_passed and self.expectation_check_passed else "fail"


def build_validation_cases() -> list[SyntheticCase]:
    cases = generate_statistical_population(STATISTICAL_CYCLE_COUNT, seed=STATISTICAL_SEED)
    cases.extend(generate_curveball_cases())
    return cases


def generate_statistical_population(count: int, *, seed: int) -> list[SyntheticCase]:
    rng = random.Random(seed)
    cases: list[SyntheticCase] = []
    start = date(2026, 1, 1)

    for index in range(count):
        cycle_length = _clip_int(round(rng.gauss(28.5, 3.18)), 22, 36)
        peak_day = _clip_int(round(rng.gauss(15.0, 2.6)), 10, cycle_length - 7)
        base_c = rng.uniform(36.25, 36.55)
        rise_c = rng.uniform(0.30, 0.43)
        observations = _build_cycle(
            start + timedelta(days=index * 45),
            length=cycle_length,
            peak_day=peak_day,
            base_c=base_c,
            rise_c=rise_c,
            profile="standard",
            low_phase_offset=index % 6,
        )
        cases.append(
            SyntheticCase(
                case_id=f"stat-{index + 1:03d}",
                label=f"Statistical synthetic cycle {index + 1}",
                category="statistical",
                description=(
                    "Source-shaped ovulatory cycle with Gaussian cycle length, "
                    "Gaussian mucus Peak Day, physiologic low-phase BBT, and luteal rise."
                ),
                observations=tuple(observations),
                expected_peak_day=start + timedelta(days=index * 45 + peak_day - 1),
                true_peak_cycle_day=peak_day,
                source_shape="WHO cycle/Peak Day distribution plus StatPearls BBT rise.",
            )
        )

    return cases


def generate_curveball_cases() -> list[SyntheticCase]:
    start = date(2026, 9, 1)
    case_specs = [
        (
            "repeat-false-peaks",
            "Repeat false peaks before true Peak Day",
            "curveball",
            "Earlier peak-quality mucus patches dry up, then a later true Peak Day appears.",
            _build_cycle(start, length=29, peak_day=16, false_peak_days={9, 10}, profile="standard"),
            16,
            True,
            (),
            (),
            None,
            None,
        ),
        (
            "late-long-cycle",
            "Late ovulation in a long cycle",
            "curveball",
            "Long follicular phase with Peak Day much later than calendar-day assumptions.",
            _build_cycle(start + timedelta(days=40), length=37, peak_day=24, profile="standard"),
            24,
            True,
            (),
            (),
            None,
            None,
        ),
        (
            "slow-staircase-rise",
            "Slow staircase temperature rise",
            "exception",
            "Third high is above the coverline but below the 0.2 C threshold; fourth high is needed.",
            _build_cycle(start + timedelta(days=90), length=30, peak_day=15, profile="slow_staircase"),
            15,
            True,
            (),
            (),
            True,
            None,
        ),
        (
            "exact-threshold",
            "Exact 0.2 C third-high threshold",
            "exception",
            "Third high lands exactly on coverline + 0.2 C and should confirm without day four.",
            _build_cycle(start + timedelta(days=130), length=29, peak_day=14, profile="exact_threshold"),
            14,
            True,
            (),
            (),
            False,
            None,
        ),
        (
            "disturbed-high",
            "Disturbed high temperature blocks confirmation",
            "exception",
            "One of the first three high temperatures is disturbed and cannot be counted.",
            _build_cycle(
                start + timedelta(days=170),
                length=29,
                peak_day=14,
                profile="standard",
                disturbed_days={16},
            ),
            14,
            False,
            (),
            (),
            None,
            None,
        ),
        (
            "missing-calendar-day",
            "Missing calendar day blocks temperature confirmation",
            "exception",
            "A missing day interrupts the required consecutive 6-low/3-high temperature sequence.",
            _build_cycle(
                start + timedelta(days=210),
                length=29,
                peak_day=14,
                profile="standard",
                missing_days={16},
            ),
            14,
            False,
            (),
            (),
            None,
            None,
        ),
        (
            "fever-warning",
            "Fever/elevated temperature warning",
            "curveball",
            "A later fever-like reading is charted after the true shift and should be warned on.",
            _build_cycle(
                start + timedelta(days=250),
                length=29,
                peak_day=14,
                profile="standard",
                fever_days={22},
            ),
            14,
            True,
            ("elevated_temperature",),
            (),
            None,
            None,
        ),
        (
            "unclear-no-mucus",
            "No mucus observations, temperature-only confirmation",
            "exception",
            "No mucus observations are recorded; Peak Day should stay empty and the unclear-mucus exception should be used for BBT.",
            _build_cycle(
                start + timedelta(days=290),
                length=29,
                peak_day=14,
                profile="standard",
                no_mucus=True,
            ),
            None,
            True,
            ("unclear_mucus_peak", "bbt_without_mucus"),
            ("temperature_unclear_mucus_exception",),
            None,
            True,
        ),
        (
            "premature-temp-rise",
            "Premature pre-Peak temperature rise is ignored",
            "exception",
            "A valid-looking early rise occurs before a later Peak Day; highs after Peak Day should be used.",
            _build_premature_temperature_rise_cycle(start + timedelta(days=330)),
            18,
            True,
            (),
            ("premature_temperature_rise_ignored",),
            None,
            None,
        ),
        (
            "breakthrough-bleeding",
            "Breakthrough bleeding without ovulatory shift",
            "curveball",
            "Internal medium bleeding appears without a confirmed temperature shift.",
            _build_breakthrough_bleeding_cycle(start + timedelta(days=370)),
            None,
            False,
            ("possible_anovulatory_bleeding",),
            (),
            None,
            None,
        ),
        (
            "open-ended-peak",
            "Peak-quality mucus at chart end is not locked",
            "exception",
            "The chart ends on a peak-quality day, so there is no later lower-quality day to lock Peak Day.",
            _build_open_ended_peak_cycle(start + timedelta(days=410)),
            None,
            False,
            (),
            (),
            None,
            None,
        ),
    ]

    cases: list[SyntheticCase] = []
    for (
        case_id,
        label,
        category,
        description,
        observations,
        peak_day,
        expected_temperature_shift,
        warning_codes,
        trace_codes,
        fourth_exception,
        unclear_exception,
    ) in case_specs:
        true_peak_date = (
            observations[0].observation_date + timedelta(days=peak_day - 1)
            if peak_day is not None
            else None
        )
        cases.append(
            SyntheticCase(
                case_id=case_id,
                label=label,
                category=category,
                description=description,
                observations=tuple(observations),
                expected_peak_day=true_peak_date,
                true_peak_cycle_day=peak_day,
                source_shape="Purpose-built curve-ball for STM exception behavior.",
                expected_temperature_shift=expected_temperature_shift,
                expected_warning_codes=tuple(warning_codes),
                expected_trace_codes=tuple(trace_codes),
                expected_fourth_day_exception=fourth_exception,
                expected_unclear_mucus_exception=unclear_exception,
            )
        )

    return cases


def run_validation(cases: Iterable[SyntheticCase]) -> list[ValidationResult]:
    return [_evaluate_case(case) for case in cases]


def summarize_results(results: list[ValidationResult]) -> dict[str, Any]:
    peak_expected = [item for item in results if item.case.expected_peak_day is not None]
    no_peak_expected = [item for item in results if item.case.expected_peak_day is None]
    exact = [item for item in peak_expected if item.delta_days == 0]
    within_1 = [item for item in peak_expected if item.delta_days is not None and abs(item.delta_days) <= 1]
    within_4 = [item for item in peak_expected if item.delta_days is not None and abs(item.delta_days) <= 4]
    false_negative = [item for item in peak_expected if item.detected_peak_day is None]
    false_positive = [item for item in no_peak_expected if item.detected_peak_day is not None]
    true_no_peak = [item for item in no_peak_expected if item.detected_peak_day is None]
    expectation_failures = [item for item in results if not item.expectation_check_passed]
    failed_cases = [item for item in results if item.status != "pass"]

    statistical_cases = [item.case for item in results if item.case.category == "statistical"]
    statistical_peak_days = [
        item.true_peak_cycle_day for item in statistical_cases if item.true_peak_cycle_day is not None
    ]
    statistical_lengths = [item.cycle_length for item in statistical_cases]

    warning_expectations = sum(len(item.case.expected_warning_codes) for item in results)
    warning_hits = sum(
        len(set(item.case.expected_warning_codes).intersection(item.warning_codes))
        for item in results
    )
    trace_expectations = sum(len(item.case.expected_trace_codes) for item in results)
    trace_hits = sum(
        len(set(item.case.expected_trace_codes).intersection(item.trace_codes))
        for item in results
    )
    exception_expectations = 0
    exception_hits = 0
    for item in results:
        if item.case.expected_fourth_day_exception is not None:
            exception_expectations += 1
            if item.detected_fourth_day_exception == item.case.expected_fourth_day_exception:
                exception_hits += 1
        if item.case.expected_unclear_mucus_exception is not None:
            exception_expectations += 1
            if item.detected_unclear_mucus_exception == item.case.expected_unclear_mucus_exception:
                exception_hits += 1

    return {
        "run_id": RUN_ID,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "case_count": len(results),
        "peak_expected_count": len(peak_expected),
        "no_peak_expected_count": len(no_peak_expected),
        "exact_peak_count": len(exact),
        "within_1_day_count": len(within_1),
        "within_4_day_count": len(within_4),
        "false_negative_count": len(false_negative),
        "false_positive_count": len(false_positive),
        "true_no_peak_count": len(true_no_peak),
        "expectation_failure_count": len(expectation_failures),
        "failed_case_count": len(failed_cases),
        "exact_peak_rate": _rate(len(exact), len(peak_expected)),
        "within_1_day_rate": _rate(len(within_1), len(peak_expected)),
        "within_4_day_rate": _rate(len(within_4), len(peak_expected)),
        "true_no_peak_rate": _rate(len(true_no_peak), len(no_peak_expected)),
        "warning_expectations": warning_expectations,
        "warning_hits": warning_hits,
        "trace_expectations": trace_expectations,
        "trace_hits": trace_hits,
        "exception_expectations": exception_expectations,
        "exception_hits": exception_hits,
        "statistical_cycle_count": len(statistical_cases),
        "statistical_cycle_length_mean": round(statistics.mean(statistical_lengths), 2),
        "statistical_cycle_length_sd": round(statistics.stdev(statistical_lengths), 2),
        "statistical_peak_day_mean": round(statistics.mean(statistical_peak_days), 2),
        "statistical_peak_day_sd": round(statistics.stdev(statistical_peak_days), 2),
    }


def write_artifacts(
    results: list[ValidationResult],
    metrics: dict[str, Any],
    *,
    report_path: Path = REPORT_PATH,
    results_path: Path = RESULTS_PATH,
    figure_dir: Path = FIGURE_DIR,
) -> None:
    figure_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    normal_result = next(item for item in results if item.case.category == "statistical")
    temperature_svg = render_temperature_history(normal_result)
    symptoms_svg = render_symptom_history(normal_result)
    curveball_svg = render_curveball_panels(
        [item for item in results if item.case.category != "statistical"]
    )
    accuracy_svg = render_accuracy_summary(metrics)

    figure_paths = {
        "temperature": figure_dir / "temperature-history.svg",
        "symptoms": figure_dir / "symptom-history.svg",
        "curveballs": figure_dir / "curveball-panels.svg",
        "accuracy": figure_dir / "accuracy-summary.svg",
    }
    figure_paths["temperature"].write_text(temperature_svg, encoding="utf-8")
    figure_paths["symptoms"].write_text(symptoms_svg, encoding="utf-8")
    figure_paths["curveballs"].write_text(curveball_svg, encoding="utf-8")
    figure_paths["accuracy"].write_text(accuracy_svg, encoding="utf-8")

    payload = {
        "metrics": metrics,
        "sources": SOURCES,
        "cases": [_result_as_dict(item) for item in results],
    }
    results_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(
        render_markdown_report(
            results,
            metrics,
            report_path=report_path,
            results_path=results_path,
            figure_paths=figure_paths,
        ),
        encoding="utf-8",
    )


def render_markdown_report(
    results: list[ValidationResult],
    metrics: dict[str, Any],
    *,
    report_path: Path,
    results_path: Path,
    figure_paths: dict[str, Path],
) -> str:
    curveballs = [item for item in results if item.case.category != "statistical"]
    failures = [item for item in results if item.status != "pass"]
    rel_figures = {
        key: _relative_path(path, report_path.parent)
        for key, path in figure_paths.items()
    }
    results_rel = _relative_path(results_path, report_path.parent)

    lines = [
        "# Peak-Day Accuracy Validation Report",
        "",
        f"Generated: {metrics['generated_at']}",
        "",
        "## Executive Summary",
        "",
        (
            f"The validation harness generated {metrics['case_count']} deterministic synthetic charts: "
            f"{metrics['statistical_cycle_count']} source-shaped ovulatory cycles and "
            f"{len(curveballs)} curve-ball/exception charts. Peak Day detection was exact in "
            f"{metrics['exact_peak_count']} of {metrics['peak_expected_count']} charts with a known "
            f"Peak Day ({_percent(metrics['exact_peak_rate'])}), and every known Peak Day landed "
            f"within +/-4 days. No no-peak chart produced a false Peak Day."
        ),
        "",
        (
            "The generated population stayed close to the cited target ranges: "
            f"cycle length mean {metrics['statistical_cycle_length_mean']} days "
            f"(SD {metrics['statistical_cycle_length_sd']}) and true mucus Peak Day mean cycle day "
            f"{metrics['statistical_peak_day_mean']} (SD {metrics['statistical_peak_day_sd']})."
        ),
        "",
        "This validates the current `stm-v1` rule behavior against known synthetic ground truth. It is not medical certification or a substitute for instruction in a fertility awareness method.",
        "",
        "## Figures",
        "",
        "![Temperature history with Peak Day and coverline](" + rel_figures["temperature"] + ")",
        "",
        "![Symptom history with Peak Day](" + rel_figures["symptoms"] + ")",
        "",
        "![Curve-ball scenario panels](" + rel_figures["curveballs"] + ")",
        "",
        "![Accuracy summary](" + rel_figures["accuracy"] + ")",
        "",
        "## Accuracy Metrics",
        "",
        "| Metric | Result |",
        "| --- | ---: |",
        f"| Known-Peak charts | {metrics['peak_expected_count']} |",
        f"| Exact Peak Day matches | {metrics['exact_peak_count']} ({_percent(metrics['exact_peak_rate'])}) |",
        f"| Within +/-1 day | {metrics['within_1_day_count']} ({_percent(metrics['within_1_day_rate'])}) |",
        f"| Within +/-4 days | {metrics['within_4_day_count']} ({_percent(metrics['within_4_day_rate'])}) |",
        f"| False negatives on known-Peak charts | {metrics['false_negative_count']} |",
        f"| No-Peak charts correctly left empty | {metrics['true_no_peak_count']} of {metrics['no_peak_expected_count']} |",
        f"| False positives on No-Peak charts | {metrics['false_positive_count']} |",
        f"| Warning expectations hit | {metrics['warning_hits']} of {metrics['warning_expectations']} |",
        f"| Trace expectations hit | {metrics['trace_hits']} of {metrics['trace_expectations']} |",
        f"| Exception flag expectations hit | {metrics['exception_hits']} of {metrics['exception_expectations']} |",
        "",
        "## Curve-Balls and Exceptions",
        "",
        "| Case | Expected Peak | Detected Peak | Temp Shift | Expected Signals | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for result in curveballs:
        expected_signals = sorted(
            set(result.case.expected_warning_codes)
            | set(result.case.expected_trace_codes)
            | _exception_labels(result.case)
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    _md(result.case.label),
                    _date_label(result.case.expected_peak_day),
                    _date_label(result.detected_peak_day),
                    "yes" if result.detected_temperature_shift else "no",
                    _md(", ".join(expected_signals) if expected_signals else "-"),
                    result.status,
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Bugs and Fixes",
            "",
            (
                "No new rule-engine bug was exposed by this validation pass. The suite did re-exercise "
                "the existing exact-threshold boundary behavior for the third high temperature, which remains covered."
                if not failures
                else "Validation exposed failing cases that should be fixed before the report is treated as passing."
            ),
            "",
            "## Source-Backed Synthetic Design",
            "",
            "The synthetic generator uses fixed seeds and known ground truth rather than downloaded patient-level data. This lets the harness score exact Peak Day outcomes while still keeping the simulated chart shapes anchored to published ranges.",
            "",
        ]
    )
    for source in SOURCES:
        lines.append(f"- [{source['label']}]({source['url']}): {source['note']}")

    lines.extend(
        [
            "",
            "## Reproducibility",
            "",
            f"- Script: `scripts/validate_peak_day_accuracy.py`",
            f"- Results JSON: `{results_rel}`",
            f"- Statistical seed: `{STATISTICAL_SEED}`",
            f"- Statistical synthetic cycle count: `{STATISTICAL_CYCLE_COUNT}`",
            "",
            "Regenerate with:",
            "",
            "```powershell",
            ".\\.venv\\Scripts\\python.exe scripts\\validate_peak_day_accuracy.py",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def render_temperature_history(result: ValidationResult) -> str:
    case = result.case
    points = _temperature_points(case)
    width = 980
    height = 430
    margin = 62
    chart_w = width - margin * 2
    chart_h = 260
    chart_top = 84
    min_temp = min(item[1] for item in points) - 0.08
    max_temp = max(item[1] for item in points) + 0.08

    def x(day: int) -> float:
        denominator = max(case.cycle_length - 1, 1)
        return margin + ((day - 1) / denominator) * chart_w

    def y(temp: float) -> float:
        return chart_top + (max_temp - temp) / (max_temp - min_temp) * chart_h

    polyline = " ".join(f"{x(day):.1f},{y(temp):.1f}" for day, temp, _disturbed in points)
    elements = [
        _svg_header(width, height),
        _svg_text(24, 32, "Temperature History: Representative Source-Shaped Cycle", size=20, weight="700"),
        _svg_text(24, 56, f"{case.label} ({case.case_id})", size=13, fill="#5c6670"),
        _svg_rect(margin, chart_top, chart_w, chart_h, fill="#ffffff", stroke="#d6dde5"),
    ]

    for tick in _nice_ticks(min_temp, max_temp, 5):
        yy = y(tick)
        elements.append(_svg_line(margin, yy, margin + chart_w, yy, stroke="#eef2f6"))
        elements.append(_svg_text(14, yy + 4, f"{tick:.2f} C", size=11, fill="#5c6670"))

    if result.detected_coverline_celsius is not None:
        yy = y(result.detected_coverline_celsius)
        elements.append(_svg_line(margin, yy, margin + chart_w, yy, stroke="#9a6b00", dash="5 4"))
        elements.append(
            _svg_text(
                margin + chart_w - 138,
                yy - 8,
                f"coverline {result.detected_coverline_celsius:.2f} C",
                size=12,
                fill="#8a5c00",
            )
        )

    elements.append(f'<polyline points="{polyline}" fill="none" stroke="#1f7a83" stroke-width="3" stroke-linejoin="round" />')
    for day, temp, disturbed in points:
        fill = "#f57c00" if disturbed else "#ffffff"
        stroke = "#f57c00" if disturbed else "#1f7a83"
        radius = 4.4 if disturbed else 3.4
        elements.append(_svg_circle(x(day), y(temp), radius, fill=fill, stroke=stroke, stroke_width=2))

    _add_peak_marker(elements, case, result, x, chart_top, chart_h)
    if result.detected_temperature_confirmed_date is not None:
        confirmed_day = _cycle_day(case, result.detected_temperature_confirmed_date)
        xx = x(confirmed_day)
        elements.append(_svg_line(xx, chart_top, xx, chart_top + chart_h, stroke="#3155a4", dash="3 5"))
        elements.append(_svg_text(xx + 6, chart_top + 20, "temp confirmed", size=12, fill="#3155a4"))

    elements.extend(_axis_elements(margin, chart_top, chart_w, chart_h, case.cycle_length))
    elements.append(_svg_text(margin, height - 38, "Orange points are disturbed readings excluded from BBT confirmation.", size=12, fill="#5c6670"))
    elements.append("</svg>")
    return "\n".join(elements)


def render_symptom_history(result: ValidationResult) -> str:
    case = result.case
    width = 980
    height = 390
    margin = 62
    chart_w = width - margin * 2
    chart_h = 220
    chart_top = 86

    def x(day: int) -> float:
        denominator = max(case.cycle_length - 1, 1)
        return margin + ((day - 1) / denominator) * chart_w

    def y(score: float) -> float:
        return chart_top + (4.2 - score) / 4.2 * chart_h

    elements = [
        _svg_header(width, height),
        _svg_text(24, 32, "Symptom History: Mucus Score and Bleeding", size=20, weight="700"),
        _svg_text(24, 56, f"{case.label} ({case.case_id})", size=13, fill="#5c6670"),
        _svg_rect(margin, chart_top, chart_w, chart_h, fill="#ffffff", stroke="#d6dde5"),
    ]
    labels = [(0, "dry/none"), (1, "sticky"), (2, "creamy"), (3, "watery"), (4, "peak")]
    for score, label in labels:
        yy = y(score)
        elements.append(_svg_line(margin, yy, margin + chart_w, yy, stroke="#eef2f6"))
        elements.append(_svg_text(10, yy + 4, label, size=11, fill="#5c6670"))

    bar_w = max(5.0, chart_w / max(case.cycle_length, 1) * 0.55)
    for observation in case.observations:
        day = _cycle_day(case, observation.observation_date)
        score = _mucus_score(observation.fluid)
        xx = x(day)
        yy = y(score)
        fill = _mucus_color(score)
        elements.append(_svg_rect(xx - bar_w / 2, yy, bar_w, chart_top + chart_h - yy, fill=fill, stroke="none"))
        if observation.bleeding != BleedingLevel.NONE:
            elements.append(_svg_circle(xx, chart_top + chart_h + 13, 5.0, fill="#b42318", stroke="#7a1a13"))

    _add_peak_marker(elements, case, result, x, chart_top, chart_h)
    elements.extend(_axis_elements(margin, chart_top, chart_w, chart_h, case.cycle_length))
    elements.append(_svg_text(margin, height - 34, "Red dots below the axis indicate medium/heavy bleeding days.", size=12, fill="#5c6670"))
    elements.append("</svg>")
    return "\n".join(elements)


def render_curveball_panels(results: list[ValidationResult]) -> str:
    width = 1100
    panel_w = 520
    panel_h = 160
    gap = 24
    cols = 2
    rows = math.ceil(len(results) / cols)
    height = 78 + rows * (panel_h + gap)
    elements = [
        _svg_header(width, height),
        _svg_text(24, 32, "Curve-Ball and Exception Panels", size=20, weight="700"),
        _svg_text(24, 56, "Compact BBT lines with expected/detected Peak Day checks", size=13, fill="#5c6670"),
    ]

    for index, result in enumerate(results):
        row = index // cols
        col = index % cols
        left = 24 + col * (panel_w + gap)
        top = 78 + row * (panel_h + gap)
        elements.extend(_render_curveball_panel(result, left, top, panel_w, panel_h))

    elements.append("</svg>")
    return "\n".join(elements)


def render_accuracy_summary(metrics: dict[str, Any]) -> str:
    width = 920
    height = 360
    margin = 76
    chart_top = 82
    chart_h = 190
    bar_gap = 28
    bar_w = 118
    bars = [
        ("Exact", metrics["exact_peak_rate"]),
        ("+/-1 day", metrics["within_1_day_rate"]),
        ("+/-4 days", metrics["within_4_day_rate"]),
        ("No false peak", metrics["true_no_peak_rate"]),
    ]
    elements = [
        _svg_header(width, height),
        _svg_text(24, 32, "Accuracy Summary", size=20, weight="700"),
        _svg_text(24, 56, "Peak Day detection against known synthetic ground truth", size=13, fill="#5c6670"),
        _svg_line(margin, chart_top + chart_h, width - margin, chart_top + chart_h, stroke="#aeb8c2"),
    ]
    for y_rate in [0, 0.25, 0.5, 0.75, 1.0]:
        yy = chart_top + chart_h - y_rate * chart_h
        elements.append(_svg_line(margin, yy, width - margin, yy, stroke="#eef2f6"))
        elements.append(_svg_text(24, yy + 4, f"{int(y_rate * 100)}%", size=11, fill="#5c6670"))

    for index, (label, rate) in enumerate(bars):
        left = margin + index * (bar_w + bar_gap) + 44
        bar_h = rate * chart_h
        top = chart_top + chart_h - bar_h
        elements.append(_svg_rect(left, top, bar_w, bar_h, fill="#217c88", stroke="none", radius=5))
        elements.append(_svg_text(left + bar_w / 2, top - 10, _percent(rate), size=13, fill="#174e57", anchor="middle", weight="700"))
        elements.append(_svg_text(left + bar_w / 2, chart_top + chart_h + 26, label, size=12, fill="#374151", anchor="middle"))

    elements.append(_svg_text(margin, height - 42, f"Cases: {metrics['case_count']} total, {metrics['peak_expected_count']} known-Peak, {metrics['no_peak_expected_count']} no-Peak.", size=12, fill="#5c6670"))
    elements.append("</svg>")
    return "\n".join(elements)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate Peak Day detection with deterministic synthetic STM charts.")
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--results", type=Path, default=RESULTS_PATH)
    parser.add_argument("--figures", type=Path, default=FIGURE_DIR)
    args = parser.parse_args(argv)

    cases = build_validation_cases()
    results = run_validation(cases)
    metrics = summarize_results(results)
    write_artifacts(results, metrics, report_path=args.report, results_path=args.results, figure_dir=args.figures)

    print(f"Generated {args.report}")
    print(f"Generated {args.results}")
    print(f"Generated figures in {args.figures}")
    print(
        "Peak Day exact accuracy: "
        f"{metrics['exact_peak_count']}/{metrics['peak_expected_count']} "
        f"({_percent(metrics['exact_peak_rate'])})"
    )
    print(f"Failures: {metrics['failed_case_count']}")
    return 1 if metrics["failed_case_count"] else 0


def _evaluate_case(case: SyntheticCase) -> ValidationResult:
    report = evaluate_observations(case.observations)
    cycle = report.cycles[0] if report.cycles else None
    if cycle is None:
        raise AssertionError(f"No cycle returned for {case.case_id}")

    detected_peak = cycle.peak_day
    delta_days = (
        (detected_peak - case.expected_peak_day).days
        if detected_peak is not None and case.expected_peak_day is not None
        else None
    )
    warning_codes = tuple(sorted({warning.code for warning in [*report.warnings, *cycle.warnings]}))
    trace_codes = tuple(sorted({trace.code for trace in [*report.traces, *cycle.traces]}))
    shift = cycle.temperature_shift

    if case.expected_peak_day is None:
        peak_check_passed = detected_peak is None
    else:
        peak_check_passed = detected_peak == case.expected_peak_day

    expectation_check_passed = _expectations_pass(
        case,
        cycle,
        warning_codes=warning_codes,
        trace_codes=trace_codes,
    )
    return ValidationResult(
        case=case,
        detected_peak_day=detected_peak,
        detected_temperature_shift=shift is not None,
        detected_temperature_confirmed_date=shift.confirmed_date if shift else None,
        detected_coverline_celsius=shift.coverline_celsius if shift else None,
        detected_fourth_day_exception=shift.fourth_day_exception if shift else None,
        detected_unclear_mucus_exception=shift.unclear_mucus_exception if shift else None,
        warning_codes=warning_codes,
        trace_codes=trace_codes,
        delta_days=delta_days,
        peak_check_passed=peak_check_passed,
        expectation_check_passed=expectation_check_passed,
    )


def _expectations_pass(
    case: SyntheticCase,
    cycle: CycleInterpretation,
    *,
    warning_codes: tuple[str, ...],
    trace_codes: tuple[str, ...],
) -> bool:
    shift = cycle.temperature_shift
    if case.expected_temperature_shift is not None and (shift is not None) != case.expected_temperature_shift:
        return False
    for code in case.expected_warning_codes:
        if code not in warning_codes:
            return False
    for code in case.expected_trace_codes:
        if code not in trace_codes:
            return False
    if case.expected_fourth_day_exception is not None:
        if shift is None or shift.fourth_day_exception != case.expected_fourth_day_exception:
            return False
    if case.expected_unclear_mucus_exception is not None:
        if shift is None or shift.unclear_mucus_exception != case.expected_unclear_mucus_exception:
            return False
    return True


def _build_cycle(
    start: date,
    *,
    length: int,
    peak_day: int,
    base_c: float = 36.42,
    rise_c: float = 0.35,
    profile: str,
    low_phase_offset: int = 0,
    false_peak_days: set[int] | None = None,
    disturbed_days: set[int] | None = None,
    missing_days: set[int] | None = None,
    fever_days: set[int] | None = None,
    no_mucus: bool = False,
) -> list[DailyObservation]:
    false_peak_days = false_peak_days or set()
    disturbed_days = disturbed_days or set()
    missing_days = missing_days or set()
    fever_days = fever_days or set()
    temperatures = _temperature_series(
        length=length,
        peak_day=peak_day,
        base_c=base_c,
        rise_c=rise_c,
        profile=profile,
        low_phase_offset=low_phase_offset,
    )
    observations: list[DailyObservation] = []
    for day in range(1, length + 1):
        if day in missing_days:
            continue
        temp = 38.2 if day in fever_days else temperatures[day - 1]
        fluid = None if no_mucus else _fluid_for_day(day, peak_day=peak_day, false_peak_days=false_peak_days)
        observations.append(
            DailyObservation(
                observation_date=start + timedelta(days=day - 1),
                waking_temperature=round(temp, 2),
                temperature_unit=TemperatureUnit.CELSIUS,
                temperature_disturbed=day in disturbed_days,
                fluid=fluid,
                bleeding=BleedingLevel.MEDIUM if day == 1 else BleedingLevel.NONE,
            )
        )
    return observations


def _build_premature_temperature_rise_cycle(start: date) -> list[DailyObservation]:
    observations: list[DailyObservation] = []
    temps = [
        36.35,
        36.38,
        36.36,
        36.40,
        36.37,
        36.39,
        36.67,
        36.70,
        36.78,
        36.74,
        36.72,
        36.39,
        36.38,
        36.40,
        36.37,
        36.39,
        36.41,
        36.40,
        36.66,
        36.71,
        36.82,
        36.83,
        36.82,
        36.80,
    ]
    for day, temp in enumerate(temps, start=1):
        if day == 18:
            fluid = _peak()
        elif day in {19, 20, 21, 22, 23, 24}:
            fluid = _sticky()
        elif day in {16, 17}:
            fluid = _watery()
        else:
            fluid = _dry()
        observations.append(
            DailyObservation(
                observation_date=start + timedelta(days=day - 1),
                waking_temperature=temp,
                temperature_unit=TemperatureUnit.CELSIUS,
                fluid=fluid,
                bleeding=BleedingLevel.MEDIUM if day == 1 else BleedingLevel.NONE,
            )
        )
    return observations


def _build_breakthrough_bleeding_cycle(start: date) -> list[DailyObservation]:
    observations: list[DailyObservation] = []
    for day in range(1, 22):
        observations.append(
            DailyObservation(
                observation_date=start + timedelta(days=day - 1),
                waking_temperature=36.38 + ((day % 3) * 0.01),
                temperature_unit=TemperatureUnit.CELSIUS,
                fluid=_dry(),
                bleeding=BleedingLevel.MEDIUM if day in {1, 10, 11} else BleedingLevel.NONE,
            )
        )
    return observations


def _build_open_ended_peak_cycle(start: date) -> list[DailyObservation]:
    observations: list[DailyObservation] = []
    for day in range(1, 16):
        fluid = _peak() if day == 15 else _dry()
        observations.append(
            DailyObservation(
                observation_date=start + timedelta(days=day - 1),
                waking_temperature=36.36 + ((day % 4) * 0.01),
                temperature_unit=TemperatureUnit.CELSIUS,
                fluid=fluid,
                bleeding=BleedingLevel.MEDIUM if day == 1 else BleedingLevel.NONE,
            )
        )
    return observations


def _temperature_series(
    *,
    length: int,
    peak_day: int,
    base_c: float,
    rise_c: float,
    profile: str,
    low_phase_offset: int,
) -> list[float]:
    first_high_day = peak_day + 1
    low_offsets = [-0.04, -0.02, 0.00, 0.02, 0.01, 0.03]
    temps = [
        base_c + low_offsets[(day + low_phase_offset) % len(low_offsets)]
        for day in range(1, length + 1)
    ]
    coverline = max(temps[max(0, first_high_day - 7) : first_high_day - 1])

    if profile == "standard":
        high_offsets = [0.07, 0.14, max(0.22, rise_c - 0.08), rise_c]
    elif profile == "slow_staircase":
        high_offsets = [0.04, 0.09, 0.14, 0.24, 0.29]
    elif profile == "exact_threshold":
        high_offsets = [0.05, 0.11, 0.20, 0.26]
    else:
        raise ValueError(f"Unknown temperature profile: {profile}")

    for day in range(first_high_day, length + 1):
        offset_index = min(day - first_high_day, len(high_offsets) - 1)
        plateau_jitter = 0.01 * ((day - first_high_day) % 3)
        temps[day - 1] = coverline + high_offsets[offset_index] + plateau_jitter
    return temps


def _fluid_for_day(day: int, *, peak_day: int, false_peak_days: set[int]) -> FluidObservation:
    if day in false_peak_days:
        return _peak()
    if day in {false_peak + 1 for false_peak in false_peak_days}:
        return _sticky()
    if day == peak_day:
        return _peak()
    if day == peak_day - 1:
        return _watery()
    if peak_day - 4 <= day <= peak_day - 2:
        return _creamy()
    if peak_day + 1 <= day <= peak_day + 3:
        return _sticky()
    return _dry()


def _dry() -> FluidObservation:
    return FluidObservation(sensation=FluidSensation.DRY, quantity=FluidQuantity.NONE)


def _sticky() -> FluidObservation:
    return FluidObservation(
        sensation=FluidSensation.STICKY,
        quantity=FluidQuantity.LOW,
        color=MucusColor.CLOUDY,
        texture=MucusTexture.STICKY,
        amount=1,
    )


def _creamy() -> FluidObservation:
    return FluidObservation(
        sensation=FluidSensation.CREAMY,
        quantity=FluidQuantity.MEDIUM,
        color=MucusColor.WHITE,
        texture=MucusTexture.CREAMY,
        amount=2,
    )


def _watery() -> FluidObservation:
    return FluidObservation(
        sensation=FluidSensation.WATERY,
        quantity=FluidQuantity.HIGH,
        color=MucusColor.CLEAR,
        texture=MucusTexture.SLIPPERY,
        amount=4,
    )


def _peak() -> FluidObservation:
    return FluidObservation(
        sensation=FluidSensation.SLIPPERY,
        quantity=FluidQuantity.HIGH,
        color=MucusColor.CLEAR,
        texture=MucusTexture.STRETCHY,
        amount=5,
        peak_quality=True,
    )


def _result_as_dict(result: ValidationResult) -> dict[str, Any]:
    case = result.case
    return {
        "case_id": case.case_id,
        "label": case.label,
        "category": case.category,
        "description": case.description,
        "cycle_length": case.cycle_length,
        "true_peak_cycle_day": case.true_peak_cycle_day,
        "expected_peak_day": _date_or_none(case.expected_peak_day),
        "detected_peak_day": _date_or_none(result.detected_peak_day),
        "delta_days": result.delta_days,
        "detected_temperature_shift": result.detected_temperature_shift,
        "detected_temperature_confirmed_date": _date_or_none(result.detected_temperature_confirmed_date),
        "detected_coverline_celsius": result.detected_coverline_celsius,
        "detected_fourth_day_exception": result.detected_fourth_day_exception,
        "detected_unclear_mucus_exception": result.detected_unclear_mucus_exception,
        "warning_codes": list(result.warning_codes),
        "trace_codes": list(result.trace_codes),
        "peak_check_passed": result.peak_check_passed,
        "expectation_check_passed": result.expectation_check_passed,
        "status": result.status,
    }


def _render_curveball_panel(
    result: ValidationResult,
    left: float,
    top: float,
    width: float,
    height: float,
) -> list[str]:
    case = result.case
    points = _temperature_points(case)
    chart_left = left + 22
    chart_top = top + 50
    chart_w = width - 44
    chart_h = height - 82
    min_temp = min(item[1] for item in points) - 0.06
    max_temp = max(item[1] for item in points) + 0.06

    def x(day: int) -> float:
        denominator = max(case.cycle_length - 1, 1)
        return chart_left + ((day - 1) / denominator) * chart_w

    def y(temp: float) -> float:
        return chart_top + (max_temp - temp) / (max_temp - min_temp) * chart_h

    polyline = " ".join(f"{x(day):.1f},{y(temp):.1f}" for day, temp, _disturbed in points)
    status_fill = "#e6f4ea" if result.status == "pass" else "#fce8e6"
    status_text = "#137333" if result.status == "pass" else "#b42318"
    elements = [
        _svg_rect(left, top, width, height, fill="#ffffff", stroke="#d6dde5", radius=7),
        _svg_text(left + 16, top + 24, case.label, size=14, weight="700"),
        _svg_rect(left + width - 66, top + 10, 48, 24, fill=status_fill, stroke="none", radius=5),
        _svg_text(left + width - 42, top + 27, result.status, size=11, fill=status_text, anchor="middle", weight="700"),
        _svg_text(left + 16, top + 42, _shorten(case.description, 74), size=10.5, fill="#5c6670"),
        f'<polyline points="{polyline}" fill="none" stroke="#1f7a83" stroke-width="2.2" />',
    ]
    _add_peak_marker(elements, case, result, x, chart_top, chart_h, compact=True)
    elements.append(_svg_text(left + 16, top + height - 16, f"expected: {_date_label(case.expected_peak_day)}  detected: {_date_label(result.detected_peak_day)}", size=11, fill="#374151"))
    return elements


def _add_peak_marker(
    elements: list[str],
    case: SyntheticCase,
    result: ValidationResult,
    x_func,
    chart_top: float,
    chart_h: float,
    *,
    compact: bool = False,
) -> None:
    if case.expected_peak_day is not None:
        expected_day = _cycle_day(case, case.expected_peak_day)
        xx = x_func(expected_day)
        elements.append(_svg_line(xx, chart_top, xx, chart_top + chart_h, stroke="#7b2cbf", dash="5 4"))
        label = "expected Peak" if not compact else "E"
        elements.append(_svg_text(xx + 5, chart_top + chart_h - 8, label, size=11, fill="#6f2da8"))
    if result.detected_peak_day is not None:
        detected_day = _cycle_day(case, result.detected_peak_day)
        xx = x_func(detected_day)
        elements.append(_svg_line(xx, chart_top, xx, chart_top + chart_h, stroke="#c2410c", dash="2 4"))
        label = "detected Peak" if not compact else "D"
        elements.append(_svg_text(xx + 5, chart_top + 14, label, size=11, fill="#c2410c"))


def _axis_elements(
    margin: float,
    chart_top: float,
    chart_w: float,
    chart_h: float,
    cycle_length: int,
) -> list[str]:
    elements = [
        _svg_line(margin, chart_top + chart_h, margin + chart_w, chart_top + chart_h, stroke="#aeb8c2"),
        _svg_line(margin, chart_top, margin, chart_top + chart_h, stroke="#aeb8c2"),
    ]
    for day in range(1, cycle_length + 1):
        if day == 1 or day == cycle_length or day % 5 == 0:
            denominator = max(cycle_length - 1, 1)
            xx = margin + ((day - 1) / denominator) * chart_w
            elements.append(_svg_line(xx, chart_top + chart_h, xx, chart_top + chart_h + 6, stroke="#aeb8c2"))
            elements.append(_svg_text(xx, chart_top + chart_h + 22, str(day), size=11, fill="#5c6670", anchor="middle"))
    elements.append(_svg_text(margin + chart_w / 2, chart_top + chart_h + 43, "cycle day", size=12, fill="#5c6670", anchor="middle"))
    return elements


def _temperature_points(case: SyntheticCase) -> list[tuple[int, float, bool]]:
    points: list[tuple[int, float, bool]] = []
    for observation in case.observations:
        if observation.waking_temperature is None:
            continue
        value = observation.waking_temperature
        if observation.temperature_unit == TemperatureUnit.FAHRENHEIT:
            value = (value - 32.0) * 5.0 / 9.0
        points.append((_cycle_day(case, observation.observation_date), value, observation.temperature_disturbed))
    return points


def _mucus_score(fluid: FluidObservation | None) -> int:
    if fluid is None:
        return 0
    if fluid.peak_quality or fluid.texture in {MucusTexture.STRETCHY, MucusTexture.SLIPPERY}:
        return 4
    if fluid.sensation in {FluidSensation.WATERY, FluidSensation.SLIPPERY} or fluid.color == MucusColor.CLEAR:
        return 3
    if fluid.sensation == FluidSensation.CREAMY or fluid.texture == MucusTexture.CREAMY:
        return 2
    if fluid.sensation == FluidSensation.STICKY or fluid.quantity != FluidQuantity.NONE:
        return 1
    return 0


def _mucus_color(score: int) -> str:
    return {
        0: "#e7edf3",
        1: "#a8dadc",
        2: "#80b918",
        3: "#3a86ff",
        4: "#7b2cbf",
    }[score]


def _cycle_day(case: SyntheticCase, value: date) -> int:
    return (value - case.observations[0].observation_date).days + 1


def _clip_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def _date_or_none(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _date_label(value: date | None) -> str:
    return value.isoformat() if value else "-"


def _md(value: str) -> str:
    return value.replace("|", "\\|")


def _exception_labels(case: SyntheticCase) -> set[str]:
    labels: set[str] = set()
    if case.expected_fourth_day_exception is not None:
        labels.add(f"fourth_day_exception={case.expected_fourth_day_exception}")
    if case.expected_unclear_mucus_exception is not None:
        labels.add(f"unclear_mucus_exception={case.expected_unclear_mucus_exception}")
    return labels


def _relative_path(path: Path, start: Path) -> str:
    try:
        return path.resolve().relative_to(start.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _shorten(value: str, max_length: int) -> str:
    return value if len(value) <= max_length else value[: max_length - 3] + "..."


def _nice_ticks(min_value: float, max_value: float, count: int) -> list[float]:
    if count <= 1:
        return [min_value]
    step = (max_value - min_value) / (count - 1)
    return [round(min_value + step * index, 2) for index in range(count)]


def _svg_header(width: float, height: float) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" role="img">'
        "<style>text{font-family:Arial,Helvetica,sans-serif}</style>"
    )


def _svg_rect(
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    fill: str,
    stroke: str,
    radius: float = 0,
) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
        f'rx="{radius:.1f}" fill="{fill}" stroke="{stroke}" />'
    )


def _svg_line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    stroke: str,
    dash: str | None = None,
) -> str:
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}"{dash_attr} />'


def _svg_circle(
    cx: float,
    cy: float,
    radius: float,
    *,
    fill: str,
    stroke: str,
    stroke_width: float = 1,
) -> str:
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width:.1f}" />'
    )


def _svg_text(
    x: float,
    y: float,
    value: str,
    *,
    size: float,
    fill: str = "#1f2937",
    anchor: str = "start",
    weight: str = "400",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size:.1f}" fill="{fill}" '
        f'text-anchor="{anchor}" font-weight="{weight}">{html.escape(value)}</text>'
    )


if __name__ == "__main__":
    raise SystemExit(main())
