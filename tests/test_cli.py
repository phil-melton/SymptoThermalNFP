import datetime as dt
import json

from symptothermal_nfp.cli import main
from symptothermal_nfp.models import DailyObservation, FluidObservation
from symptothermal_nfp.storage import LocalStore
from symptothermal_nfp.taxonomy import (
    BleedingLevel,
    FluidQuantity,
    FluidSensation,
    MucusColor,
    MucusTexture,
    TemperatureUnit,
)


def test_log_observation_accepts_full_mucus_fields(tmp_path, capsys) -> None:
    db_path = tmp_path / "local.db"

    exit_code = main(
        [
            "--db",
            str(db_path),
            "log-observation",
            "--date",
            "2026-04-01",
            "--temperature",
            "36.40",
            "--fluid-sensation",
            "slippery",
            "--fluid-quantity",
            "high",
            "--fluid-color",
            "clear",
            "--fluid-texture",
            "stretchy",
            "--fluid-amount",
            "5",
            "--fluid-peak",
        ]
    )
    capsys.readouterr()

    store = LocalStore(db_path)
    observation = store.get_observation("2026-04-01")

    assert exit_code == 0
    assert observation is not None
    assert observation.fluid is not None
    assert observation.fluid.color == MucusColor.CLEAR
    assert observation.fluid.texture == MucusTexture.STRETCHY
    assert observation.fluid.amount == 5


def test_interpret_command_emits_json_contract(tmp_path, capsys) -> None:
    db_path = tmp_path / "local.db"
    store = LocalStore(db_path)
    store.initialize()
    store.upsert_observation(
        DailyObservation(
            observation_date=dt.date(2026, 4, 1),
            waking_temperature=36.4,
            fluid=FluidObservation(
                sensation=FluidSensation.DRY,
                quantity=FluidQuantity.NONE,
            ),
            bleeding=BleedingLevel.MEDIUM,
        ),
        TemperatureUnit.CELSIUS,
    )

    exit_code = main(["--db", str(db_path), "interpret", "--json"])
    output = capsys.readouterr().out

    payload = json.loads(output)
    assert exit_code == 0
    assert payload["rule_pack_version"] == "stm-v1"
    assert payload["cycles"][0]["days"][0]["status"] == "potentially_fertile"


def test_interpret_command_shows_mucus_confirmation_column(tmp_path, capsys) -> None:
    db_path = tmp_path / "local.db"
    store = LocalStore(db_path)
    store.initialize()
    for observation in _cli_stm_cycle(dt.date(2026, 4, 1)):
        store.upsert_observation(observation, TemperatureUnit.CELSIUS)

    exit_code = main(["--db", str(db_path), "interpret"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Mucus Confirmed" in output
    assert "2026-04-09" in output


def _cli_stm_cycle(start: dt.date) -> list[DailyObservation]:
    observations: list[DailyObservation] = []
    for day in range(1, 13):
        if day < 7:
            temp = 36.40 + ((day % 5) * 0.02)
        elif day < 10:
            temp = 36.75 + ((day - 7) * 0.03)
        else:
            temp = 36.80

        if day == 6:
            fluid = FluidObservation(
                sensation=FluidSensation.SLIPPERY,
                quantity=FluidQuantity.HIGH,
                color=MucusColor.CLEAR,
                texture=MucusTexture.STRETCHY,
                amount=5,
                peak_quality=True,
            )
        elif day in {7, 8, 9}:
            fluid = FluidObservation(
                sensation=FluidSensation.STICKY,
                quantity=FluidQuantity.LOW,
                color=MucusColor.CLOUDY,
                texture=MucusTexture.STICKY,
                amount=1,
            )
        else:
            fluid = FluidObservation(sensation=FluidSensation.DRY, quantity=FluidQuantity.NONE)

        observations.append(
            DailyObservation(
                observation_date=start + dt.timedelta(days=day - 1),
                waking_temperature=temp,
                fluid=fluid,
                bleeding=BleedingLevel.MEDIUM if day == 1 else BleedingLevel.NONE,
            )
        )
    return observations
