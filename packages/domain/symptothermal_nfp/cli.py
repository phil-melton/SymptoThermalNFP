from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .models import AppSettings, CervicalPositionObservation, DailyObservation, FluidObservation, parse_hhmm_time, parse_iso_date
from .storage import LocalStore
from .taxonomy import (
    BleedingLevel,
    CervixFirmness,
    CervixHeight,
    CervixOpening,
    FluidQuantity,
    FluidSensation,
    TemperatureUnit,
)

DEFAULT_DB_PATH = "data/local.db"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="symptothermal",
        description="Local-first sympto-thermal charting CLI",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help="Path to SQLite database file",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db", help="Create or migrate the local database")
    init_db.set_defaults(handler=handle_init_db)

    set_settings = subparsers.add_parser("set-settings", help="Update app-level charting settings")
    set_settings.add_argument("--temperature-unit", choices=_enum_values(TemperatureUnit))
    set_settings.add_argument("--wake-time", help="Default wake time in HH:MM format")
    track_group = set_settings.add_mutually_exclusive_group()
    track_group.add_argument(
        "--track-cervical-position",
        dest="track_cervical_position",
        action="store_true",
        help="Enable cervical position tracking in entry workflow",
    )
    track_group.add_argument(
        "--no-track-cervical-position",
        dest="track_cervical_position",
        action="store_false",
        help="Disable cervical position tracking in entry workflow",
    )
    set_settings.set_defaults(track_cervical_position=None, handler=handle_set_settings)

    show_settings = subparsers.add_parser("show-settings", help="Show current app settings")
    show_settings.set_defaults(handler=handle_show_settings)

    log_observation = subparsers.add_parser("log-observation", help="Insert or update one daily observation")
    log_observation.add_argument("--date", help="Observation date in YYYY-MM-DD format (defaults to today)")
    log_observation.add_argument("--temperature", type=float, help="Waking temperature value")
    log_observation.add_argument("--temperature-time", help="Time temperature was taken (HH:MM)")
    log_observation.add_argument(
        "--temperature-disturbed",
        action="store_true",
        help="Mark that sleep/measurement conditions were disturbed",
    )
    log_observation.add_argument("--fluid-sensation", choices=_enum_values(FluidSensation))
    log_observation.add_argument("--fluid-quantity", choices=_enum_values(FluidQuantity))
    log_observation.add_argument("--fluid-peak", action="store_true")
    log_observation.add_argument("--cervix-height", choices=_enum_values(CervixHeight))
    log_observation.add_argument("--cervix-firmness", choices=_enum_values(CervixFirmness))
    log_observation.add_argument("--cervix-opening", choices=_enum_values(CervixOpening))
    log_observation.add_argument(
        "--bleeding",
        choices=_enum_values(BleedingLevel),
        default=BleedingLevel.NONE.value,
    )
    log_observation.add_argument("--notes", default="")
    log_observation.set_defaults(handler=handle_log_observation)

    list_observations = subparsers.add_parser("list-observations", help="List logged observations")
    list_observations.add_argument("--start", help="Filter start date YYYY-MM-DD")
    list_observations.add_argument("--end", help="Filter end date YYYY-MM-DD")
    list_observations.set_defaults(handler=handle_list_observations)

    list_cycles = subparsers.add_parser("list-cycles", help="List cycle snapshots")
    list_cycles.add_argument("--start", help="Filter start date YYYY-MM-DD")
    list_cycles.add_argument("--end", help="Filter end date YYYY-MM-DD")
    list_cycles.set_defaults(handler=handle_list_cycles)

    plot_cycle_parser = subparsers.add_parser("plot-cycle", help="Evaluate and plot a specific cycle")
    plot_cycle_parser.add_argument("--cycle-index", type=int, required=True, help="The index of the cycle to plot")
    plot_cycle_parser.add_argument("--save", help="Path to save the generated image (e.g., cycle.png)")
    plot_cycle_parser.set_defaults(handler=handle_plot_cycle)

    return parser


