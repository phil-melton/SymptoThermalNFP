# Sensiplan Algorithm Specification (v1 reference for SymptoThermalNFP)

This is the canonical rule set the `algorithm.py` module is targeting. It is the
**Sensiplan double-check symptothermal method** as published by the Arbeitsgruppe
NFP (Düsseldorf/Heidelberg). Citations at bottom. All rules should be implemented
exactly as written; deviations must be documented in code comments.

> **Conservative principle**: when any rule is ambiguous, unmet, or data is
> missing, the day is **fertile (state 1)**, never infertile. The cost of a
> false-infertile is much higher than a false-fertile.

---

## 1. Daily inputs (per cycle day)

- `bbt`: basal body temperature, stored in its **original unit** (do NOT guess
  unit from magnitude — read `temperature_unit` from the DB row).
- `bbt_disturbed`: bool. Disturbances include fever, illness, < 4 h sleep,
  alcohol, unusually late measurement, travel, etc.
- `mucus`: one of {dry, sticky, creamy, watery, slippery} or None.
- `mucus_sensation`: dry / moist / wet-slippery (the *feeling*, distinct from
  what is seen).
- `bleeding`: none / spotting / light / medium / heavy.
- `cervix` (optional): height/firmness/opening — Sensiplan allows cervix to
  *replace* mucus as the second sign but never replace BBT.

## 2. State machine

Three output states per day:
- **S0** — infertile (pre-ovulatory) or menses
- **S1** — fertile
- **S2** — infertile (post-ovulatory)

Transitions: S0 → S1 → S2. Never S2 → S1 within a cycle. New cycle resets to S0
on day 1 of menses.

---

## 3. Opening the fertile window (S0 → S1)

Sensiplan is a **double-check** opener. The fertile window opens at the
**earlier** of (a) and (b):

### (a) Mucus / sensation rule ("first deviation from BIP")
The Basic Infertile Pattern (BIP) is the user's pre-ovulatory baseline of dry
sensation OR an unchanging same-quality discharge over multiple days. The
fertile window opens on the **first day** the mucus or sensation deviates from
BIP (anything wetter, more abundant, or any change toward fertile-type).
For a first-time user with no established BIP, the window opens on the first
day of *any* mucus observation.

### (b) Calculation rule (Doering / "minus 8")
Applies only **after the user has charted ≥ 12 cycles**. Otherwise skip (b).
- Find the earliest 1st-higher-temperature day across all prior cycles.
- Subtract 8.
- That cycle day is the last infertile day by calculation.
- The fertile window opens on the day **after** that.

### First-cycle rule (5-day rule)
For a user's **very first** charted cycle, Sensiplan does not allow any
pre-ovulatory infertile days beyond menses. All non-menses days before the
fertile-window confirmation are S1.

### Menses
Days of medium/heavy bleeding at cycle start are S0 (menses-infertile)
**only** if the previous cycle had a confirmed post-ovulatory phase. Otherwise
treat as S1 (intermenstrual bleeding can mask fertile mucus).

---

## 4. Closing the fertile window (S1 → S2)

Sensiplan requires **BOTH** the temperature rule AND the peak rule to be met.
The transition to S2 happens on the **evening** of whichever rule is satisfied
*later*.

### 4.1 Temperature rule (3-over-6)

1. Identify a candidate "1st higher temperature": a day whose BBT is **strictly
   greater than** the highest of the **6 immediately preceding valid** temperatures.
   - "Valid" = not disturbed, not missing. Disturbed/missing days are skipped
     when counting back to find 6 lows; they do not reset the window.
2. The 2nd day must also be **strictly greater than** the same 6-low maximum
   (the "coverline").
3. The 3rd day must be **≥ coverline + 0.2 °C (≥ coverline + 0.4 °F)**.
   - **NOTE**: many secondary sources say 0.9 °F. The Sensiplan handbook
     specifies **2/10 °C, which rounds to 0.4 °F** when working in Fahrenheit
     at 0.1° resolution. Implement in the storage unit consistently.
4. **Exception 1 (slow rise)**: if days 1 and 2 are above coverline but day 3
   is above coverline by less than 0.2 °C, wait for a **4th** day. The 4th day
   must be strictly above the coverline (no +0.2 °C requirement). All 4 days
   must remain above coverline.
5. **Exception 2 (drop-back)**: among the 3 (or 4) higher days, **one** value
   may fall back to or below the coverline. That day is excluded and an
   additional higher day is required to replace it.
6. Disturbed temperatures within the higher-temperature window are **excluded**
   and replaced (treated like the drop-back exception).

The temperature rule is **satisfied on the evening** of the day the 3rd
(or 4th) qualifying high temperature is recorded.

### 4.2 Peak day rule

1. **Peak day** = the **last day** of best-quality mucus OR wet/slippery
   sensation, identifiable only **retrospectively** (the next day shows a
   clear change to drier/less fertile).
   - "Best-quality" is defined per-user. For users who never see slippery,
     it may be creamy/watery. Do **not** require slippery to declare a peak.
2. The peak rule is satisfied on the **evening of the 3rd day** after peak,
   provided all 3 days following peak show a clearly drier pattern than peak.
3. If the temperature rule was a slow-rise (Exception 1), the peak rule
   requires **4** dry days after peak instead of 3.

### 4.3 Combined (double-check)

- `t_post_ov_evening = max(temp_rule_satisfied_evening, peak_rule_satisfied_evening)`
- The day **following** that evening is the first full S2 day.
- If either rule is never satisfied in the cycle, the cycle has **no** S2
  phase. The whole post-fertile-opening cycle remains S1 until next menses.

---

## 5. Disqualifiers (force whole cycle to S1, no S2)

- Fever ≥ 38 °C during the relevant window.
- Postpartum, breastfeeding, perimenopause, post-hormonal-contraceptive
  return-of-fertility cycles → require special rule packs not in v1.
- < 3 valid mucus observations in the cycle.
- < 6 valid temperatures before the candidate rise.
- Cycle marked by user as anovulatory or disturbed.

---

## 6. Things that are **NOT** part of Sensiplan and must not be added silently

- No "predict next ovulation by averaging cycle length."
- No moving-average smoothing of BBT.
- No machine learning. Rules only, all explainable.
- Cervix position is a **substitute** for mucus, not an averaging input.

---

## 7. Sources

1. Arbeitsgruppe NFP. *Natürlich und sicher — Das Praxisbuch* (Sensiplan
   handbook), TRIAS Verlag. Primary source for all numeric thresholds.
2. Frank-Herrmann P, Heil J, Gnoth C, et al. *The effectiveness of a fertility
   awareness based method to avoid pregnancy in relation to a couple's sexual
   behaviour during the fertile time.* Hum Reprod. 2007;22(5):1310–1319.
3. Duane M, Stanford JB, Porucznik CA, Vigil P. *Fertility Awareness-Based
   Methods for Women's Health and Family Planning.* Front Med. 2022. PMC9171018.
4. Peragallo Urrutia R et al. *Effectiveness of Fertility Awareness-Based
   Methods for Pregnancy Prevention: A Systematic Review.* Obstet Gynecol.
   2018;132(3):591–604.

The agent should treat the Sensiplan handbook (source 1) as authoritative and
flag any place where this spec is ambiguous so it can be reconciled against the
handbook directly.
