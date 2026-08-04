# Desktop Web Interface Report — 2026-08-04

## Outcome

The primary product surface was changed from an Expo mobile app to a
computer-first local web interface.

## Delivered

1. `symptothermal web` starts a local-only server at `127.0.0.1:8765`.
2. Desktop navigation for Today, Chart, and History.
3. Wide daily-entry workflow with separate morning and evening saves.
4. Date selection for entering or reviewing past observations.
5. Sticky fertility feedback with temperature and mucus confirmation progress.
6. Full-width temperature, mucus, bleeding, and fertility-status chart.
7. Cycle history table with direct chart navigation.
8. Local chart setup for goal, units, wake time, and special cycle context.
9. Direct reuse of the canonical Python `stm-v1` engine and SQLite storage.
10. Local security headers, no CORS, and a required desktop-client header for writes.

## Verification

- JavaScript syntax check passed.
- Python suite: 46 tests passed.
- Browser QA passed at a 1280 x 720 desktop viewport: first-run setup,
  temperature and symptom entry, instant interpretation, chart, and history.
- No page-level horizontal overflow or browser console warnings/errors were found.
- Desktop HTTP, bootstrap, settings, observation persistence, security-header,
  and write-protection tests passed.

## Product Position

The Expo source remains available as an optional prototype. New user-facing
work should target the desktop web interface unless product direction changes.
