import { ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, spacing } from '../theme';
import type { CycleInterpretation, DailyObservation, UserFertilityLabel } from '../types';

const DAY_WIDTH = 50;
const PLOT_HEIGHT = 176;

const statusColors: Record<UserFertilityLabel, string> = {
  fertility_possible: colors.possible,
  post_ovulation_confirmed: colors.confirmed,
  lower_probability_method_rules_apply: colors.lower,
  not_enough_information: colors.incomplete,
};

export function CycleChart({ cycle }: { cycle: CycleInterpretation }) {
  const usableTemperatures = cycle.observations
    .filter((item) => item.wakingTemperature !== null && item.temperatureDisturbances.length === 0)
    .map((item) => displayTemperature(item));
  const min = usableTemperatures.length ? Math.min(...usableTemperatures) - 0.15 : 96.8;
  const max = usableTemperatures.length ? Math.max(...usableTemperatures) + 0.15 : 98.6;
  const chartWidth = Math.max(cycle.observations.length * DAY_WIDTH, 320);
  const points = cycle.observations.map((observation, index) => {
    if (observation.wakingTemperature === null || observation.temperatureDisturbances.length) {
      return null;
    }
    const temperature = displayTemperature(observation);
    return {
      x: index * DAY_WIDTH + DAY_WIDTH / 2,
      y: temperatureY(temperature, min, max) + 5,
    };
  });

  return (
    <View style={styles.wrapper}>
      <Text style={styles.chartTitle}>Temperature and daily signs</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator accessibilityLabel="Scrollable cycle chart">
        <View style={[styles.chart, { width: chartWidth }]}>
          {cycle.observations.map((observation, index) => {
            const interpretation = cycle.days[index];
            const temperature =
              observation.wakingTemperature !== null && observation.temperatureDisturbances.length === 0
                ? displayTemperature(observation)
                : null;
            const y = temperature === null ? null : temperatureY(temperature, min, max);
            return (
              <View
                key={observation.date}
                style={[
                  styles.dayColumn,
                  {
                    left: index * DAY_WIDTH,
                    backgroundColor: interpretation
                      ? statusColors[interpretation.feedback.label]
                      : colors.incomplete,
                  },
                ]}
              >
                <Text style={styles.dayNumber}>{interpretation?.cycleDay ?? index + 1}</Text>
                {y !== null ? (
                  <View style={[styles.temperaturePoint, { top: y }]} accessibilityLabel={`${temperature?.toFixed(2)} degrees`} />
                ) : (
                  <Text style={styles.missingPoint}>×</Text>
                )}
                <Text style={styles.mucusLabel}>{mucusAbbreviation(observation.mucus)}</Text>
                <Text style={styles.bleedingLabel}>{bleedingAbbreviation(observation.bleeding)}</Text>
              </View>
            );
          })}
          {points.slice(1).map((point, index) => {
            const previous = points[index];
            if (!point || !previous) return null;
            const width = Math.hypot(point.x - previous.x, point.y - previous.y);
            const angle = Math.atan2(point.y - previous.y, point.x - previous.x) * 180 / Math.PI;
            return (
              <View
                key={`line-${index}`}
                style={[
                  styles.temperatureLine,
                  {
                    left: (point.x + previous.x) / 2 - width / 2,
                    top: (point.y + previous.y) / 2 - 1,
                    width,
                    transform: [{ rotate: `${angle}deg` }],
                  },
                ]}
              />
            );
          })}
        </View>
      </ScrollView>
      <View style={styles.legend}>
        <Legend color={colors.possible} label="Fertility possible" />
        <Legend color={colors.confirmed} label="Post-ovulation confirmed" />
        <Legend color={colors.lower} label="Lower probability — rules apply" />
        <Legend color={colors.incomplete} label="Not enough information" />
      </View>
      <Text style={styles.help}>Mucus: D dry · S sticky · C creamy · W wet · Sl slippery · — not checked</Text>
      <Text style={styles.help}>Bleeding: Sp spotting · L light · M medium · H heavy</Text>
    </View>
  );
}

function Legend({ color, label }: { color: string; label: string }) {
  return (
    <View style={styles.legendItem}>
      <View style={[styles.swatch, { backgroundColor: color }]} />
      <Text style={styles.legendText}>{label}</Text>
    </View>
  );
}

function temperatureY(value: number, min: number, max: number): number {
  const plotRange = PLOT_HEIGHT - 46;
  return 26 + ((max - value) / Math.max(max - min, 0.1)) * plotRange;
}

function displayTemperature(observation: DailyObservation): number {
  const value = observation.wakingTemperature ?? 0;
  return observation.temperatureUnit === 'fahrenheit' ? ((value - 32) * 5) / 9 : value;
}

function mucusAbbreviation(value: DailyObservation['mucus']): string {
  return { not_checked: '—', dry: 'D', sticky: 'S', creamy: 'C', wet: 'W', slippery: 'Sl' }[value];
}

function bleedingAbbreviation(value: DailyObservation['bleeding']): string {
  return { none: '', spotting: 'Sp', light: 'L', medium: 'M', heavy: 'H' }[value];
}

const styles = StyleSheet.create({
  wrapper: { backgroundColor: colors.surface, borderRadius: 18, padding: spacing.md, gap: spacing.md },
  chartTitle: { color: colors.text, fontSize: 18, fontWeight: '800' },
  chart: { height: PLOT_HEIGHT + 58, position: 'relative', borderBottomWidth: 1, borderColor: colors.border },
  dayColumn: {
    position: 'absolute',
    top: 0,
    width: DAY_WIDTH,
    height: PLOT_HEIGHT + 58,
    borderRightWidth: 1,
    borderRightColor: 'rgba(24, 60, 64, 0.12)',
    alignItems: 'center',
  },
  dayNumber: { color: colors.text, fontSize: 12, fontWeight: '800', marginTop: spacing.xs },
  temperaturePoint: {
    position: 'absolute',
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.primary,
    borderWidth: 2,
    borderColor: colors.surface,
    zIndex: 3,
  },
  temperatureLine: { position: 'absolute', height: 2, backgroundColor: colors.primary, zIndex: 2 },
  missingPoint: { position: 'absolute', top: 86, color: colors.muted, fontSize: 18 },
  mucusLabel: { position: 'absolute', bottom: 24, color: '#66447A', fontSize: 13, fontWeight: '800' },
  bleedingLabel: { position: 'absolute', bottom: 5, color: colors.danger, fontSize: 12, fontWeight: '800' },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6, width: '47%' },
  swatch: { width: 14, height: 14, borderWidth: 1, borderColor: colors.border },
  legendText: { flex: 1, color: colors.text, fontSize: 12 },
  help: { color: colors.muted, fontSize: 12, lineHeight: 17 },
});
