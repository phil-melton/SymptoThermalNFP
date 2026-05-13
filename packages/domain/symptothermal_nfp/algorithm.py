from dataclasses import dataclass
from typing import List, Optional

from .models import DailyObservation
from .taxonomy import FluidSensation

@dataclass
class EvaluationResult:
    states: List[int] # 0 = Infertile Menses, 1 = Fertile, 2 = Infertile Post-Ovulation
    t_shift: Optional[int] = None # index in the cycle
    t_cover: Optional[float] = None
    t_peak: Optional[int] = None # index in the cycle
    t_infertile: Optional[int] = None # index in the cycle

def _celsius_to_fahrenheit(c: float) -> float:
    return (c * 9/5) + 32

def map_fluid_score(fluid) -> int:
    if fluid is None:
        return 0
    sensation = fluid.sensation
    if sensation == FluidSensation.DRY:
        return 0
    if sensation == FluidSensation.STICKY:
        return 1
    if sensation == FluidSensation.CREAMY:
        return 2
    if sensation == FluidSensation.WATERY:
        return 3
    if sensation == FluidSensation.SLIPPERY:
        return 4
    return 0

def evaluate_cycle(cycle_days: List[DailyObservation], default_temp_unit: str = "fahrenheit") -> EvaluationResult:
    """
    Evaluates a cycle according to the symptothermal rules.
    Returns the daily state assignments and transition dates.
    All logic done in Fahrenheit internally.
    """
    temps_f = []
    for day in cycle_days:
        if day.waking_temperature is None or day.temperature_disturbed:
            temps_f.append(None)
        else:
            # Assuming domain model currently stores whatever user entered,
            # We assume it's Fahrenheit if unit is 'fahrenheit' else Celsius.
            if day.waking_temperature < 50: # A naive check; likely celsius
                 temps_f.append(_celsius_to_fahrenheit(day.waking_temperature))
            else:
                 temps_f.append(day.waking_temperature)

    mucus_scores = [map_fluid_score(day.fluid) for day in cycle_days]

    n = len(cycle_days)
    states = [0] * n

    # Find the start of the fertile window (first day with mucus score > 0)
    fertile_start = -1
    for i in range(n):
        if mucus_scores[i] > 0:
            fertile_start = i
            break

    # State 1 starts at fertile_start
    if fertile_start != -1:
        for i in range(fertile_start, n):
            states[i] = 1

    # Find $t_{peak}$: last day of mucus score 4 before a sustained drop
    # Confirmation is valid on evening of 3rd day of score < 4
    t_peak = None
    peak_confirmed_day = None

    for i in range(n - 3):
        if mucus_scores[i] == 4:
            # check if next three days are strictly < 4
            if mucus_scores[i+1] < 4 and mucus_scores[i+2] < 4 and mucus_scores[i+3] < 4:
                t_peak = i
                peak_confirmed_day = i + 3
                break

    # Find $t_{shift}$ using 3-over-6 rule
    t_shift = None
    t_cover = None
    shift_confirmed_day = None

    for i in range(6, n - 2):
        # We need a candidate t_shift
        candidate = temps_f[i]
        if candidate is None:
             continue

        # Get 6 previous valid temperatures
        valid_prev_temps = []
        for j in range(i - 1, -1, -1):
            if temps_f[j] is not None:
                valid_prev_temps.append(temps_f[j])
            if len(valid_prev_temps) == 6:
                break

        if len(valid_prev_temps) < 6:
             continue # Cannot form 6 low temps

        coverline = max(valid_prev_temps)

        if candidate > coverline:
            temp1 = temps_f[i]
            temp2 = temps_f[i+1] if i+1 < n else None
            temp3 = temps_f[i+2] if i+2 < n else None
            temp4 = temps_f[i+3] if i+3 < n else None

            if temp2 is not None and temp3 is not None and temp1 > coverline and temp2 > coverline:
                if round(temp3, 1) >= round(coverline + 0.4, 1):
                    t_shift = i
                    t_cover = coverline
                    shift_confirmed_day = i + 2
                    break
                elif temp3 > coverline and temp4 is not None and round(temp4, 1) >= round(coverline, 1):
                     # Exception rule: wait for day 4. Day 3 must still be above coverline.
                     t_shift = i
                     t_cover = coverline
                     shift_confirmed_day = i + 3
                     break


    # Determine transition to State 2 (Infertile Post-Ovulation)
    t_infertile = None
    if shift_confirmed_day is not None and peak_confirmed_day is not None:
        t_infertile = max(shift_confirmed_day, peak_confirmed_day)

    if t_infertile is not None:
        for i in range(t_infertile, n):
            states[i] = 2

    return EvaluationResult(
        states=states,
        t_shift=t_shift,
        t_cover=t_cover,
        t_peak=t_peak,
        t_infertile=t_infertile
    )