def handle_init_db(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    store.initialize()
    print(f"Database initialized at {Path(args.db).resolve()}")
    return 0


def handle_set_settings(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    store.initialize()
    existing = store.load_settings()

    temperature_unit = TemperatureUnit(args.temperature_unit) if args.temperature_unit else existing.temperature_unit
    wake_time = args.wake_time if args.wake_time else existing.default_wake_time
    track_cervical_position = (
        args.track_cervical_position
        if args.track_cervical_position is not None
        else existing.track_cervical_position
    )

    updated = AppSettings(
        temperature_unit=temperature_unit,
        default_wake_time=wake_time,
        track_cervical_position=track_cervical_position,
    )
    store.save_settings(updated)
    print("Settings updated")
    return 0


def handle_show_settings(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    store.initialize()
    settings = store.load_settings()
    print(f"temperature_unit: {settings.temperature_unit.value}")
    print(f"default_wake_time: {settings.default_wake_time}")
    print(f"track_cervical_position: {settings.track_cervical_position}")
    return 0


def handle_log_observation(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    store.initialize()
    settings = store.load_settings()

    observation_date = parse_iso_date(args.date) if args.date else date.today()
    temperature_time = parse_hhmm_time(args.temperature_time) if args.temperature_time else None
    fluid = _build_fluid_observation(args)
    cervical_position = _build_cervical_position(args)

    observation = DailyObservation(
        observation_date=observation_date,
        waking_temperature=args.temperature,
        temperature_time=temperature_time,
        temperature_disturbed=bool(args.temperature_disturbed),
        fluid=fluid,
        cervical_position=cervical_position,
        bleeding=BleedingLevel(args.bleeding),
        notes=args.notes,
    )

    store.upsert_observation(observation, settings.temperature_unit)
    print(f"Saved observation for {observation.observation_date.isoformat()}")
    return 0


def handle_list_observations(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    store.initialize()

    start = parse_iso_date(args.start).isoformat() if args.start else None
    end = parse_iso_date(args.end).isoformat() if args.end else None

    observations = store.list_observations(start_date=start, end_date=end)
    if not observations:
        print("No observations found")
        return 0

    rows: list[list[str]] = []
    for observation in observations:
        rows.append(
            [
                observation.observation_date.isoformat(),
                "-" if observation.waking_temperature is None else f"{observation.waking_temperature:.2f}",
                "yes" if observation.temperature_disturbed else "no",
                observation.fluid.sensation.value if observation.fluid else "-",
                observation.bleeding.value,
                _truncate(observation.notes, 32),
            ]
        )

    _print_table(
        headers=["Date", "Temp", "Disturbed", "Fluid", "Bleeding", "Notes"],
        rows=rows,
    )
    return 0


def handle_list_cycles(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    store.initialize()

    start = parse_iso_date(args.start).isoformat() if args.start else None
    end = parse_iso_date(args.end).isoformat() if args.end else None
    cycles = store.list_cycle_snapshots(start_date=start, end_date=end)

    if not cycles:
        print("No cycle snapshots available")
        return 0

    rows = [
        [
            str(cycle.cycle_index),
            cycle.start_date.isoformat(),
            cycle.end_date.isoformat(),
            str(cycle.span_days),
            str(cycle.logged_days),
            "yes" if cycle.starts_with_menses else "no",
        ]
        for cycle in cycles
    ]

    _print_table(
        headers=["Cycle", "Start", "End", "Span Days", "Logged Days", "Menses Start"],
        rows=rows,
    )
    return 0


def handle_plot_cycle(args: argparse.Namespace) -> int:
    store = _store_from_args(args)
    store.initialize()

    # Find the cycle snapshot for the given index
    cycles = store.list_cycle_snapshots()
    target_cycle = None
    for c in cycles:
        if c.cycle_index == args.cycle_index:
            target_cycle = c
            break

    if not target_cycle:
        print(f"Cycle {args.cycle_index} not found.")
        return 1

    # Fetch all observations for the cycle
    observations = store.list_observations(
        start_date=target_cycle.start_date.isoformat(),
        end_date=target_cycle.end_date.isoformat()
    )

    if not observations:
        print(f"No observations found for cycle {args.cycle_index}.")
        return 1

    settings = store.load_settings()
    from .plot import plot_cycle
    plot_cycle(observations, settings=settings, save_path=args.save)
    return 0


def _store_from_args(args: argparse.Namespace) -> LocalStore:
    return LocalStore(Path(args.db))


def _build_fluid_observation(args: argparse.Namespace) -> FluidObservation | None:
    if args.fluid_sensation is None and (args.fluid_quantity is not None or args.fluid_peak):
        raise ValueError("Provide --fluid-sensation when using --fluid-quantity or --fluid-peak")
    if args.fluid_sensation is None:
        return None
    quantity = FluidQuantity(args.fluid_quantity) if args.fluid_quantity else FluidQuantity.NONE
    return FluidObservation(
        sensation=FluidSensation(args.fluid_sensation),
        quantity=quantity,
        peak_quality=bool(args.fluid_peak),
    )


def _build_cervical_position(args: argparse.Namespace) -> CervicalPositionObservation | None:
    parts = [args.cervix_height, args.cervix_firmness, args.cervix_opening]
    if not any(parts):
        return None
    if not all(parts):
        raise ValueError(
            "Provide --cervix-height, --cervix-firmness, and --cervix-opening together"
        )
    return CervicalPositionObservation(
        height=CervixHeight(args.cervix_height),
        firmness=CervixFirmness(args.cervix_firmness),
        opening=CervixOpening(args.cervix_opening),
    )


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for index, column in enumerate(row):
            widths[index] = max(widths[index], len(column))

    header_line = " | ".join(header.ljust(widths[index]) for index, header in enumerate(headers))
    separator_line = "-+-".join("-" * width for width in widths)
    print(header_line)
    print(separator_line)
    for row in rows:
        print(" | ".join(column.ljust(widths[index]) for index, column in enumerate(row)))


def _truncate(value: str, length: int) -> str:
    return value if len(value) <= length else value[: length - 3] + "..."


def _enum_values(enum_cls) -> list[str]:
    return [item.value for item in enum_cls]


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        return args.handler(args)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
