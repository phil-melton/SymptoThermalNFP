import type {
  AppSettings,
  CycleInterpretation,
  DailyInterpretation,
  DailyObservation,
  InterpretationProgress,
  TrackingGoal,
  UserFeedback,
  UserFertilityLabel,
} from './types';

const DAY_MS = 86_400_000;
const BBT_THRESHOLD_C = 0.2;

type InternalStatus = DailyInterpretation['status'];

interface TemperatureShift {
  confirmedDate: string;
  highCount: number;
}

export function evaluateObservations(
  observations: DailyObservation[],
  settings: AppSettings,
): CycleInterpretation[] {
  const cycles = splitCycles(observations);
  const results: CycleInterpretation[] = [];
  const previousLengths: number[] = [];

  cycles.forEach((cycle, index) => {
    const result = evaluateCycle(cycle, index + 1, previousLengths, settings);
    results.push(result);
    previousLengths.push(result.spanDays);
  });
  return results;
}

function evaluateCycle(
  observations: DailyObservation[],
  cycleIndex: number,
  previousLengths: number[],
  settings: AppSettings,
): CycleInterpretation {
  const startDate = observations[0]?.date;
  const endDate = observations.at(-1)?.date;
  if (!startDate || !endDate) {
    throw new Error('Cannot interpret an empty cycle.');
  }

  const peakDay = findPeakDay(observations);
  const mucusConfirmationDate = findMucusConfirmationDate(observations);
  const temperatureShift = findTemperatureShift(observations, settings, peakDay);
  const postOvulationStartDate =
    mucusConfirmationDate && temperatureShift
      ? maxDate(mucusConfirmationDate, temperatureShift.confirmedDate)
      : null;
  const fertileWindowStartDate = findFertileWindowStart(
    observations,
    previousLengths,
    settings,
  );

  const days = observations.map((observation, index): DailyInterpretation => {
    let status: InternalStatus;
    if (postOvulationStartDate && observation.date > postOvulationStartDate) {
      status = 'absolute_infertility';
    } else if (postOvulationStartDate && observation.date === postOvulationStartDate) {
      status = 'absolute_infertility_from_evening';
    } else if (observation.date < fertileWindowStartDate) {
      status = 'relative_infertility';
    } else {
      status = 'potentially_fertile';
    }

    const progress = interpretationProgress(observations.slice(0, index + 1), settings);
    return {
      date: observation.date,
      cycleDay: daysBetween(startDate, observation.date) + 1,
      status,
      progress,
      feedback: userFeedback(
        status,
        progress,
        settings.trackingGoal,
        status === 'absolute_infertility_from_evening',
      ),
    };
  });

  const warnings: string[] = [];
  if (previousLengths.length < 4) {
    warnings.push('Fewer than four prior cycles are available; Phase 1 is treated as fertile.');
  }
  if (settings.ruleContext !== 'standard') {
    warnings.push('Special context: pre-ovulatory lower-probability days are not calculated.');
  }
  if (!observations.some((item) => item.mucus !== 'not_checked')) {
    warnings.push('No mucus observations are available; temperature alone cannot identify the fertile-window start.');
  }
  if (
    observations.some((item) => {
      const value = temperatureCelsius(item, settings);
      return value !== null && value >= 38;
    })
  ) {
    warnings.push('An elevated temperature may make BBT interpretation unreliable.');
  }

  return {
    cycleIndex,
    startDate,
    endDate,
    spanDays: daysBetween(startDate, endDate) + 1,
    loggedDays: observations.length,
    fertileWindowStartDate,
    peakDay,
    mucusConfirmationDate,
    temperatureConfirmationDate: temperatureShift?.confirmedDate ?? null,
    postOvulationStartDate,
    days,
    observations,
    warnings,
  };
}

