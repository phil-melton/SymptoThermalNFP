export type TemperatureUnit = 'celsius' | 'fahrenheit';

export type TrackingGoal =
  | 'avoid_pregnancy'
  | 'achieve_pregnancy'
  | 'understand_cycle';

export type RuleContext =
  | 'standard'
  | 'post_hormonal'
  | 'postpartum'
  | 'post_miscarriage'
  | 'perimenopause';

export type TemperatureDisturbance =
  | 'illness_or_fever'
  | 'poor_sleep'
  | 'later_than_usual'
  | 'alcohol'
  | 'travel'
  | 'measurement_issue'
  | 'other';

export type MucusSign =
  | 'not_checked'
  | 'dry'
  | 'sticky'
  | 'creamy'
  | 'wet'
  | 'slippery';

export type BleedingLevel = 'none' | 'spotting' | 'light' | 'medium' | 'heavy';

export interface AppSettings {
  temperatureUnit: TemperatureUnit;
  defaultWakeTime: string;
  trackingGoal: TrackingGoal;
  ruleContext: RuleContext;
  onboardingComplete: boolean;
}

export interface DailyObservation {
  date: string;
  wakingTemperature: number | null;
  temperatureUnit: TemperatureUnit;
  temperatureTime: string | null;
  temperatureDisturbances: TemperatureDisturbance[];
  mucus: MucusSign;
  bleeding: BleedingLevel;
  notes: string;
}

export type UserFertilityLabel =
  | 'fertility_possible'
  | 'post_ovulation_confirmed'
  | 'lower_probability_method_rules_apply'
  | 'not_enough_information';

export interface InterpretationProgress {
  temperatureHighCount: number;
  temperatureHighRequired: number;
  temperatureConfirmed: boolean;
  mucusLowerQualityCount: number;
  mucusLowerQualityRequired: number;
  mucusConfirmed: boolean;
  temperatureRecordedToday: boolean;
  mucusRecordedToday: boolean;
  dataQualityMessages: string[];
  nextStep: string;
}

export interface UserFeedback {
  label: UserFertilityLabel;
  headline: string;
  summary: string;
  action: string;
}

export interface DailyInterpretation {
  date: string;
  cycleDay: number;
  status:
    | 'relative_infertility'
    | 'potentially_fertile'
    | 'absolute_infertility_from_evening'
    | 'absolute_infertility';
  feedback: UserFeedback;
  progress: InterpretationProgress;
}

export interface CycleInterpretation {
  cycleIndex: number;
  startDate: string;
  endDate: string;
  spanDays: number;
  loggedDays: number;
  fertileWindowStartDate: string;
  peakDay: string | null;
  mucusConfirmationDate: string | null;
  temperatureConfirmationDate: string | null;
  postOvulationStartDate: string | null;
  days: DailyInterpretation[];
  observations: DailyObservation[];
  warnings: string[];
}

export const DEFAULT_SETTINGS: AppSettings = {
  temperatureUnit: 'fahrenheit',
  defaultWakeTime: '06:30',
  trackingGoal: 'understand_cycle',
  ruleContext: 'standard',
  onboardingComplete: false,
};

export function emptyObservation(date: string, settings: AppSettings): DailyObservation {
  return {
    date,
    wakingTemperature: null,
    temperatureUnit: settings.temperatureUnit,
    temperatureTime: settings.defaultWakeTime,
    temperatureDisturbances: [],
    mucus: 'not_checked',
    bleeding: 'none',
    notes: '',
  };
}
