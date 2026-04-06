# SymptoThermalNFP Project Plan

## Status

This document captures the current implementation plan for a local-first, privacy-first, open-source fertility awareness tracker based on the Sympto-Thermal Method. It is intended as a handoff document for future implementation work.

## Product Goal

Build a free, open-source competitor to PeakDay that supports Sympto-Thermal fertility awareness charting with a conservative, explainable interpretation engine.

The first release should run locally on the user's device with no required backend.

## Product Principles

1. Local-first before cloud-first.
2. Privacy-first before convenience features.
3. Explainable rule-based interpretation before predictive or AI features.
4. Conservative fertility interpretation when data are incomplete or ambiguous.
5. Open data portability through export and backup.

## Scientific Grounding

The product should not claim to represent every Sympto-Thermal school identically. The literature supports sympto-thermal tracking as an effective fertility awareness approach when users are trained and when rules are followed consistently, but exact operational rules vary by method.

### Evidence Base

1. Frank-Herrmann P, Heil J, Gnoth C, et al. The effectiveness of a fertility awareness based method to avoid pregnancy in relation to a couple's sexual behaviour during the fertile time: a prospective longitudinal study. Human Reproduction. 2007;22(5):1310-1319. doi:10.1093/humrep/dem003.

   Relevance: prospective cohort study of a sympto-thermal method using basal body temperature plus cervical secretion observations. Reported strong effectiveness when rules were followed and fertile-window behavior was aligned with the method.

2. Peragallo Urrutia R, Polis CB, Jensen ET, et al. Effectiveness of Fertility Awareness-Based Methods for Pregnancy Prevention: A Systematic Review. Obstetrics and Gynecology. 2018;132(3):591-604. doi:10.1097/AOG.0000000000002784.

   Relevance: systematic review showing that effectiveness varies substantially across fertility awareness methods and implementations. Product implication: the app must clearly state which rule set it implements.

3. Bigelow JL, Dunson DB, Stanford JB, Ecochard R, Gnoth C, Colombo B. Mucus observations in the fertile window: a better predictor of conception than timing of intercourse. Human Reproduction. 2004;19(4):889-892. doi:10.1093/humrep/deh173.

   Relevance: supports the importance of cervical fluid observations as a primary biomarker rather than an optional secondary input.

4. Wilcox AJ, Weinberg CR, Baird DD. Timing of sexual intercourse in relation to ovulation: effects on the probability of conception, survival of the pregnancy, and sex of the baby. New England Journal of Medicine. 1995;333(23):1517-1521. doi:10.1056/NEJM199512073332301.

   Relevance: supports the biologic basis of a fertile window and the need for conservative handling of fertile-phase boundaries.

5. Hassoun D. Natural Family Planning methods and Barrier: CNGOF Contraception Guidelines. Gynecologie Obstetrique Fertilite and Senologie. 2018;46(12):873-882. doi:10.1016/j.gofs.2018.10.002.

   Relevance: formal clinical guidance recognizing cervical mucus, basal body temperature, and sympto-thermal approaches while emphasizing correct use and user education.

6. American College of Obstetricians and Gynecologists. Fertility Awareness-Based Methods of Family Planning. FAQ024. Published 2019, last reviewed 2025.

   Relevance: practical clinical guidance for user warnings, contraindications, and educational framing.

### Interpretation Baseline for Version 1

Use a conservative, double-check sympto-thermal baseline inspired by Sensiplan-style logic.

Proposed baseline behavior:

1. Use basal body temperature and cervical fluid as primary signs.
2. Allow optional cervical position as a supporting sign, not a required signal.
3. Identify Peak Day as the last day of highest-quality fertile-type fluid or lubricative sensation.
4. Require three full days after Peak Day before mucus-based post-ovulatory confirmation contributes.
5. Use a conservative 3-high-over-6-low style temperature confirmation.
6. Start post-ovulatory infertile status only after both mucus and temperature conditions are satisfied, using the later of the two.
7. If observations are missing, disturbed, or contradictory, remain in an unconfirmed state.
8. Disable or warn on confident automation for postpartum, breastfeeding return of fertility, perimenopause, suspected anovulatory cycles, fever, major sleep disruption, or recent hormonal transition.

## Product Scope

### In Scope for the First Release

1. Daily charting for basal body temperature.
2. Daily charting for cervical fluid observations.
3. Optional cervical position tracking.
4. Bleeding tracking.
5. Daily notes.
6. Cycle history and chart review.
7. On-device interpretation engine.
8. Local export and backup.
9. Basic app lock or device-protected access if feasible.

### Out of Scope for the First Release

1. Cloud sync.
2. User accounts.
3. Browser application.
4. Partner collaboration.
5. Wearable ingestion.
6. Provider portal.
7. Diagnostic or treatment recommendations.
8. Server-side analytics.
9. Machine learning predictions.

## Technical Direction

### Recommended Stack

1. Expo + React Native + TypeScript for the app shell.
2. File-based routing via Expo Router.
3. Shared TypeScript domain layer for schemas, rule evaluation, and export models.
4. Embedded local persistence using SQLite or equivalent.
5. Zod for runtime schema validation.
6. Local chart rendering with mobile-first UX.

### Why This Stack

