import { useEffect, useState, type ReactNode } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';

import { ChoiceChip } from '../components/ChoiceChip';
import { FeedbackCard } from '../components/FeedbackCard';
import { colors, spacing } from '../theme';
import {
  emptyObservation,
  type AppSettings,
  type BleedingLevel,
  type DailyInterpretation,
  type DailyObservation,
  type MucusSign,
  type TemperatureDisturbance,
} from '../types';

interface TodayScreenProps {
  date: string;
  settings: AppSettings;
  observation: DailyObservation | null;
  interpretation: DailyInterpretation;
  saving: boolean;
  onSave: (observation: DailyObservation) => Promise<void>;
  onEditSetup: () => void;
}

const disturbances: { value: TemperatureDisturbance; label: string }[] = [
  { value: 'illness_or_fever', label: 'Illness / fever' },
  { value: 'poor_sleep', label: 'Poor sleep' },
  { value: 'later_than_usual', label: 'Later than usual' },
  { value: 'alcohol', label: 'Alcohol' },
  { value: 'travel', label: 'Travel' },
  { value: 'measurement_issue', label: 'Measurement issue' },
  { value: 'other', label: 'Other' },
];

const mucusOptions: { value: MucusSign; label: string; hint: string }[] = [
  { value: 'not_checked', label: 'Not checked', hint: 'No observation was made; this does not count as dry.' },
  { value: 'dry', label: 'Dry', hint: 'Dry sensation and no visible mucus.' },
  { value: 'sticky', label: 'Sticky', hint: 'Sticky, tacky, or crumbly.' },
  { value: 'creamy', label: 'Creamy', hint: 'Creamy or lotion-like.' },
  { value: 'wet', label: 'Wet', hint: 'Wet or watery sensation.' },
  { value: 'slippery', label: 'Slippery', hint: 'Slippery sensation or clear, stretchy mucus.' },
];

const bleedingOptions: { value: BleedingLevel; label: string }[] = [
  { value: 'none', label: 'None' },
  { value: 'spotting', label: 'Spotting' },
  { value: 'light', label: 'Light' },
  { value: 'medium', label: 'Medium' },
  { value: 'heavy', label: 'Heavy' },
];

export function TodayScreen({
  date,
  settings,
  observation,
  interpretation,
  saving,
  onSave,
  onEditSetup,
}: TodayScreenProps) {
  const [draft, setDraft] = useState<DailyObservation>(
    observation ?? emptyObservation(date, settings),
  );
  const [temperatureText, setTemperatureText] = useState(
    observation?.wakingTemperature?.toString() ?? '',
  );
  const [showDetails, setShowDetails] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const next = observation ?? emptyObservation(date, settings);
    setDraft(next);
    setTemperatureText(next.wakingTemperature?.toString() ?? '');
  }, [date, observation, settings]);

  const save = async (section: 'morning' | 'evening') => {
    const parsed = temperatureText.trim() === '' ? null : Number(temperatureText);
    const minimum = settings.temperatureUnit === 'fahrenheit' ? 80 : 30;
    const maximum = settings.temperatureUnit === 'fahrenheit' ? 110 : 45;
    if (parsed !== null && (!Number.isFinite(parsed) || parsed < minimum || parsed > maximum)) {
      setError(`Enter a realistic ${settings.temperatureUnit === 'fahrenheit' ? 'Fahrenheit' : 'Celsius'} body temperature.`);
      return;
    }
    if (parsed === null && draft.temperatureDisturbances.length) {
      setError('Enter a temperature before adding a disturbance flag.');
      return;
    }
    setError('');
    const next = { ...draft, wakingTemperature: parsed };
    setDraft(next);
    await onSave(next);
    setMessage(section === 'morning' ? 'Morning temperature saved.' : 'Evening signs saved.');
  };

  const toggleDisturbance = (value: TemperatureDisturbance) => {
    setDraft((current) => ({
      ...current,
      temperatureDisturbances: current.temperatureDisturbances.includes(value)
        ? current.temperatureDisturbances.filter((item) => item !== value)
        : [...current.temperatureDisturbances, value],
    }));
  };

  return (
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.headerRow}>
        <View>
          <Text style={styles.date}>{formatDate(date)}</Text>
          <Text style={styles.cycleDay}>Cycle day {interpretation.cycleDay}</Text>
        </View>
        <Pressable accessibilityRole="button" onPress={onEditSetup} style={styles.setupButton}>
          <Text style={styles.setupButtonText}>Setup</Text>
        </Pressable>
      </View>

      <FeedbackCard interpretation={interpretation} />

      <Section title="Morning temperature" subtitle="Take immediately after waking, before getting out of bed.">
        <View style={styles.temperatureRow}>
          <TextInput
            accessibilityLabel="Waking temperature"
            value={temperatureText}
            onChangeText={setTemperatureText}
            keyboardType="decimal-pad"
            placeholder={settings.temperatureUnit === 'fahrenheit' ? '97.60' : '36.45'}
            placeholderTextColor="#879393"
            style={styles.temperatureInput}
          />
          <Text style={styles.unit}>°{settings.temperatureUnit === 'fahrenheit' ? 'F' : 'C'}</Text>
          <TextInput
            accessibilityLabel="Temperature time"
            value={draft.temperatureTime ?? ''}
            onChangeText={(temperatureTime) => setDraft((current) => ({ ...current, temperatureTime }))}
            placeholder="06:30"
            placeholderTextColor="#879393"
            style={styles.timeInput}
          />
        </View>

        <Text style={styles.fieldLabel}>Anything that may affect this reading?</Text>
        <View style={styles.chips}>
          {disturbances.map((item) => (
            <ChoiceChip
              key={item.value}
              label={item.label}
              selected={draft.temperatureDisturbances.includes(item.value)}
              onPress={() => toggleDisturbance(item.value)}
            />
          ))}
        </View>
        <PrimaryButton label={saving ? 'Saving…' : 'Save morning temperature'} disabled={saving} onPress={() => void save('morning')} />
      </Section>

      <Section title="Evening signs" subtitle="Choose the most fertile mucus sign noticed at any point today.">
        <Text style={styles.fieldLabel}>Cervical mucus</Text>
        <View accessibilityRole="radiogroup" style={styles.chips}>
          {mucusOptions.map((item) => (
            <ChoiceChip
              key={item.value}
              label={item.label}
              selected={draft.mucus === item.value}
              onPress={() => setDraft((current) => ({ ...current, mucus: item.value }))}
              accessibilityHint={item.hint}
            />
          ))}
        </View>
        <Text style={styles.helper}>
          “Not checked” means no observation. “Dry” means you checked and observed dryness.
        </Text>

        <Text style={styles.fieldLabel}>Bleeding</Text>
        <View accessibilityRole="radiogroup" style={styles.chips}>
          {bleedingOptions.map((item) => (
            <ChoiceChip
              key={item.value}
              label={item.label}
              selected={draft.bleeding === item.value}
              onPress={() => setDraft((current) => ({ ...current, bleeding: item.value }))}
            />
          ))}
        </View>

        <Pressable onPress={() => setShowDetails((value) => !value)} style={styles.detailsButton}>
          <Text style={styles.detailsButtonText}>{showDetails ? 'Hide details' : 'Add notes'}</Text>
        </Pressable>
        {showDetails ? (
          <TextInput
            accessibilityLabel="Daily notes"
            value={draft.notes}
            onChangeText={(notes) => setDraft((current) => ({ ...current, notes }))}
            placeholder="Optional notes"
            placeholderTextColor="#879393"
            multiline
            maxLength={2000}
            style={styles.notes}
          />
        ) : null}
        <PrimaryButton label={saving ? 'Saving…' : 'Save evening signs'} disabled={saving} onPress={() => void save('evening')} />
      </Section>

      {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
      {message ? <Text accessibilityLiveRegion="polite" style={styles.saved}>{message}</Text> : null}
      <Text style={styles.disclaimer}>
        Educational charting aid—not a diagnosis or a guarantee against pregnancy. Learn your chosen method from a qualified instructor, especially when avoiding pregnancy or during postpartum, hormonal-transition, miscarriage, or perimenopause cycles.
      </Text>
    </ScrollView>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  return (
    <View style={styles.section}>
      <Text style={styles.sectionTitle}>{title}</Text>
      <Text style={styles.sectionSubtitle}>{subtitle}</Text>
      {children}
    </View>
  );
}

