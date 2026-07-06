# SymptoThermalNFP

Python-first domain, a browser UI with Excel-backed persistence, and
conservative symptothermal interpretation are now in place.

> **⚠️ Disclaimer**
>
> This project is predominantly AI-generated code. The symptothermal rule
> implementation has **not** been verified by an independent qualified
> professional — it has only been reviewed by someone who took a class on
> natural family planning. It is not medical advice and must not be relied on
> as your sole method of avoiding or achieving pregnancy. Consult a certified
> NFP/FABM instructor or a healthcare provider before acting on anything this
> software tells you.

## What Is Implemented

1. Domain models for daily observations and settings.
2. Symptom taxonomy enums for temperature, fluid, bleeding, and cervical signs.
3. Conservative STM interpretation with BBT 3-over-6, Peak Day, Phase 1,
   BIP, transition-context warnings, and luteal-phase warnings.
4. A Flask web UI: interactive BBT cycle chart with daily fertility status
   bands, daily logging form, settings, and observation history.
5. Excel (.xlsx) as the tracking data store, with workbook upload (merge or
   replace), download, and a blank template — plus SQLite persistence and a
   CLI from earlier stages.
6. JSON interpretation output at `/api/interpretation` and `/api/observations`.
7. Automated tests for domain, storage, Excel import/export, the web app, and
   day-by-day fertile-window determination scenarios.

## Web UI Quick Start

```bash
pip install -e .[dev]
symptothermal-web            # opens on http://127.0.0.1:5000
```

All data is tracked in an Excel workbook (`data/symptothermal.xlsx` by
default; override with `SYMPTOTHERMAL_XLSX=/path/to/file.xlsx`). The file has
an `Observations` sheet (one row per day) and a `Settings` sheet, so it can be
edited directly in Excel and re-uploaded through the UI. `SYMPTOTHERMAL_HOST`
and `SYMPTOTHERMAL_PORT` configure the bind address.

Saves are crash-safe: each write goes to a temp file that atomically replaces
the workbook, and the previous version is kept alongside it as
`<name>.xlsx.bak` — if an import or edit goes wrong, rename the `.bak` file
back to recover. All POST forms are CSRF-protected; the session secret is
random per process by default, or set `SYMPTOTHERMAL_SECRET` for a stable one.

From the browser you can:

- log daily temperature, mucus, bleeding, cervix, and notes;
- see the cycle chart with coverline, Peak Day, and per-day fertility bands;
- upload an .xlsx workbook (merge or replace) — invalid rows are reported and
  skipped, valid rows import; friendly header aliases like `Day`, `Temp`,
  `Sensation` are accepted;
- download the current data file or a blank template.

## Repository Shape

```text
apps/
  mobile/
docs/
  project-plan.md
  agent-reports/
packages/
  domain/
    symptothermal_nfp/
tests/
```

## Quick Start

1. Create a Python environment.
2. Install development dependencies:

   ```bash
   pip install -e .[dev]
   ```

3. Initialize local data store:

   ```bash
   symptothermal init-db
   ```

4. Set baseline settings:

   ```bash
   symptothermal set-settings --temperature-unit celsius --wake-time 06:30 --track-cervical-position
   ```

   Optional rule context flags include `--rule-context post_hormonal`,
   `--transition-cycle-count 2`, `--use-doering-rule`,
   `--use-rotzer-rule`, and `--enable-bip`.

5. Log a daily observation:

   ```bash
   symptothermal log-observation --date 2026-04-06 --temperature 36.45 --temperature-time 06:22 --fluid-sensation watery --fluid-quantity high --fluid-color clear --fluid-texture stretchy --fluid-amount 5 --bleeding none --notes "Felt well-rested"
   ```

6. View observations, cycle history, and interpretation:

   ```bash
   symptothermal list-observations
   symptothermal list-cycles
   symptothermal interpret
   symptothermal interpret --json
   ```

## Interpretation Contract

The reusable Python API is:

```python
from symptothermal_nfp import AppSettings, evaluate_observations

report = evaluate_observations(observations, AppSettings())
payload = report.as_dict()
```

`symptothermal interpret --json` emits the same stable payload with
`rule_pack_version`, cycle-level confirmations, daily fertility statuses,
warnings, and rule traces. Results are calculated on demand and are not
persisted.
