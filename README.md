# SymptoThermalNFP

A computer-first, local fertility charting tool with conservative
symptothermal interpretation. The primary interface runs in a desktop browser;
there is no mobile app, account, cloud backend, or analytics service.

> **Warning**
>
> This project is predominantly AI-generated. Its symptothermal rules have not
> been independently verified by a qualified professional. It is educational
> software, not medical advice, and should not be the sole basis for avoiding
> or achieving pregnancy. Consult a certified NFP/FABM instructor or healthcare
> provider before acting on its feedback.

## Desktop quick start

```powershell
pip install -e .[dev]
symptothermal web
```

The app opens at `http://127.0.0.1:5000/`. Use `symptothermal web --no-open`
to leave the browser closed, or `symptothermal web --data-file path/to/chart.xlsx`
to use another workbook.

All web data is stored locally in `data/symptothermal.xlsx` by default. Saves
are crash-safe: the workbook is replaced atomically and the prior version is
kept as `<name>.xlsx.bak`. POST forms are CSRF-protected.

## Desktop workflows

- Enter a date, waking temperature, time, mucus observation, bleeding, and
  optional notes from one wide daily-entry screen.
- See the latest plain-language fertility interpretation beside the entry
  workflow.
- Review an interactive temperature chart with fertility bands, coverline,
  Peak Day, bleeding, and disturbed-temperature markers.
- Edit or delete prior observations from the history table.
- Download the current workbook, import another `.xlsx` file, or download a
  blank template.
- Configure units, wake time, cycle context, and optional advanced rules.

## Implemented foundation

1. Domain models for daily observations and settings.
2. Symptom taxonomies for temperature, fluid, bleeding, and cervical signs.
3. Conservative interpretation with BBT 3-over-6, Peak Day, Phase 1, BIP,
   transition-context warnings, and luteal-phase warnings.
4. Structured feedback and temperature/mucus confirmation progress.
5. Excel persistence for the desktop web app, plus SQLite persistence and CLI
   commands for programmatic workflows.
6. JSON interpretation APIs at `/api/interpretation` and `/api/observations`.
7. Automated domain, storage, Excel, web, and fertile-window scenario tests.

## CLI workflows

```powershell
symptothermal init-db
symptothermal set-settings --temperature-unit celsius --wake-time 06:30
symptothermal log-observation --date 2026-04-06 --temperature 36.45 --temperature-time 06:22 --fluid-sensation watery --bleeding none
symptothermal list-observations
symptothermal list-cycles
symptothermal interpret --json
```

SQLite commands use `data/local.db` by default. Pass
`symptothermal --db path/to/local.db <command>` to select another database.

## Interpretation API

```python
from symptothermal_nfp import AppSettings, evaluate_observations

report = evaluate_observations(observations, AppSettings())
payload = report.as_dict()
```

The payload includes rule versioning, cycle confirmations, daily fertility
statuses, warnings, rule traces, plain-language feedback, and structured
confirmation progress. Results are calculated on demand and are not persisted.

## Repository shape

```text
docs/
packages/domain/symptothermal_nfp/
tests/
```
