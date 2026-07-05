"""Tests for the Excel workbook persistence layer."""

from __future__ import annotations

import datetime as dt
import io

import pytest
from openpyxl import Workbook, load_workbook

from cycle_builders import peak, textbook_cycle
from symptothermal_nfp.excel_store import (
    OBSERVATIONS_SHEET,
    SETTINGS_SHEET,
    ExcelStore,
    ExcelStoreError,
    build_workbook,
    read_observations,
)
from symptothermal_nfp.models import AppSettings, DailyObservation, FluidObservation
from symptothermal_nfp.taxonomy import (
    BleedingLevel,
    CervixFirmness,
    CervixHeight,
    CervixOpening,
    FluidSensation,
    RuleContext,
    TemperatureUnit,
)

START = dt.date(2026, 3, 1)


@pytest.fixture()
def store(tmp_path):
    excel_store = ExcelStore(tmp_path / "data.xlsx")
    excel_store.initialize()
    return excel_store


def _workbook_bytes(rows: list[list], header: list[str], *, sheet_name: str = OBSERVATIONS_SHEET) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_initialize_creates_openable_workbook(store) -> None:
    workbook = load_workbook(store.path)
    assert OBSERVATIONS_SHEET in workbook.sheetnames
    assert SETTINGS_SHEET in workbook.sheetnames
    assert store.load_observations() == []


def test_full_observation_round_trip(store) -> None:
    original = textbook_cycle(START)
    # Add cervix + notes + disturbed flags to exercise every column.
    original[5] = DailyObservation(
        observation_date=START + dt.timedelta(days=5),
        waking_temperature=97.61,
        temperature_unit=TemperatureUnit.FAHRENHEIT,
        temperature_time=dt.time(6, 15),
        temperature_disturbed=True,
        fluid=peak(),
        cervical_position=None,
        bleeding=BleedingLevel.SPOTTING,
        notes="slept badly",
    )
    for observation in original:
        store.upsert_observation(observation)

    loaded = store.load_observations()
    assert [item.as_dict() for item in loaded] == [
        item.as_dict() for item in sorted(original, key=lambda o: o.observation_date)
    ]


def test_upsert_replaces_same_date(store) -> None:
    first = DailyObservation(observation_date=START, waking_temperature=36.4)
    replaced = store.upsert_observation(first)
    assert not replaced

    second = DailyObservation(observation_date=START, waking_temperature=36.9)
    assert store.upsert_observation(second)

    loaded = store.load_observations()
    assert len(loaded) == 1
    assert loaded[0].waking_temperature == 36.9


def test_delete_observation(store) -> None:
    store.upsert_observation(DailyObservation(observation_date=START, waking_temperature=36.4))
    assert store.delete_observation(START)
    assert not store.delete_observation(START)
    assert store.load_observations() == []


def test_settings_round_trip(store) -> None:
    settings = AppSettings(
        temperature_unit=TemperatureUnit.FAHRENHEIT,
        default_wake_time="05:45",
        track_cervical_position=True,
        rule_context=RuleContext.POST_HORMONAL,
        transition_cycle_count=3,
        use_doering_rule=True,
        use_rotzer_rule=True,
        bip_enabled=True,
    )
    store.save_settings(settings)
    assert store.load_settings().as_dict() == settings.as_dict()


def test_import_merge_upserts_and_counts_replacements(store) -> None:
    store.upsert_observation(DailyObservation(observation_date=START, waking_temperature=36.2))

    payload = _workbook_bytes(
        [
            [START.isoformat(), 36.5, "celsius"],
            [(START + dt.timedelta(days=1)).isoformat(), 36.45, "celsius"],
        ],
        ["date", "temperature", "temperature_unit"],
    )
    result = store.import_workbook(payload, mode="merge")

    assert result.ok
    assert result.imported == 2
    assert result.replaced == 1
    loaded = store.load_observations()
    assert len(loaded) == 2
    assert loaded[0].waking_temperature == 36.5


def test_import_replace_discards_existing_data(store) -> None:
    store.upsert_observation(DailyObservation(observation_date=START, waking_temperature=36.2))

    payload = _workbook_bytes(
        [[(START + dt.timedelta(days=40)).isoformat(), 36.6, "celsius"]],
        ["date", "temperature", "temperature_unit"],
    )
    result = store.import_workbook(payload, mode="replace")

    assert result.imported == 1
    loaded = store.load_observations()
    assert len(loaded) == 1
    assert loaded[0].observation_date == START + dt.timedelta(days=40)


