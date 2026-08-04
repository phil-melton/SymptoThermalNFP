# SymptoThermalNFP

Python-first domain, local persistence, and conservative symptothermal
interpretation are now in place.

An offline Expo/React Native client is also available in `apps/mobile`. It
provides onboarding, quick morning/evening charting, plain-language fertility
feedback, confirmation progress, cycle charts, history, and on-device SQLite
persistence.

## What Is Implemented In This Stage

1. Domain models for daily observations and settings.
2. Symptom taxonomy enums for temperature, fluid, bleeding, and cervical signs.
3. Local SQLite persistence with migration tracking.
4. Conservative STM interpretation with BBT 3-over-6, Peak Day, Phase 1,
   BIP, transition-context warnings, and luteal-phase warnings.
5. CLI commands for fast daily logging, history review, settings, and
   interpretation.
6. JSON interpretation output for future browser/mobile wiring.
7. Automated tests for domain, storage, CLI, and interpretation behavior.
8. Mobile-first Today, Chart, and History workflows.

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
warnings, rule traces, user-facing feedback, and structured confirmation
progress. Results are calculated on demand and are not persisted.

## Mobile Quick Start

```bash
cd apps/mobile
pnpm install
pnpm start
```

The mobile client stores observations locally in SQLite. See
`apps/mobile/README.md` for implemented workflows and safety scope.
