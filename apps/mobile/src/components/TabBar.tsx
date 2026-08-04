import { Pressable, StyleSheet, Text, View } from 'react-native';

import { colors, spacing } from '../theme';

export type AppTab = 'today' | 'chart' | 'history';

interface TabBarProps {
  active: AppTab;
  onChange: (tab: AppTab) => void;
}

const tabs: { id: AppTab; label: string }[] = [
  { id: 'today', label: 'Today' },
  { id: 'chart', label: 'Chart' },
  { id: 'history', label: 'History' },
];

export function TabBar({ active, onChange }: TabBarProps) {
  return (
    <View accessibilityRole="tablist" style={styles.bar}>
      {tabs.map((tab) => {
        const selected = active === tab.id;
        return (
          <Pressable
            key={tab.id}
            accessibilityRole="tab"
            accessibilityState={{ selected }}
            onPress={() => onChange(tab.id)}
            style={({ pressed }) => [styles.tab, selected && styles.activeTab, pressed && styles.pressed]}
          >
            <Text style={[styles.label, selected && styles.activeLabel]}>{tab.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: colors.border,
    backgroundColor: colors.surface,
    paddingHorizontal: spacing.sm,
    paddingTop: spacing.sm,
    paddingBottom: spacing.md,
  },
  tab: { flex: 1, minHeight: 46, alignItems: 'center', justifyContent: 'center', borderRadius: 14 },
  activeTab: { backgroundColor: colors.primarySoft },
  pressed: { opacity: 0.7 },
  label: { color: colors.muted, fontSize: 14, fontWeight: '700' },
  activeLabel: { color: colors.primary, fontWeight: '800' },
});