1. It supports local-first mobile delivery now.
2. It keeps a future browser path open through shared TypeScript domain logic.
3. It avoids committing the project to a backend too early.
4. It reduces initial privacy risk because no health data needs to leave the device.

## Privacy and Security Direction

### Version 1 Security Model

The first release should assume all health data remains on-device.

Phase 1 can begin with local persistence while the product model stabilizes.
Phase 2 should add encryption for local records and encrypted backup/export.

### Security Design Requirements

1. Keep all fertility observations and interpretation results on-device.
2. Avoid third-party analytics that may expose health data.
3. Encrypt local records once Phase 2 begins.
4. Use standard platform crypto only.
5. Support encrypted export or backup bundles for portability.
6. Treat device compromise as an explicit threat outside the protection boundary of stored-data encryption.

### Cryptography Notes

1. Use standard audited cryptographic primitives only.
2. Favor authenticated encryption such as AES-GCM through platform-supported APIs.
3. Do not build custom cryptography.
4. Do not use homomorphic encryption in the MVP.
5. If passphrase-based recovery is introduced later, require a modern password-hardening approach.

## Architecture Overview

### Local-First App Architecture

The initial application should consist of four main layers:

1. Presentation layer.
   Screens for daily logging, cycle charting, cycle review, settings, and export.

2. Domain layer.
   Types, symptom taxonomy, interpretation rules, explanation traces, and validation.

3. Persistence layer.
   Local database access, migrations, repositories, and import/export serialization.

4. Security layer.
   Local encryption, key management, and backup protection.

### Future Expansion Path

If a browser client or multi-device sync is added later:

1. Reuse the same TypeScript domain models.
2. Reuse the same encryption envelope format.
3. Add a ciphertext-only API service later, likely FastAPI with PostgreSQL.
4. Keep interpretation on the client unless there is a strong reason to move it.

## Delivery Roadmap

### Phase 1: Core Local Charting

Goal: deliver an offline, local-only charting app with stable domain models.

Deliverables:

1. Daily observation model for temperature, fluid, cervical changes, bleeding, notes.
2. Observation entry UX optimized for quick daily logging.
3. Cycle chart and history views.
4. Local persistence and migration strategy.
5. Settings for units, waking-time assumptions, and symptom preferences.

Exit criteria:

1. A user can chart complete cycles offline.
2. Data survives restarts and app updates.
3. Observation categories are stable enough to support later interpretation and encryption.

### Phase 2: Local Encryption and Backup

Goal: protect stored data without introducing a backend.

Deliverables:

1. Local encryption for stored records.
2. Key generation and secure local key storage.
3. Encrypted backup export.
4. Import and restore flow.
5. App access protection where platform support is practical.

Exit criteria:

1. Local data at rest is protected.
2. Backup bundles are restorable.
3. No plaintext health data is emitted through logs or telemetry.

### Phase 3: Sympto-Thermal Interpretation Engine

Goal: implement deterministic, explainable on-device rule evaluation.

Deliverables:

1. Named version 1 rule pack.
2. Temperature shift confirmation logic.
3. Peak Day and mucus confirmation logic.
4. Conservative conflict resolution.
5. Explanation traces for all outputs.
6. Manual override and annotation support.
7. Test fixtures for common and edge-case cycles.

Exit criteria:

1. Every fertile or infertile status can be traced to observations and rules.
2. Ambiguous data yields uncertainty rather than overconfidence.
3. The app clearly communicates contraindications and limitations.

### Phase 4: Exporting and Reporting

Goal: make user data portable and reviewable.

Deliverables:

1. Human-readable cycle reports.
2. Structured CSV or JSON export.
3. Encrypted full-backup export.
4. Provenance details such as app version, rule-pack version, timezone, and unit configuration.

Exit criteria:

1. Users can move or archive their data without lock-in.
2. Exported reports are understandable and reproducible.
3. Backup and restore are documented and tested.

## Initial Repository Shape

Recommended target structure when implementation resumes:

```text
apps/
  mobile/
docs/
  project-plan.md
packages/
  domain/
```

### Expected Purpose of Each Area

1. `apps/mobile`
   Mobile app shell, screens, navigation, UI components, local persistence wiring.

2. `packages/domain`
   Shared schemas, symptom taxonomy, interpretation engine, export models, fixtures.

3. `docs`
   Product decisions, threat model, rule pack notes, and roadmap updates.

## Acceptance Criteria for the Next Implementation Session

When coding resumes, the next step should be to scaffold a local-first workspace and establish the domain model before building interpretation logic.

Recommended order:

1. Create the workspace structure.
2. Define the TypeScript domain types for daily observations and cycles.
3. Define the symptom taxonomy.
4. Build local persistence around those types.
5. Create the first charting screens.

## Open Decisions to Resolve Later

1. Whether version 1 is only for avoiding pregnancy or also supports achieving pregnancy.
2. Whether cervical position is fully supported or remains optional.
3. Whether backup protection uses only device security or also a user passphrase.
4. Whether the future browser version should be read-only first or feature-complete.
5. Whether a later sync system should be self-hostable from day one.

## Summary

The implementation path is intentionally narrow:

1. Build a local-first mobile app first.
2. Keep data on-device.
3. Add encryption locally before any network architecture.
4. Implement a conservative, explainable sympto-thermal rule engine.
5. Treat browser support and sync as later expansion work, not current blockers.