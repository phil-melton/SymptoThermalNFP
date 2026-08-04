import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing } from '../theme';
import type { DailyInterpretation, UserFertilityLabel } from '../types';

interface FeedbackCardProps {
  interpretation: DailyInterpretation;
}

const palette: Record<UserFertilityLabel, { background: string; border: string }> = {
  fertility_possible: { background: colors.possible, border: colors.possibleBorder },
  post_ovulation_confirmed: { background: colors.confirmed, border: colors.confirmedBorder },
  lower_probability_method_rules_apply: { background: colors.lower, border: colors.lowerBorder },
  not_enough_information: { background: colors.incomplete, border: colors.incompleteBorder },
};

export function FeedbackCard({ interpretation }: FeedbackCardProps) {
  const { feedback, progress } = interpretation;
  const selectedPalette = palette[feedback.label];

  return (
    <View
      accessibilityRole="summary"
      style={[
        styles.card,
        { backgroundColor: selectedPalette.background, borderColor: selectedPalette.border },
      ]}
    >
      <Text style={styles.eyebrow}>TODAY'S INTERPRETATION</Text>
      <Text style={styles.headline}>{feedback.headline}</Text>
      <Text style={styles.summary}>{feedback.summary}</Text>
      <Text style={styles.action}>{feedback.action}</Text>

      <View style={styles.divider} />
      <Text style={styles.progressTitle}>Confirmation progress</Text>
      <ProgressRow
        label="Temperature"
        value={
          progress.temperatureConfirmed
            ? 'Confirmed'
            : `${progress.temperatureHighCount}/${progress.temperatureHighRequired} elevated`
        }
      />
      <ProgressRow
        label="Mucus"
        value={
          progress.mucusConfirmed
            ? 'Confirmed'
            : `${progress.mucusLowerQualityCount}/${progress.mucusLowerQualityRequired} after Peak`
        }
      />
      <Text style={styles.nextStep}>{progress.nextStep}</Text>
      {progress.dataQualityMessages.map((message) => (
        <Text key={message} style={styles.quality}>• {message}</Text>
      ))}
    </View>
  );
}

function ProgressRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.progressRow}>
      <Text style={styles.progressLabel}>{label}</Text>
      <Text style={styles.progressValue}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: 20, borderWidth: 2, padding: spacing.lg, gap: spacing.sm },
  eyebrow: { color: colors.muted, fontSize: 12, fontWeight: '800', letterSpacing: 1.1 },
  headline: { color: colors.text, fontSize: 24, lineHeight: 29, fontWeight: '800' },
  summary: { color: colors.text, fontSize: 16, lineHeight: 23 },
  action: { color: colors.text, fontSize: 15, lineHeight: 22, fontWeight: '700' },
  divider: { height: 1, backgroundColor: 'rgba(24, 60, 64, 0.18)', marginVertical: spacing.sm },
  progressTitle: { color: colors.text, fontSize: 14, fontWeight: '800' },
  progressRow: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.md },
  progressLabel: { color: colors.muted, fontSize: 14 },
  progressValue: { color: colors.text, fontSize: 14, fontWeight: '700' },
  nextStep: { color: colors.text, fontSize: 14, lineHeight: 20, marginTop: spacing.xs },
  quality: { color: colors.danger, fontSize: 13, lineHeight: 18 },
});
