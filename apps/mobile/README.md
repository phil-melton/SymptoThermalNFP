# Mobile App

Offline Expo/React Native charting client for the `stm-v1` symptothermal rule pack.

## Implemented UX

- Three-tab navigation: Today, Chart, and History.
- One-time onboarding for goal, temperature unit, wake time, and cycle context.
- Separate morning temperature and evening symptom saves.
- Explicit distinction between `Not checked` and `Dry` cervical mucus.
- Disturbance flags for illness, sleep, measurement time, alcohol, travel, and measurement issues.
- Plain-language feedback: `Fertility possible`, `Post-ovulation phase confirmed`,
  `Lower probability — method rules apply`, and `Not enough information`.
- Structured temperature and mucus confirmation progress with a next logging step.
- On-device SQLite persistence. No account, backend, analytics, or cloud sync.
- Accessible chart legend that does not rely on color alone.

## Run

```bash
cd apps/mobile
pnpm install
pnpm start
```

Use Expo Go or an Android/iOS development build. Static verification:

```bash
pnpm run typecheck
pnpm exec expo export --platform android
```

## Interpretation Architecture

`src/domain.ts` is the mobile TypeScript port of the conservative Python
`stm-v1` behavior. The canonical Python implementation remains in
`packages/domain/symptothermal_nfp/interpretation.py`. Charting in the Python
CLI now consumes that same canonical implementation instead of the retired
prototype evaluator in `algorithm.py`.

Cross-language fixtures should be expanded whenever rule behavior changes so
the Python and TypeScript implementations cannot drift.

## Safety Scope

This app is an educational charting aid. It is not medical advice, a diagnosis,
contraception, or a guarantee against pregnancy. Users avoiding pregnancy or
charting during postpartum, breastfeeding, recent hormonal transition,
post-miscarriage, or perimenopause contexts should learn their chosen method
from a qualified instructor.
