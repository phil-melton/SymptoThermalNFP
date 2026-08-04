import { Pressable, StyleSheet, Text } from 'react-native';

import { colors, spacing } from '../theme';

interface ChoiceChipProps {
  label: string;
  selected: boolean;
  onPress: () => void;
  accessibilityHint?: string;
}

export function ChoiceChip({
  label,
  selected,
  onPress,
  accessibilityHint,
}: ChoiceChipProps) {
  return (
    <Pressable
      accessibilityRole="radio"
      accessibilityState={{ selected }}
      accessibilityHint={accessibilityHint}
      onPress={onPress}
      style={({ pressed }) => [
        styles.chip,
        selected && styles.selected,
        pressed && styles.pressed,
      ]}
    >
      <Text style={[styles.label, selected && styles.selectedLabel]}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    minHeight: 44,
    borderRadius: 22,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.md,
    paddingVertical: 11,
    justifyContent: 'center',
  },
  selected: {
    borderColor: colors.primary,
    backgroundColor: colors.primarySoft,
    borderWidth: 2,
    paddingHorizontal: spacing.md - 1,
    paddingVertical: 10,
  },
  pressed: { opacity: 0.72 },
  label: { color: colors.text, fontSize: 15, fontWeight: '600' },
  selectedLabel: { color: colors.primary, fontWeight: '800' },
});
