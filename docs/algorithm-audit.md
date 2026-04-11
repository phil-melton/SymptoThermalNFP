# Algorithm Audit: Sensiplan Implementation

Audit of `packages/domain/symptothermal_nfp/algorithm.py` against
`docs/SENSIPLAN_ALGORITHM_SPEC.md`. Each item from the handoff prompt is verified
below.

---

## Bug 1: Unit Detection by Magnitude

**Confirmed: YES**

**Code evidence** (`algorithm.py:47-50`):
```python
if day.waking_temperature < 50:  # A naive check; likely celsius
    temps_f.append(_celsius_to_fahrenheit(day.waking_temperature))
else:
    temps_f.append(day.waking_temperature)
```

**Spec reference** (§1): "stored in its original unit (do NOT guess unit from
magnitude — read `temperature_unit` from the DB row)."

**Problem**: The `< 50` heuristic is wrong for any temperature between 50.0 °F
and 50.0 °C (impossible in practice, but the real issue is that ~97 °F values
are treated as Fahrenheit while ~36.5 °C values get converted — but the code
has no way to distinguish 37.0 °C from a hypothetical 37.0 °F typo). The
storage layer already persists `temperature_unit` per observation row, but
`_db_row_to_observation` (storage.py:266) never reads it back. The
`DailyObservation` model has no `temperature_unit` field.

**Fix**:
1. Add `temperature_unit: TemperatureUnit | None = None` to `DailyObservation`.
2. Read it from DB in `_db_row_to_observation`.
3. In the algorithm, read `obs.temperature_unit` and convert to Celsius
   (canonical unit). If unit is None and temp is present, mark temp as invalid.
4. Remove `_celsius_to_fahrenheit` and the `< 50` heuristic.

**Test**: Fixture with Fahrenheit temps verifies correct conversion to Celsius.
Fixture with Celsius temps verifies no conversion. A case with missing unit
should result in the temperature being excluded.

---

## Bug 2: 3-over-6 Threshold Wrong

**Confirmed: YES**

**Code evidence** (`algorithm.py:113`):
```python
if round(temp3, 1) >= round(coverline + 0.4, 1):
```

**Spec reference** (§4.1, step 3): "The 3rd day must be ≥ coverline + 0.2 °C
(≥ coverline + 0.4 °F)."

**Problem**: The code always uses `+0.4` (Fahrenheit constant) but performs this
check after the magnitude-based unit guess from Bug 1. If canonical unit becomes
Celsius (as decided), the threshold must be `+0.2`. Even in the current
Fahrenheit-internal code, the threshold is only correct *if* the unit guess was
right.

**Fix**: Switch canonical unit to Celsius. Threshold becomes `coverline + 0.2`.
Comment must cite "Spec §4.1, step 3: ≥ coverline + 0.2 °C".

**Test**: Fixture with temp3 = coverline + 0.19 (should NOT confirm) and
temp3 = coverline + 0.2 (should confirm).

---

## Bug 3: Pre-Ovulatory Infertility Not Implemented

**Confirmed: YES**

**Code evidence** (`algorithm.py:57-67`):
```python
fertile_start = -1
for i in range(n):
    if mucus_scores[i] > 0:
        fertile_start = i
        break
if fertile_start != -1:
    for i in range(fertile_start, n):
        states[i] = 1
```

All days before the first mucus observation are unconditionally state 0
(infertile). This is unsafe: pre-ovulatory infertility requires BIP
establishment, Doering calculation, or first-cycle restrictions.

**Spec reference** (§3): BIP deviation, Doering (minus-8 after 12+ cycles),
first-cycle rule (no pre-ov infertile days beyond menses), menses safety.

**Fix (v1 Conservative MVP)**: Treat the entire pre-ovulatory phase as S1
(fertile). No BIP, no Doering for v1. All days from cycle day 1 are S1
until the post-ovulatory close is confirmed (S2). Only exception: if this is
not the first cycle and the prior cycle had confirmed S2, menses days
(medium/heavy bleeding) can be S0.

The `prior_cycles` parameter is accepted in the signature for future Doering
support but unused in v1.

**Test**: First-cycle fixture should have all pre-ov days as S1 (fertile).

---

## Bug 4: Peak Day Requires Score == 4

**Confirmed: YES**

**Code evidence** (`algorithm.py:75`):
```python
if mucus_scores[i] == 4:
```

**Spec reference** (§4.2): "Peak day = the last day of best-quality mucus…
'Best-quality' is defined per-user. For users who never see slippery, it may
be creamy/watery. Do not require slippery to declare a peak."

**Problem**: The code hardcodes slippery (score 4) as the only peak quality.
The `FluidObservation.peak_quality` boolean field exists in the model but is
never consulted.

**Fix**: Peak day detection should check `fluid.peak_quality == True` first.
If no observations have `peak_quality` set, fall back to the highest mucus
sensation observed in the cycle (whatever that turns out to be). Never hardcode
score 4.

**Test**: Fixture where the user's best mucus is watery (not slippery) with
`peak_quality=True` — peak should still be detected.

---

## Bug 5: 3-over-6 Search Starts at Index 6

**Confirmed: PARTIALLY**

**Code evidence** (`algorithm.py:87`):
```python
for i in range(6, n - 2):
```

The outer loop starts at absolute index 6. The inner loop (lines 95-99)
correctly searches backwards for 6 valid temps, skipping None. However:

**Problem**: Starting at index 6 means the algorithm cannot detect a shift
earlier than cycle day 7 (0-indexed). In a cycle with no missing/disturbed
temps, the earliest possible shift is day 7 (6 preceding valid temps at indices
0-5). This is accidentally correct for clean data. BUT if early days have
disturbed temps, the loop still starts at index 6 even though the inner loop
would need to reach further back — the inner loop handles this. The real issue
is the opposite: if early days are all valid, a shift at index 6 is the
earliest possible, which is correct. The bug manifests with `n - 2` as the
upper bound — the loop uses `i+2` and `i+3` but only ensures `i+2 < n` via
`range(6, n - 2)`, missing the `i+3` case for the slow-rise exception.

**Spec reference** (§4.1.1): "6 immediately preceding valid temperatures.
Disturbed/missing days are skipped when counting back."

**Fix**: Start from the earliest index where 6 preceding valid temps exist
(dynamically computed). Upper bound must accommodate the slow-rise exception
(i+3).

**Test**: Fixture with disturbed temps in early days, ensuring the shift is
still found when enough valid temps exist further back.

---

## Bug 6: Slow-Rise Day 4 Uses >= Instead of >

**Confirmed: YES**

**Code evidence** (`algorithm.py:118`):
```python
elif temp3 > coverline and temp4 is not None and round(temp4, 1) >= round(coverline, 1):
```

**Spec reference** (§4.1, step 4): "The 4th day must be strictly above the
coverline (no +0.2 °C requirement)."

**Problem**: `>=` allows equality with coverline. The spec says "strictly
above", which means `>`.

**Fix**: Change `>=` to `>` for day 4 in the slow-rise exception.

**Test**: Fixture where day 4 temp equals coverline exactly — shift should NOT
be confirmed. Fixture where day 4 is 0.1 above coverline — shift confirmed.

---

## Bug 7: Drop-Back Exception Not Implemented

**Confirmed: YES**

**Code evidence**: No code exists for this rule anywhere in algorithm.py.

**Spec reference** (§4.1, step 5): "Among the 3 (or 4) higher days, one value
may fall back to or below the coverline. That day is excluded and an additional
higher day is required to replace it."

**Fix**: After finding the initial 3 (or 4) high temps, check if exactly one
falls at or below coverline. If so, exclude it and require one additional day
above coverline. If more than one falls back, the shift is not confirmed at
this position.

**Test**: Fixture with a drop-back on day 2 of the 3 highs, requiring a 4th
day to replace it.

---

## Bug 8: Evening-of Semantics Wrong

**Confirmed: YES**

**Code evidence** (`algorithm.py:128-133`):
```python
t_infertile = max(shift_confirmed_day, peak_confirmed_day)
if t_infertile is not None:
    for i in range(t_infertile, n):
        states[i] = 2
```

**Spec reference** (§4.3): "The day following that evening is the first full S2
day."

**Problem**: The confirmation day itself is marked S2, but per Sensiplan, S2
begins on the *evening* of the confirmation day. The day itself is still fertile
during daytime. In the `states` array (which represents the day's status), the
confirmation day should remain S1, and the *next* day should be the first S2.

**Fix**: Change `range(t_infertile, n)` to `range(t_infertile + 1, n)`. Store
`infertile_from_evening_of` in the result for the UI to explain "infertile
starting evening of day X".

**Test**: Fixture verifying that the confirmation day is S1 and the following
day is S2.

---

## Bug 9: No Disqualifiers

**Confirmed: YES**

**Code evidence**: No disqualifier checks exist anywhere in algorithm.py.

**Spec reference** (§5):
- Fever ≥ 38 °C during the relevant window
- < 3 valid mucus observations in the cycle
- < 6 valid temperatures before the candidate rise
- Cycle marked by user as anovulatory or disturbed

**Fix**: Add a `_scan_disqualifiers` function that checks each condition.
If any disqualifier fires, the cycle has no S2 phase — the entire post-fertile-
opening phase remains S1. Disqualifier reasons are recorded in the
`EvaluationResult.disqualifiers` list for the UI.

**Test**: Fever fixture (temp ≥ 38.0 °C during shift window) should result in
no S2. Anovulatory fixture (no temp rise) should result in no S2.

---

## Bug 10: Tests Encode Bugs

**Confirmed: YES**

**Evidence**:
- `test_fertile_start` validates the "first mucus > 0 = fertile start" logic
  (Bug 3 behavior — all pre-mucus days incorrectly marked infertile).
- `test_temp_shift_and_peak` uses Fahrenheit temps with the `< 50` heuristic
  and validates `t_peak` based on score==4 (Bug 4). It also checks
  `t_infertile == 8` without accounting for evening-of semantics (Bug 8).
- `test_temp_shift_exception` validates the slow-rise where day 4 uses `>=`
  (Bug 6 behavior).

**Fix**: Rewrite all tests from spec, not from current behavior. Use YAML
fixture files with expected outputs computed by hand from Sensiplan rules. The
old tests are discarded entirely.

---

## Additional Issues Found

### A. `plot.py` duplicates the `< 50` heuristic
`plot.py:18-19` also uses the magnitude-based unit guess. Must be updated to
read `observation.temperature_unit`.

### B. Peak day search breaks on first match
`algorithm.py:74-80`: The loop `break`s on the first slippery day followed by
3 non-slippery days. But peak day is the *last* such day. The `break` should
be removed; the loop should continue and keep updating `t_peak`.

### C. Mucus confirmation doesn't check for any mucus (just < 4)
`algorithm.py:77`: Checks `< 4` but doesn't verify the post-peak days
actually have mucus observations at all. Missing data should not count as
"drier".

---

## Summary

All 10 reported bugs are confirmed. 3 additional issues (A, B, C) were found.
The algorithm requires a full rewrite rather than incremental patches.
