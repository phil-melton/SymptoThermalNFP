import { evaluateObservations } from '../src/domain';
import {
  DEFAULT_SETTINGS,
  type AppSettings,
  type DailyObservation,
  type MucusSign,
} from '../src/types';

const settings: AppSettings = {
  ...DEFAULT_SETTINGS,
  onboardingComplete: true,
  temperatureUnit: 'celsius',
};

const cycle = buildCycle();
const interpreted = evaluateObservations(cycle, settings)[0];
assert(interpreted !== undefined, 'Expected a cycle interpretation.');
assert(interpreted.peakDay === '2026-04-06', 'Expected Peak Day on April 6.');
assert(interpreted.mucusConfirmationDate === '2026-04-09', 'Expected third lower-quality day on April 9.');
assert(interpreted.temperatureConfirmationDate === '2026-04-09', 'Expected temperature confirmation on April 9.');
assert(interpreted.days[8]?.feedback.headline === 'Post-ovulation phase confirmed', 'Expected plain-language confirmation.');

const missingMucus = buildCycle();
missingMucus[6] = { ...missingMucus[6]!, mucus: 'not_checked' };
const missingResult = evaluateObservations(missingMucus, settings)[0];
assert(missingResult?.mucusConfirmationDate === null, 'Missing mucus must not count as dry.');
assert(missingResult?.postOvulationStartDate === null, 'Missing mucus must block the double-check.');

const noSigns: DailyObservation = {
  date: '2026-04-01',
  wakingTemperature: null,
  temperatureUnit: 'celsius',
  temperatureTime: null,
  temperatureDisturbances: [],
  mucus: 'not_checked',
  bleeding: 'none',
  notes: '',
};
const incomplete = evaluateObservations([noSigns], settings)[0]?.days[0]?.feedback;
assert(incomplete?.label === 'not_enough_information', 'Expected incomplete-data feedback.');

const avoidSettings: AppSettings = { ...settings, trackingGoal: 'avoid_pregnancy' };
const dryObservation = { ...noSigns, mucus: 'dry' as const };
const avoidFeedback = evaluateObservations([dryObservation], avoidSettings)[0]?.days[0]?.feedback;
assert(avoidFeedback?.label === 'fertility_possible', 'Dry on the first cycle must remain potentially fertile.');
assert(avoidFeedback.action.includes('treat today as potentially fertile'), 'Expected goal-aware conservative guidance.');

console.log('Mobile domain checks passed.');

function buildCycle(): DailyObservation[] {
  const temperatures = [36.42, 36.44, 36.46, 36.48, 36.40, 36.50, 36.75, 36.78, 36.82, 36.80, 36.79, 36.81];
  return temperatures.map((temperature, index) => {
    const day = index + 1;
    let mucus: MucusSign = 'dry';
    if (day === 6) mucus = 'slippery';
    if (day >= 7 && day <= 9) mucus = 'sticky';
    return {
      date: `2026-04-${String(day).padStart(2, '0')}`,
      wakingTemperature: temperature,
      temperatureUnit: 'celsius',
      temperatureTime: '06:30',
      temperatureDisturbances: [],
      mucus,
      bleeding: day === 1 ? 'medium' : 'none',
      notes: '',
    };
  });
}

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}