function splitCycles(observations: DailyObservation[]): DailyObservation[][] {
  const sorted = [...observations].sort((a, b) => a.date.localeCompare(b.date));
  const cycles: DailyObservation[][] = [];
  let current: DailyObservation[] = [];
  let previous: DailyObservation | null = null;

  for (const observation of sorted) {
    const beginsMenses = isMenses(observation.bleeding);
    const newCycle = beginsMenses && previous !== null && !isMenses(previous.bleeding);
    if (newCycle && current.length) {
      cycles.push(current);
      current = [];
    }
    current.push(observation);
    previous = observation;
  }
  if (current.length) {
    cycles.push(current);
  }
  return cycles;
}

function findFertileWindowStart(
  observations: DailyObservation[],
  previousLengths: number[],
  settings: AppSettings,
): string {
  const start = observations[0]?.date;
  if (!start || settings.ruleContext !== 'standard') {
    return start ?? '';
  }

  let calendarStart = start;
  if (previousLengths.length >= 4) {
    const shortest = Math.min(...previousLengths);
    let lastLowerProbabilityOffset: number;
    if (previousLengths.length <= 6) {
      lastLowerProbabilityOffset = Math.min(Math.max(shortest - 21, 0), 5);
    } else if (previousLengths.length <= 12) {
      lastLowerProbabilityOffset = Math.max(shortest - 21, 0);
    } else {
      lastLowerProbabilityOffset = Math.max(shortest - 20, 0);
    }
    calendarStart = addDays(start, lastLowerProbabilityOffset);
  }

  const physicalStart = observations.find(
    (item) => item.mucus !== 'not_checked' && item.mucus !== 'dry',
  )?.date;
  return physicalStart ? minDate(calendarStart, physicalStart) : calendarStart;
}

function findPeakDay(observations: DailyObservation[]): string | null {
  let lastPeakIndex = -1;
  observations.forEach((observation, index) => {
    if (isPeakQuality(observation)) {
      lastPeakIndex = index;
    }
  });
  if (lastPeakIndex < 0) {
    return null;
  }
  return observations.slice(lastPeakIndex + 1).some(isLowerQualityOrDry)
    ? observations[lastPeakIndex]?.date ?? null
    : null;
}

function findMucusConfirmationDate(observations: DailyObservation[]): string | null {
  let lastPeakIndex = -1;
  observations.forEach((observation, index) => {
    if (isPeakQuality(observation)) {
      lastPeakIndex = index;
    }
  });
  if (lastPeakIndex < 0) {
    return null;
  }

  let expected = addDays(observations[lastPeakIndex]!.date, 1);
  let count = 0;
  for (const observation of observations.slice(lastPeakIndex + 1)) {
    if (observation.date !== expected || observation.mucus === 'not_checked') {
      return null;
    }
    expected = addDays(expected, 1);
    if (!isLowerQualityOrDry(observation)) {
      return null;
    }
    count += 1;
    if (count === 3) {
      return observation.date;
    }
  }
  return null;
}

function findTemperatureShift(
  observations: DailyObservation[],
  settings: AppSettings,
  peakDay: string | null,
): TemperatureShift | null {
  const temperatures = observations.map((item) => temperatureCelsius(item, settings));
  const requireFourth = peakDay === null;

  for (let highStart = 6; highStart < observations.length; highStart += 1) {
    const highStartDate = observations[highStart]?.date;
    if (!highStartDate || (peakDay && highStartDate < addDays(peakDay, 1))) {
      continue;
    }
    if (!datesConsecutive(observations, highStart - 6, 9)) {
      continue;
    }
    const baseline = temperatures.slice(highStart - 6, highStart);
    const highs = temperatures.slice(highStart, highStart + 3);
    if (baseline.some((value) => value === null) || highs.some((value) => value === null)) {
      continue;
    }
    const coverline = Math.max(...(baseline as number[]));
    if (!(highs as number[]).every((value) => value > coverline)) {
      continue;
    }
    const third = highs[2] as number;
    const needsFourth = requireFourth || third + 1e-9 < coverline + BBT_THRESHOLD_C;
    if (needsFourth) {
      const fourthIndex = highStart + 3;
      const fourth = temperatures[fourthIndex];
      if (
        fourth === undefined ||
        fourth === null ||
        fourth <= coverline ||
        !datesConsecutive(observations, highStart, 4)
      ) {
        continue;
      }
      return { confirmedDate: observations[fourthIndex]!.date, highCount: 4 };
    }
    return { confirmedDate: observations[highStart + 2]!.date, highCount: 3 };
  }
  return null;
}

