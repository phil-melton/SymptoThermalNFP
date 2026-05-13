# Agent Report - 2026-05-13 Temperature Confirmation Accuracy

## Request

Validate the 3-high-over-6-low temperature confirmation, fix any bugs, and report
what was accomplished. Accuracy was treated as the priority.

## Rule Baseline Checked

- Checked the project plan, which calls for a conservative 3-high-over-6-low
  style temperature confirmation and a double-check with mucus confirmation.
- Cross-checked the temperature rule against a Sensiplan-related clinical paper:
  temperature rise is recognized by three readings higher than the previous six,
  with the last reading 0.2 C higher than the previous six.
  Source: https://www.sensiplan.nl/wp-content/uploads/2025/02/Natural-conception-rates-in-subfertile-couples-following-fertility-awareness-training.pdf
- Cross-checked BBT measurement quality guidance against Cleveland Clinic:
  BBT is taken immediately after waking, before standing, and measurement timing
  matters.
  Source: https://my.clevelandclinic.org/health/articles/21065-basal-body-temperature
- Cross-checked disturbance handling against NCBI Bookshelf/StatPearls, which
  notes that fever, stress, alcohol, medication changes, and inconsistent
  measurement can affect BBT reliability.
  Source: https://www.ncbi.nlm.nih.gov/books/NBK546686/

## Implementation Reviewed

Reviewed `packages/domain/symptothermal_nfp/interpretation.py`, especially:

- `_find_temperature_shift`
- `_scan_temperature_shift`
- `_temperature_celsius`
- interaction with Peak Day, unclear mucus handling, disturbed temperatures, and
  Fahrenheit normalization

The scanner already had the right conservative shape:

- requires six preceding low readings
- requires three consecutive high readings
- uses the highest of the six lows as the coverline
- requires all three highs to be strictly above the coverline
- requires the third high to meet the 0.2 C threshold unless a fourth-day
  exception is used
- excludes disturbed temperature readings from confirmation
- requires consecutive calendar days for the baseline and high sequence
- normalizes Fahrenheit readings to Celsius before comparison

## Bug Fixed

Fixed a floating-point boundary bug in the third-high threshold check.

Example failing case before the fix:

- coverline: 36.46 C
- required third high: 36.66 C
- mathematically valid difference: 0.20 C
- Python float expression `36.46 + 0.2` can evaluate as
  `36.660000000000004`, causing an exact valid threshold to be rejected.

Change made:

- Added `_TEMP_COMPARISON_EPSILON_C = 1e-9`.
- Added `_meets_temperature_threshold(value, coverline)`.
- Used that helper only for the 0.2 C threshold comparison.
- Left the strict coverline rule unchanged, so a reading equal to the coverline
  still does not count as a high temperature.

## Tests Added

Added targeted tests in `tests/test_interpretation.py`:

- exact third-high Celsius threshold confirms without requiring a fourth day
- third high below threshold with no fourth day does not confirm
- reading equal to the coverline is not counted as high
- missing calendar day prevents temperature confirmation
- disturbed baseline temperature blocks temperature confirmation

Existing relevant coverage already included:

- standard double-check confirmation
- fourth-day temperature exception
- disturbed high temperature blocks confirmation
- Fahrenheit temperatures normalize before shift detection
- premature pre-Peak temperature rise is ignored until after Peak Day
- JSON interpretation contract

## Verification

Initial full-suite run failed because pytest could not access the default temp
directory under the user profile:

```text
PermissionError: [WinError 5] Access is denied:
C:\Users\pmelto1\AppData\Local\Temp\pytest-of-pmelto1
```

Reran with a workspace-local temp base:

```powershell
.\.venv\Scripts\python.exe -m pytest --basetemp .test-tmp\codex-pytest -p no:cacheprovider
```

Final result:

```text
26 passed in 0.27s
```

## Files Changed

- `packages/domain/symptothermal_nfp/interpretation.py`
- `tests/test_interpretation.py`
- `docs/agent-reports/session-2026-05-13-temperature-confirmation.md`

## Residual Notes

- This confirms the implemented rule engine behavior for the current `stm-v1`
  rule pack; it does not certify the app as medical advice or as a substitute
  for training in a specific fertility awareness method.
- The repository had preexisting uncommitted and untracked work before this
  session. I did not revert or normalize unrelated files.
