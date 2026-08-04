import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { CycleChart } from '../components/CycleChart';
import { colors, spacing } from '../theme';
import type { CycleInterpretation } from '../types';

interface ChartScreenProps {
  cycles: CycleInterpretation[];
  selectedIndex: number;
  onSelect: (index: number) => void;
}

export function ChartScreen({ cycles, selectedIndex, onSelect }: ChartScreenProps) {
  const cycle = cycles[selectedIndex];
  if (!cycle) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyTitle}>No chart yet</Text>
        <Text style={styles.emptyText}>Save today’s temperature or symptoms to begin a chart.</Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.title}>Cycle chart</Text>
      <View style={styles.cyclePicker}>
        {cycles.map((item, index) => (
          <Pressable
            key={`${item.startDate}-${item.cycleIndex}`}
            onPress={() => onSelect(index)}
            style={[styles.cycleButton, index === selectedIndex && styles.selectedCycle]}
          >
            <Text style={[styles.cycleButtonText, index === selectedIndex && styles.selectedCycleText]}>
              Cycle {item.cycleIndex}
            </Text>
          </Pressable>
        ))}
      </View>
      <View>
        <Text style={styles.range}>{formatShort(cycle.startDate)}–{formatShort(cycle.endDate)} · {cycle.spanDays} days</Text>
        <Text style={styles.meta}>Peak: {cycle.peakDay ? formatShort(cycle.peakDay) : 'not confirmed'} · Temperature: {cycle.temperatureConfirmationDate ? formatShort(cycle.temperatureConfirmationDate) : 'not confirmed'}</Text>
      </View>
      <CycleChart cycle={cycle} />
      {cycle.warnings.length ? (
        <View style={styles.warningCard}>
          <Text style={styles.warningTitle}>Chart notes</Text>
          {cycle.warnings.map((warning) => <Text key={warning} style={styles.warningText}>• {warning}</Text>)}
        </View>
      ) : null}
      <Text style={styles.disclaimer}>Tap History to review another cycle. Editing a past day will be added in the next workflow increment.</Text>
    </ScrollView>
  );
}

function formatShort(value: string): string {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(`${value}T12:00:00`));
}

const styles = StyleSheet.create({
  content: { padding: spacing.md, paddingBottom: spacing.xl, gap: spacing.md },
  title: { color: colors.text, fontSize: 28, fontWeight: '900' },
  cyclePicker: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  cycleButton: { minHeight: 42, paddingHorizontal: spacing.md, justifyContent: 'center', borderRadius: 21, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface },
  selectedCycle: { backgroundColor: colors.primarySoft, borderColor: colors.primary, borderWidth: 2 },
  cycleButtonText: { color: colors.muted, fontSize: 14, fontWeight: '700' },
  selectedCycleText: { color: colors.primary, fontWeight: '800' },
  range: { color: colors.text, fontSize: 17, fontWeight: '800' },
  meta: { color: colors.muted, fontSize: 13, lineHeight: 19, marginTop: spacing.xs },
  warningCard: { backgroundColor: colors.possible, borderLeftWidth: 4, borderLeftColor: colors.possibleBorder, padding: spacing.md, gap: spacing.sm },
  warningTitle: { color: colors.text, fontSize: 16, fontWeight: '800' },
  warningText: { color: colors.text, fontSize: 14, lineHeight: 20 },
  disclaimer: { color: colors.muted, fontSize: 12, lineHeight: 18 },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl, gap: spacing.sm },
  emptyTitle: { color: colors.text, fontSize: 24, fontWeight: '800' },
  emptyText: { color: colors.muted, fontSize: 15, lineHeight: 22, textAlign: 'center' },
});