function interpretationProgress(
  observations: DailyObservation[],
  settings: AppSettings,
): InterpretationProgress {
  const today = observations.at(-1)!;
  const peakDay = findPeakDay(observations);
  const shift = findTemperatureShift(observations, settings, peakDay);
  const temperature = shift
    ? { count: shift.highCount, required: shift.highCount, confirmed: true }
    : temperatureHighProgress(observations, settings, peakDay);
  const mucusCount = mucusProgress(observations);
  const dataQualityMessages: string[] = [];

  if (today.wakingTemperature === null) {
    dataQualityMessages.push('No waking temperature was recorded today.');
  } else if (today.temperatureDisturbances.length) {
    dataQualityMessages.push("Today's temperature is marked disturbed and excluded from confirmation.");
  }
  if (today.mucus === 'not_checked') {
    dataQualityMessages.push('Mucus was not checked today; missing does not count as dry.');
  }

  let nextStep: string;
  if (today.wakingTemperature === null) {
    nextStep = 'Record a waking temperature before getting out of bed.';
  } else if (today.mucus === 'not_checked') {
    nextStep = 'Record the most fertile mucus sign noticed today.';
  } else if (!temperature.confirmed) {
    nextStep = temperature.count
      ? `Continue BBT charting; ${Math.max(temperature.required - temperature.count, 1)} more qualifying elevated temperature may be needed.`
      : 'Continue daily BBT charting to establish six low temperatures.';
  } else if (mucusCount < 3) {
    nextStep = `Continue mucus charting; ${3 - mucusCount} more lower-quality or dry day may be needed after Peak.`;
  } else {
    nextStep = 'Temperature and mucus double-checks are confirmed.';
  }

  return {
    temperatureHighCount: temperature.count,
    temperatureHighRequired: temperature.required,
    temperatureConfirmed: temperature.confirmed,
    mucusLowerQualityCount: Math.min(mucusCount, 3),
    mucusLowerQualityRequired: 3,
    mucusConfirmed: mucusCount >= 3,
    temperatureRecordedToday: today.wakingTemperature !== null,
    mucusRecordedToday: today.mucus !== 'not_checked',
    dataQualityMessages,
    nextStep,
  };
}

function temperatureHighProgress(
  observations: DailyObservation[],
  settings: AppSettings,
  peakDay: string | null,
): { count: number; required: number; confirmed: boolean } {
  const temperatures = observations.map((item) => temperatureCelsius(item, settings));
  let required = peakDay ? 3 : 4;
  let bestCount = 0;

  for (let highStart = 6; highStart < observations.length; highStart += 1) {
    const highStartDate = observations[highStart]?.date;
    if (!highStartDate || (peakDay && highStartDate < addDays(peakDay, 1))) {
      continue;
    }
    if (!datesConsecutive(observations, highStart - 6, 7)) {
      continue;
    }
    const baseline = temperatures.slice(highStart - 6, highStart);
    if (baseline.some((value) => value === null)) {
      continue;
    }
    const coverline = Math.max(...(baseline as number[]));
    let count = 0;
    for (let index = highStart; index < Math.min(observations.length, highStart + 4); index += 1) {
      const value = temperatures[index];
      if (value === null || value === undefined || value <= coverline) {
        break;
      }
      count += 1;
    }
    if (highStart + count !== observations.length) {
      continue;
    }
    if (count >= 3 && (temperatures[highStart + 2] as number) < coverline + BBT_THRESHOLD_C) {
      required = 4;
    }
    bestCount = Math.max(bestCount, Math.min(count, required));
  }
  return { count: bestCount, required, confirmed: false };
}