function PrimaryButton({
  label,
  disabled,
  onPress,
}: {
  label: string;
  disabled: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [styles.primaryButton, disabled && styles.disabled, pressed && styles.pressed]}
    >
      <Text style={styles.primaryButtonText}>{label}</Text>
    </Pressable>
  );
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { weekday: 'long', month: 'long', day: 'numeric' }).format(
    new Date(`${value}T12:00:00`),
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.md, paddingBottom: spacing.xl, gap: spacing.md },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  date: { color: colors.text, fontSize: 24, fontWeight: '800' },
  cycleDay: { color: colors.muted, fontSize: 15, marginTop: 2 },
  setupButton: { minHeight: 44, justifyContent: 'center', paddingHorizontal: spacing.md },
  setupButtonText: { color: colors.primary, fontSize: 15, fontWeight: '800' },
  section: { backgroundColor: colors.surface, borderRadius: 18, padding: spacing.md, gap: spacing.md },
  sectionTitle: { color: colors.text, fontSize: 20, fontWeight: '800' },
  sectionSubtitle: { color: colors.muted, fontSize: 14, lineHeight: 20, marginTop: -spacing.sm },
  temperatureRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  temperatureInput: {
    flex: 1,
    minHeight: 56,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    paddingHorizontal: spacing.md,
    color: colors.text,
    fontSize: 24,
    fontWeight: '700',
  },
  unit: { color: colors.text, fontSize: 20, fontWeight: '700' },
  timeInput: {
    width: 82,
    minHeight: 56,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    paddingHorizontal: spacing.sm,
    color: colors.text,
    fontSize: 16,
    textAlign: 'center',
  },
  fieldLabel: { color: colors.text, fontSize: 15, fontWeight: '800' },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  helper: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  detailsButton: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
  detailsButtonText: { color: colors.primary, fontSize: 15, fontWeight: '800' },
  notes: {
    minHeight: 96,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 14,
    padding: spacing.md,
    color: colors.text,
    fontSize: 15,
    textAlignVertical: 'top',
  },
  primaryButton: {
    minHeight: 52,
    borderRadius: 14,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: spacing.xs,
  },
  primaryButtonText: { color: '#FFFFFF', fontSize: 16, fontWeight: '800' },
  disabled: { opacity: 0.55 },
  pressed: { opacity: 0.75 },
  error: { color: colors.danger, fontSize: 14, fontWeight: '700' },
  saved: { color: colors.confirmedBorder, fontSize: 14, fontWeight: '700' },
  disclaimer: { color: colors.muted, fontSize: 12, lineHeight: 18, paddingHorizontal: spacing.sm },
});
