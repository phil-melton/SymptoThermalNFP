import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { ChoiceChip } from '../components/ChoiceChip';
import { colors, spacing } from '../theme';
import type { AppSettings, RuleContext, TrackingGoal } from '../types';

interface OnboardingScreenProps {
  initial: AppSettings;
  onComplete: (settings: AppSettings) => Promise<void>;
}

const goals: { value: TrackingGoal; label: string; description: string }[] = [
  { value: 'avoid_pregnancy', label: 'Avoid pregnancy', description: 'Conservative fertile-day coaching.' },
  { value: 'achieve_pregnancy', label: 'Achieve pregnancy', description: 'Highlights possible fertile days.' },
  { value: 'understand_cycle', label: 'Understand my cycle', description: 'Neutral charting guidance.' },
];

const contexts: { value: RuleContext; label: string }[] = [
  { value: 'standard', label: 'Standard cycles' },
  { value: 'postpartum', label: 'Postpartum / breastfeeding' },
  { value: 'post_hormonal', label: 'Recently stopped hormones' },
  { value: 'post_miscarriage', label: 'After miscarriage' },
  { value: 'perimenopause', label: 'Perimenopause' },
];

export function OnboardingScreen({ initial, onComplete }: OnboardingScreenProps) {
  const [settings, setSettings] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const continueSetup = async () => {
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(settings.defaultWakeTime)) {
      setError('Wake time must use 24-hour HH:MM format.');
      return;
    }
    setError('');
    setSaving(true);
    try {
      await onComplete({ ...settings, onboardingComplete: true });
    } finally {
      setSaving(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text style={styles.eyebrow}>PRIVATE · ON DEVICE</Text>
      <Text style={styles.title}>Set up your chart</Text>
      <Text style={styles.intro}>Three choices tailor entry defaults and coaching. They do not change your underlying observations.</Text>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>What is your goal?</Text>
        {goals.map((item) => (
          <Pressable
            key={item.value}
            accessibilityRole="radio"
            accessibilityState={{ selected: settings.trackingGoal === item.value }}
            onPress={() => setSettings((current) => ({ ...current, trackingGoal: item.value }))}
            style={[
              styles.goalCard,
              settings.trackingGoal === item.value && styles.goalCardSelected,
            ]}
          >
            <Text style={styles.goalLabel}>{item.label}</Text>
            <Text style={styles.goalDescription}>{item.description}</Text>
          </Pressable>
        ))}
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Temperature</Text>
        <Text style={styles.label}>Unit</Text>
        <View style={styles.row}>
          <ChoiceChip
            label="Fahrenheit"
            selected={settings.temperatureUnit === 'fahrenheit'}
            onPress={() => setSettings((current) => ({ ...current, temperatureUnit: 'fahrenheit' }))}
          />
          <ChoiceChip
            label="Celsius"
            selected={settings.temperatureUnit === 'celsius'}
            onPress={() => setSettings((current) => ({ ...current, temperatureUnit: 'celsius' }))}
          />
        </View>
        <Text style={styles.label}>Usual wake time</Text>
        <TextInput
          accessibilityLabel="Usual wake time"
          value={settings.defaultWakeTime}
          onChangeText={(defaultWakeTime) => setSettings((current) => ({ ...current, defaultWakeTime }))}
          placeholder="06:30"
          style={styles.input}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Cycle context</Text>
        <Text style={styles.helper}>Special contexts need method-specific instruction. The app will avoid pre-ovulatory lower-probability claims.</Text>
        <View style={styles.row}>
          {contexts.map((item) => (
            <ChoiceChip
              key={item.value}
              label={item.label}
              selected={settings.ruleContext === item.value}
              onPress={() => setSettings((current) => ({ ...current, ruleContext: item.value }))}
            />
          ))}
        </View>
      </View>

      <View style={styles.safetyCard}>
        <Text style={styles.safetyTitle}>Before relying on fertility feedback</Text>
        <Text style={styles.safetyText}>
          This is an educational charting aid, not medical advice, a diagnosis, contraception, or a guarantee against pregnancy. Learn your chosen symptothermal method from a qualified instructor. BBT confirms a shift after it occurs; it does not predict ovulation by itself.
        </Text>
      </View>

      {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
      <Pressable
        accessibilityRole="button"
        disabled={saving}
        onPress={() => void continueSetup()}
        style={({ pressed }) => [styles.button, saving && styles.disabled, pressed && styles.pressed]}
      >
        <Text style={styles.buttonText}>{saving ? 'Saving…' : 'Continue to today'}</Text>
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  content: { padding: spacing.lg, paddingTop: 56, paddingBottom: 48, gap: spacing.lg, backgroundColor: colors.background },
  eyebrow: { color: colors.primary, fontSize: 12, fontWeight: '800', letterSpacing: 1.2 },
  title: { color: colors.text, fontSize: 34, lineHeight: 39, fontWeight: '900' },
  intro: { color: colors.muted, fontSize: 16, lineHeight: 23, marginTop: -spacing.md },
  section: { backgroundColor: colors.surface, borderRadius: 18, padding: spacing.md, gap: spacing.md },
  sectionTitle: { color: colors.text, fontSize: 20, fontWeight: '800' },
  goalCard: { borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: spacing.md, gap: spacing.xs },
  goalCardSelected: { borderWidth: 2, borderColor: colors.primary, backgroundColor: colors.primarySoft, padding: spacing.md - 1 },
  goalLabel: { color: colors.text, fontSize: 16, fontWeight: '800' },
  goalDescription: { color: colors.muted, fontSize: 14 },
  label: { color: colors.text, fontSize: 14, fontWeight: '800' },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  input: { minHeight: 52, borderWidth: 1, borderColor: colors.border, borderRadius: 14, paddingHorizontal: spacing.md, color: colors.text, fontSize: 17 },
  helper: { color: colors.muted, fontSize: 14, lineHeight: 20 },
  safetyCard: { borderLeftWidth: 4, borderLeftColor: colors.possibleBorder, backgroundColor: colors.possible, padding: spacing.md, gap: spacing.sm },
  safetyTitle: { color: colors.text, fontSize: 16, fontWeight: '800' },
  safetyText: { color: colors.text, fontSize: 14, lineHeight: 21 },
  error: { color: colors.danger, fontSize: 14, fontWeight: '700' },
  button: { minHeight: 56, borderRadius: 16, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' },
  buttonText: { color: '#FFFFFF', fontSize: 17, fontWeight: '800' },
  disabled: { opacity: 0.55 },
  pressed: { opacity: 0.75 },
});
