import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, spacing } from '../theme';
import type { CycleInterpretation } from '../types';

interface HistoryScreenProps {
  cycles: CycleInterpretation[];
  onOpenCycle: (index: number) => void;
}

export function HistoryScreen({ cycles, onOpenCycle }: HistoryScreenProps) {
  if (!cycles.length) {
    return (
      <View style={styles.empty}>
        <Text style={styles.emptyTitle}>No cycle history yet</Text>
        <Text style={styles.emptyText}>Cycles appear here after you begin daily charting.</Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.title}>Cycle history</Text>
      <Text style={styles.subtitle}>Your records remain in the app’s on-device SQLite database.</Text>
      {[...cycles].reverse().map((cycle) => {
        const originalIndex = cycles.indexOf(cycle);
        const latest = cycle.days.at(-1);
        return (
          <Pressable
            key={`${cycle.startDate}-${cycle.cycleIndex}`}
            accessibilityRole="button"
            onPress={() => onOpenCycle(originalIndex)}
            style={({ pressed }) => [styles.card, pressed && styles.pressed]}
          >
            <View style={styles.cardHeader}>
              <Text style={styles.cycleTitle}>Cycle {cycle.cycleIndex}</Text>
              <Text style={styles.open}>View chart</Text>
            </View>
            <Text style={styles.range}>{formatDate(cycle.startDate)}–{formatDate(cycle.endDate)}</Text>
            <Text style={styles.meta}>{cycle.spanDays} calendar days · {cycle.loggedDays} logged days</Text>
            <Text style={styles.status}>{latest?.feedback.headline ?? 'Not enough information'}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', year: 'numeric' }).format(new Date(`${value}T12:00:00`));
}

const styles = StyleSheet.create({
  content: { padding: spacing.md, paddingBottom: spacing.xl, gap: spacing.md },
  title: { color: colors.text, fontSize: 28, fontWeight: '900' },
  subtitle: { color: colors.muted, fontSize: 14, lineHeight: 20, marginTop: -spacing.sm },
  card: { backgroundColor: colors.surface, borderRadius: 18, borderWidth: 1, borderColor: colors.border, padding: spacing.md, gap: spacing.sm },
  pressed: { opacity: 0.7 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  cycleTitle: { color: colors.text, fontSize: 19, fontWeight: '800' },
  open: { color: colors.primary, fontSize: 14, fontWeight: '800' },
  range: { color: colors.text, fontSize: 15, fontWeight: '700' },
  meta: { color: colors.muted, fontSize: 13 },
  status: { color: colors.primary, fontSize: 14, fontWeight: '800', marginTop: spacing.xs },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: spacing.xl, gap: spacing.sm },
  emptyTitle: { color: colors.text, fontSize: 24, fontWeight: '800' },
  emptyText: { color: colors.muted, fontSize: 15, lineHeight: 22, textAlign: 'center' },
});
