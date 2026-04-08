import pytest
from datetime import date
from symptothermal_nfp.models import DailyObservation, FluidObservation
from symptothermal_nfp.taxonomy import FluidSensation
from symptothermal_nfp.algorithm import evaluate_cycle

def test_fertile_start():
    # Day 1-3 Dry (State 0), Day 4 Sticky (State 1)
    days = [
        DailyObservation(observation_date=date(2023, 1, 1), fluid=FluidObservation(sensation=FluidSensation.DRY)),
        DailyObservation(observation_date=date(2023, 1, 2), fluid=FluidObservation(sensation=FluidSensation.DRY)),
        DailyObservation(observation_date=date(2023, 1, 3), fluid=FluidObservation(sensation=FluidSensation.DRY)),
        DailyObservation(observation_date=date(2023, 1, 4), fluid=FluidObservation(sensation=FluidSensation.STICKY)),
        DailyObservation(observation_date=date(2023, 1, 5), fluid=FluidObservation(sensation=FluidSensation.DRY)),
    ]
    res = evaluate_cycle(days)
    assert res.states[0] == 0
    assert res.states[1] == 0
    assert res.states[2] == 0
    assert res.states[3] == 1
    assert res.states[4] == 1

def test_temp_shift_and_peak():
    # 10 days total to give room for 6 low temps + 3 day shift + peak drop
    days = []
    temps_f = [97.0, 97.1, 97.0, 97.2, 97.1, 97.0, 97.8, 97.9, 98.1, 98.0] # Shift starts at idx 6 (day 7). Coverline is 97.2.
    mucus = [
        FluidSensation.DRY, FluidSensation.DRY, FluidSensation.STICKY, FluidSensation.WATERY,
        FluidSensation.SLIPPERY, FluidSensation.SLIPPERY, FluidSensation.CREAMY, FluidSensation.DRY, FluidSensation.DRY, FluidSensation.DRY
    ]

    for i in range(10):
        days.append(DailyObservation(
            observation_date=date(2023, 1, i+1),
            waking_temperature=temps_f[i],
            fluid=FluidObservation(sensation=mucus[i])
        ))

    res = evaluate_cycle(days)

    assert res.t_cover == 97.2
    assert res.t_shift == 6
    # temp shift confirmation should be day 6+2 = 8

    # Peak day: last day of slippery (score 4) before drop. Index 5.
    assert res.t_peak == 5
    # peak confirmation should be day 5+3 = 8

    # Infertile transition should be max(8, 8) = 8
    assert res.t_infertile == 8

    assert res.states[0] == 0
    assert res.states[1] == 0
    assert res.states[2] == 1 # Sticky
    assert res.states[8] == 2 # Infertile
    assert res.states[9] == 2 # Infertile

def test_temp_shift_exception():
    # Test Day 4 exception: Day 3 doesn't reach +0.4 but is above coverline, Day 4 is above coverline
    days = []
    temps_f = [97.0, 97.1, 97.0, 97.2, 97.1, 97.0, 97.4, 97.5, 97.4, 97.3]
    # Shift candidate idx 6 (97.4 > 97.2). Coverline 97.2.
    # idx 7: 97.5 > 97.2
    # idx 8: 97.4 >= 97.2 but not +0.4 (which would be 97.6)
    # idx 9: 97.3 >= 97.2 (Day 4 exception triggers here)
    for i in range(10):
        days.append(DailyObservation(
            observation_date=date(2023, 1, i+1),
            waking_temperature=temps_f[i],
            fluid=FluidObservation(sensation=FluidSensation.DRY) # Keep mucus out of the way for this test
        ))

    res = evaluate_cycle(days)
    assert res.t_cover == 97.2
    assert res.t_shift == 6
    # confirmation on Day 4 (idx 6 + 3 = 9)
    # since no peak, it won't transition to state 2, but we can verify shift_confirmed indirectly if we want, or add an assertion to algorithm.
    # Currently t_infertile needs both.

def test_temp_shift_exception_invalid_drop():
    # Test Day 4 exception failure: Day 3 drops to or below coverline
    days = []
    temps_f = [97.0, 97.1, 97.0, 97.2, 97.1, 97.0, 97.4, 97.5, 97.2, 97.5]
    # Shift candidate idx 6 (97.4 > 97.2). Coverline 97.2.
    # idx 7: 97.5 > 97.2
    # idx 8: 97.2 (NOT > 97.2, exception rule should fail here)
    # idx 9: 97.5 >= 97.2
    for i in range(10):
        days.append(DailyObservation(
            observation_date=date(2023, 1, i+1),
            waking_temperature=temps_f[i],
            fluid=FluidObservation(sensation=FluidSensation.DRY)
        ))

    res = evaluate_cycle(days)
    assert res.t_shift is None # Shift should not be confirmed

def test_temp_shift_floating_point():
    days = []
    # Test exact 0.4 threshold that may have floating point issues
    temps_f = [97.0, 97.1, 97.0, 97.2, 97.1, 97.0, 97.4, 97.4, 97.6, 97.6]
    # Coverline 97.2
    # idx 6: 97.4
    # idx 7: 97.4
    # idx 8: 97.6 (97.2 + 0.4 = 97.60000000000001 without rounding)
    for i in range(10):
        days.append(DailyObservation(
            observation_date=date(2023, 1, i+1),
            waking_temperature=temps_f[i],
            fluid=FluidObservation(sensation=FluidSensation.DRY)
        ))

    res = evaluate_cycle(days)
    assert res.t_shift == 6
    assert res.t_cover == 97.2
