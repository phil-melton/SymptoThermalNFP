"""Shared observation builders for fertile-window and web/Excel tests."""

from __future__ import annotations

import datetime as dt

from symptothermal_nfp.models import DailyObservation, FluidObservation
from symptothermal_nfp.taxonomy import (
    BleedingLevel,
    FluidQuantity,
    FluidSensation,
    MucusColor,
    MucusTexture,
    TemperatureUnit,
)


def dry() -> FluidObservation:
    return FluidObservation(sensation=FluidSensation.DRY)


def sticky() -> FluidObservation:
    return FluidObservation(
        sensation=FluidSensation.STICKY,
        quantity=FluidQuantity.LOW,
        color=MucusColor.WHITE,
        texture=MucusTexture.STICKY,
    )


def watery() -> FluidObservation:
    return FluidObservation(
        sensation=FluidSensation.WATERY,
        quantity=FluidQuantity.HIGH,
        color=MucusColor.CLEAR,
        texture=MucusTexture.STRETCHY,
    )


def peak() -> FluidObservation:
    return FluidObservation(
        sensation=FluidSensation.SLIPPERY,
        quantity=FluidQuantity.HIGH,
        color=MucusColor.CLEAR,
        texture=MucusTexture.SLIPPERY,
        peak_quality=True,
    )


def observation(
    start: dt.date,
    day: int,
    *,
    temp: float | None,
    fluid: FluidObservation | None = None,
    bleeding: BleedingLevel = BleedingLevel.NONE,
    disturbed: bool = False,
    unit: TemperatureUnit | None = TemperatureUnit.CELSIUS,
) -> DailyObservation:
    """Build the observation for cycle day ``day`` (1-based) of a cycle starting at ``start``."""
    return DailyObservation(
        observation_date=start + dt.timedelta(days=day - 1),
        waking_temperature=temp,
        temperature_unit=unit if temp is not None else None,
        temperature_disturbed=disturbed,
        fluid=fluid,
        bleeding=bleeding,
    )


def textbook_cycle(
    start: dt.date,
    *,
    length: int = 28,
    unit: TemperatureUnit = TemperatureUnit.CELSIUS,
    disturbed_days: frozenset[int] | set[int] = frozenset(),
) -> list[DailyObservation]:
    """A clear ovulatory cycle.

    Day-by-day script (1-based cycle days):

    * days 1-3: medium bleeding, no mucus recorded
    * days 4-7: dry
    * days 8-10: sticky build-up
    * days 11-13: watery (peak quality)
    * day 14: slippery Peak Day
    * days 15+: dry
    * temps: 36.40 C baseline through day 14 (36.45 C on day 12),
      then 36.65 / 36.70 / 36.75 C on days 15-17 and 36.70 C after.

    Expected interpretation: Peak Day = day 14, mucus confirmation day 17,
    temperature shift first high day 15 / confirmed day 17 (coverline 36.45),
    so post-ovulatory infertility starts on the evening of day 17.
    """
    observations = []
    for day in range(1, length + 1):
        if day <= 3:
            fluid = None
            bleeding = BleedingLevel.MEDIUM
        elif day <= 7:
            fluid, bleeding = dry(), BleedingLevel.NONE
        elif day <= 10:
            fluid, bleeding = sticky(), BleedingLevel.NONE
        elif day <= 13:
            fluid, bleeding = watery(), BleedingLevel.NONE
        elif day == 14:
            fluid, bleeding = peak(), BleedingLevel.NONE
        else:
            fluid, bleeding = dry(), BleedingLevel.NONE

        if day <= 14:
            temp_c = 36.45 if day == 12 else 36.40
        elif day == 15:
            temp_c = 36.65
        elif day == 16:
            temp_c = 36.70
        elif day == 17:
            temp_c = 36.75
        else:
            temp_c = 36.70

        temp = temp_c if unit == TemperatureUnit.CELSIUS else round(temp_c * 9 / 5 + 32, 2)
        observations.append(
            observation(
                start,
                day,
                temp=temp,
                fluid=fluid,
                bleeding=bleeding,
                disturbed=day in disturbed_days,
                unit=unit,
            )
        )
    return observations


def repeated_textbook_cycles(first_start: dt.date, count: int, *, length: int = 28) -> list[DailyObservation]:
    observations: list[DailyObservation] = []
    for index in range(count):
        observations.extend(
            textbook_cycle(first_start + dt.timedelta(days=index * length), length=length)
        )
    return observations
