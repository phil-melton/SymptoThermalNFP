# Algorithm Validation Report

## Summary

The Sensiplan symptothermal algorithm (`algorithm.py`) has been audited and
rewritten to correctly implement the double-check method as specified in
`docs/SENSIPLAN_ALGORITHM_SPEC.md`. All 10 reported bugs and 3 additional
issues were confirmed and fixed. The test suite was rebuilt from scratch using
YAML fixture files derived from the spec, not from prior (buggy) behavior.

**Test results: 107 passed, 0 failed.**

---

## Spec Coverage

| Spec Section | Coverage | Notes |
|-------------|----------|-------|
| §1 Daily inputs | Full | temperature_unit read from storage per observation |
| §2 State machine | Full | S0→S1→S2 transitions; FertilityState enum |
| §3 Opening fertile window | Partial (v1 MVP) | All pre-ov days are S1 (conservative). BIP/Doering deferred. `prior_cycles` parameter accepted for future use. |
| §4.1 Temperature rule | Full | 3-over-6 with +0.2°C threshold, all in Celsius |
| §4.1 Exception 1 (slow rise) | Full | Day 4 strictly > coverline; 4 post-peak dry days |
| §4.1 Exception 2 (drop-back) | Full | One fallback allowed, replaced by next high |
| §4.1 Disturbed temps | Full | Skipped in 6-low count and high sequence |
| §4.2 Peak day | Full | Per-user best quality via peak_quality flag or highest sensation |
| §4.3 Double-check | Full | Both rules required; evening-of semantics correct |
| §5 Disqualifiers | Partial | Fever ≥38°C and <3 mucus obs implemented. Anovulatory/postpartum/perimenopause deferred. |
| §6 Exclusions | Full | No prediction, smoothing, ML, or cervix-averaging added |

---

## What Each Fixture Proves

| Fixture | Spec Rules Exercised | Key Assertions |
|---------|---------------------|----------------|
| `textbook_sharp_rise.yaml` | §4.1 (3-over-6), §4.2 (peak), §4.3 (double-check) | Standard shift + peak confirm same day. S2 starts next day. All pre-ov S1. |
| `slow_rise.yaml` | §4.1 step 4 (Exception 1), §4.2 step 3 (4 dry days) | Day 3 < +0.2°C, day 4 strictly above. Peak needs 4 post-peak dry days. |
| `drop_back.yaml` | §4.1 step 5 (Exception 2) | One high falls to coverline, excluded. Replacement 4th day confirms. |
| `disturbed_temps.yaml` | §4.1.1 (valid temp counting), §4.1 step 6 | 2 disturbed days skipped in 6-low search. Shift still found. |
| `early_mucus_late_temp.yaml` | §4.3 (double-check timing) | Peak confirms day 12 but temp not until day 17. S2 waits for later rule. |
| `anovulatory.yaml` | §4.3 (no S2 without both rules) | No temp shift detected. Peak confirmed but entire cycle stays S1. |
| `fever.yaml` | §5 (fever disqualifier) | Fever ≥38.0°C on day 12. Cycle disqualified, no S2 possible. |
| `first_cycle.yaml` | §3 (first-cycle rule) | No prior cycles. All pre-ov days S1 including menses. |
| `fahrenheit_conversion.yaml` | §1 (unit handling) | Fahrenheit inputs correctly converted to Celsius. +0.2°C threshold applied. |

---

## Known Gaps

1. **Pre-ovulatory infertility (§3)**: BIP deviation, Doering rule (minus-8),
   and menses safety are not implemented in v1. All pre-ov days are
   conservatively marked S1. The `prior_cycles` parameter is accepted in the
   API signature but unused.

2. **Cervix as mucus substitute (§1, §6)**: The spec allows cervical position
   to replace mucus as the second sign. This is not implemented. Cervical data
   is stored but ignored by the algorithm.

3. **Postpartum/perimenopause/post-HBC (§5)**: Special rule packs for these
   conditions are out of scope for v1.

4. **User-marked anovulatory (§5)**: The `DailyObservation` model does not have
   a cycle-level "anovulatory" flag. This disqualifier cannot fire until that
   field is added.

5. **< 6 valid temps before rise (§5)**: This is enforced implicitly (the
   algorithm simply won't find a shift), but no explicit disqualifier message
   is generated unless the cycle ends without a shift.

---

## Judgment Calls

1. **Mucus "drier" definition for post-peak confirmation**: The spec says
   "clearly drier pattern than peak." We interpret this as: any day whose mucus
   quality is below the cycle's best quality counts as drier. If no mucus is
   observed on a post-peak day, it is NOT counted as drier (conservative —
   missing data ≠ dry).

2. **Fever detection without user marking**: The spec lists fever as a
   disqualifier. We auto-detect temps ≥ 38.0°C even if the user didn't mark
   the day as disturbed. This is more conservative than relying solely on user
   flagging.

3. **Drop-back within slow-rise**: If a slow-rise exception is needed AND a
   drop-back occurs, both are handled. The drop-back count and slow-rise count
   are tracked independently.

4. **Floating-point comparisons**: All temperature comparisons use `round(x, 2)`
   to avoid floating-point precision issues (e.g., 36.3 + 0.2 = 36.500000001).

5. **Peak day with peak_quality flag**: If the user sets `peak_quality=True` on
   any day, only days with that flag are considered peak quality. If no
   observations have the flag, the algorithm falls back to using the highest
   sensation observed in the cycle.

---

## Design Decisions

- **Canonical unit: Celsius.** Sensiplan handbook thresholds are native Celsius.
  All internal calculations use Celsius; Fahrenheit inputs are converted on
  entry. Display conversion happens in plot.py.

- **1-indexed cycle days.** All day references in `EvaluationResult` are
  1-indexed (matching how users think about cycle days). Internal 0-indexed
  arrays are converted at output boundaries.

- **Per-day rule traces.** Every day has a `DayRuleTrace` recording which rules
  fired, what inputs were used, and why the state was assigned. This is a hard
  requirement for Phase 3 (explanation UI).

- **No silent fallbacks.** If a precondition is unmet (e.g., unknown
  temperature unit), the state stays S1 and a reason is recorded.