function mucusProgress(observations: DailyObservation[]): number {
  let lastPeakIndex = -1;
  observations.forEach((observation, index) => {
    if (isPeakQuality(observation)) {
      lastPeakIndex = index;
    }
  });
  if (lastPeakIndex < 0) {
    return 0;
  }

  let expected = addDays(observations[lastPeakIndex]!.date, 1);
  let count = 0;
  for (const observation of observations.slice(lastPeakIndex + 1)) {
    if (
      observation.date !== expected ||
      observation.mucus === 'not_checked' ||
      !isLowerQualityOrDry(observation)
    ) {
      return 0;
    }
    expected = addDays(expected, 1);
    count += 1;
  }
  return count;
}

function userFeedback(
  status: InternalStatus,
  progress: InterpretationProgress,
  goal: TrackingGoal,
  beginsThisEvening: boolean,
): UserFeedback {
  let label: UserFertilityLabel;
  let headline: string;
  let summary: string;

  if (status === 'absolute_infertility' || status === 'absolute_infertility_from_evening') {
    label = 'post_ovulation_confirmed';
    headline = 'Post-ovulation phase confirmed';
    summary = `Temperature and mucus double-checks confirm the post-ovulation phase${beginsThisEvening ? ' beginning this evening.' : '.'}`;
  } else if (!progress.temperatureRecordedToday && !progress.mucusRecordedToday) {
    label = 'not_enough_information';
    headline = 'Not enough information';
    summary = 'No temperature or mucus observation is available for today.';
  } else if (status === 'relative_infertility') {
    label = 'lower_probability_method_rules_apply';
    headline = 'Lower probability — method rules apply';
    summary = 'A conservative Phase 1 rule applies; this is not a guarantee.';
  } else {
    label = 'fertility_possible';
    headline = 'Fertility possible';
    summary = 'The post-ovulation temperature and mucus double-check is not confirmed.';
  }

  return { label, headline, summary, action: feedbackAction(label, goal) };
}

function feedbackAction(label: UserFertilityLabel, goal: TrackingGoal): string {
  if (goal === 'avoid_pregnancy') {
    if (label === 'fertility_possible' || label === 'not_enough_information') {
      return 'If avoiding pregnancy, treat today as potentially fertile and follow your chosen method.';
    }
    if (label === 'lower_probability_method_rules_apply') {
      return "Follow your method's Phase 1 instructions; lower probability is not zero.";
    }
    return "Apply your chosen method's post-ovulation instructions.";
  }
  if (goal === 'achieve_pregnancy') {
    if (label === 'fertility_possible') {
      return 'If trying to conceive, this may be a fertile day.';
    }
    if (label === 'post_ovulation_confirmed') {
      return 'The fertile window appears closed for this cycle.';
    }
  }
  return 'Keep recording temperature and the most fertile mucus sign each day.';
}

function temperatureCelsius(
  observation: DailyObservation,
  settings: AppSettings,
): number | null {
  if (observation.wakingTemperature === null || observation.temperatureDisturbances.length) {
    return null;
  }
  const unit = observation.temperatureUnit ?? settings.temperatureUnit;
  return unit === 'fahrenheit'
    ? ((observation.wakingTemperature - 32) * 5) / 9
    : observation.wakingTemperature;
}

function isPeakQuality(observation: DailyObservation): boolean {
  return observation.mucus === 'wet' || observation.mucus === 'slippery';
}

function isLowerQualityOrDry(observation: DailyObservation): boolean {
  return ['dry', 'sticky', 'creamy'].includes(observation.mucus);
}

function isMenses(bleeding: DailyObservation['bleeding']): boolean {
  return bleeding === 'medium' || bleeding === 'heavy';
}

function datesConsecutive(
  observations: DailyObservation[],
  startIndex: number,
  length: number,
): boolean {
  if (startIndex < 0 || startIndex + length > observations.length) {
    return false;
  }
  for (let index = startIndex + 1; index < startIndex + length; index += 1) {
    if (observations[index]?.date !== addDays(observations[index - 1]!.date, 1)) {
      return false;
    }
  }
  return true;
}

function addDays(value: string, days: number): string {
  const date = new Date(`${value}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function daysBetween(start: string, end: string): number {
  return Math.round(
    (Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / DAY_MS,
  );
}

function minDate(first: string, second: string): string {
  return first < second ? first : second;
}

function maxDate(first: string, second: string): string {
  return first > second ? first : second;
}