def test_import_accepts_friendly_headers_and_excel_native_cells(store) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "My Chart"  # not the canonical sheet name
    sheet.append(["Day", "Temp", "Unit", "Time", "Sensation", "Peak", "Bleeding", "Note"])
    # Native datetime/time/bool cells, mixed-case enum text with spaces.
    sheet.append(
        [dt.datetime(2026, 3, 1, 0, 0), 97.7, "Fahrenheit", dt.time(6, 30), "Watery", True, "Medium", "hello"]
    )
    buffer = io.BytesIO()
    workbook.save(buffer)

    result = store.import_workbook(buffer.getvalue(), mode="replace")
    assert result.ok, result.errors

    loaded = store.load_observations()
    assert len(loaded) == 1
    item = loaded[0]
    assert item.observation_date == dt.date(2026, 3, 1)
    assert item.waking_temperature == 97.7
    assert item.temperature_unit == TemperatureUnit.FAHRENHEIT
    assert item.temperature_time == dt.time(6, 30)
    assert item.fluid is not None
    assert item.fluid.sensation == FluidSensation.WATERY
    assert item.fluid.peak_quality
    assert item.bleeding == BleedingLevel.MEDIUM
    assert item.notes == "hello"


def test_import_reports_row_errors_and_keeps_valid_rows(store) -> None:
    payload = _workbook_bytes(
        [
            ["2026-03-01", 36.5, "celsius"],
            ["2026-03-02", "not-a-number", "celsius"],
            ["2026-03-02", 36.4, "celsius"],
            ["2026-03-02", 36.4, "celsius"],  # duplicate date
            ["03/04/2026", 36.4, "celsius"],  # bad date format
            ["2026-03-05", 99.0, "celsius"],  # implausible Celsius temp
        ],
        ["date", "temperature", "temperature_unit"],
    )
    result = store.import_workbook(payload, mode="replace")

    assert not result.ok
    assert result.imported == 2
    error_rows = {error.row for error in result.errors}
    assert error_rows == {3, 5, 6, 7}
    assert len(store.load_observations()) == 2


def test_import_rejects_non_excel_payload(store) -> None:
    with pytest.raises(ExcelStoreError):
        store.import_workbook(b"this is not a workbook")


def test_import_requires_date_column(store) -> None:
    payload = _workbook_bytes([[36.5]], ["temperature"])
    with pytest.raises(ExcelStoreError, match="date"):
        store.import_workbook(payload)


def test_import_applies_settings_sheet(store) -> None:
    workbook = build_workbook(
        [],
        AppSettings(temperature_unit=TemperatureUnit.FAHRENHEIT, bip_enabled=True),
    )
    buffer = io.BytesIO()
    workbook.save(buffer)

    result = store.import_workbook(buffer.getvalue())
    assert result.settings_imported
    loaded = store.load_settings()
    assert loaded.temperature_unit == TemperatureUnit.FAHRENHEIT
    assert loaded.bip_enabled


def test_import_partial_cervix_row_is_an_error(store) -> None:
    payload = _workbook_bytes(
        [["2026-03-01", "high", "soft"]],
        ["date", "cervix_height", "cervix_firmness"],
    )
    result = store.import_workbook(payload)
    assert not result.ok
    assert "opening" in result.errors[0].message


def test_cervix_round_trip(store) -> None:
    from symptothermal_nfp.models import CervicalPositionObservation

    store.upsert_observation(
        DailyObservation(
            observation_date=START,
            cervical_position=CervicalPositionObservation(
                height=CervixHeight.HIGH,
                firmness=CervixFirmness.SOFT,
                opening=CervixOpening.OPEN,
            ),
        )
    )
    loaded = store.load_observations()[0]
    assert loaded.cervical_position is not None
    assert loaded.cervical_position.height == CervixHeight.HIGH
    assert loaded.cervical_position.firmness == CervixFirmness.SOFT
    assert loaded.cervical_position.opening == CervixOpening.OPEN


def test_export_bytes_is_a_valid_workbook(store) -> None:
    store.upsert_observation(DailyObservation(observation_date=START, waking_temperature=36.4))
    workbook = load_workbook(io.BytesIO(store.export_bytes()))
    sheet = workbook[OBSERVATIONS_SHEET]
    header = [cell.value for cell in sheet[1]]
    assert header[0] == "date"
    assert sheet.max_row == 2


def test_read_observations_sorts_by_date() -> None:
    payload = _workbook_bytes(
        [
            ["2026-03-03", 36.5, "celsius"],
            ["2026-03-01", 36.4, "celsius"],
        ],
        ["date", "temperature", "temperature_unit"],
    )
    observations, errors = read_observations(load_workbook(io.BytesIO(payload)))
    assert not errors
    assert [item.observation_date.day for item in observations] == [1, 3]


def test_invalid_import_mode_raises(store) -> None:
    with pytest.raises(ValueError, match="merge"):
        store.import_workbook(b"irrelevant", mode="overwrite")
