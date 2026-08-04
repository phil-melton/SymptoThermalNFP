import { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, SafeAreaView, StyleSheet, Text, View } from 'react-native';
import { SQLiteProvider, useSQLiteContext } from 'expo-sqlite';

import { TabBar, type AppTab } from './src/components/TabBar';
import {
  listObservations,
  loadSettings,
  migrateDatabase,
  saveObservation,
  saveSettings,
} from './src/database';
import { evaluateObservations } from './src/domain';
import { ChartScreen } from './src/screens/ChartScreen';
import { HistoryScreen } from './src/screens/HistoryScreen';
import { OnboardingScreen } from './src/screens/OnboardingScreen';
import { TodayScreen } from './src/screens/TodayScreen';
import { colors } from './src/theme';
import {
  DEFAULT_SETTINGS,
  emptyObservation,
  type AppSettings,
  type DailyObservation,
} from './src/types';

export default function App() {
  return (
    <SQLiteProvider databaseName="symptothermal.db" onInit={migrateDatabase}>
      <AppShell />
    </SQLiteProvider>
  );
}

function AppShell() {
  const db = useSQLiteContext();
  const [settings, setSettingsState] = useState<AppSettings>(DEFAULT_SETTINGS);
  const [observations, setObservations] = useState<DailyObservation[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showSetup, setShowSetup] = useState(false);
  const [activeTab, setActiveTab] = useState<AppTab>('today');
  const [selectedCycle, setSelectedCycle] = useState(0);
  const today = localDateId(new Date());

  useEffect(() => {
    let active = true;
    Promise.all([loadSettings(db), listObservations(db)])
      .then(([storedSettings, storedObservations]) => {
        if (!active) return;
        setSettingsState(storedSettings);
        setObservations(storedObservations);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [db]);

  const todayObservation = observations.find((item) => item.date === today) ?? null;
  const observationsWithToday = useMemo(() => {
    if (todayObservation) return observations;
    return [...observations, emptyObservation(today, settings)].sort((a, b) => a.date.localeCompare(b.date));
  }, [observations, settings, today, todayObservation]);
  const previewCycles = useMemo(
    () => evaluateObservations(observationsWithToday, settings),
    [observationsWithToday, settings],
  );
  const savedCycles = useMemo(
    () => evaluateObservations(observations, settings),
    [observations, settings],
  );
  const todayCycle = previewCycles.find((cycle) =>
    cycle.days.some((day) => day.date === today),
  ) ?? previewCycles.at(-1);
  const todayInterpretation = todayCycle?.days.find((day) => day.date === today);

  useEffect(() => {
    if (savedCycles.length && selectedCycle >= savedCycles.length) {
      setSelectedCycle(savedCycles.length - 1);
    }
  }, [savedCycles.length, selectedCycle]);

  const persistSettings = useCallback(async (next: AppSettings) => {
    await saveSettings(db, next);
    setSettingsState(next);
    setShowSetup(false);
  }, [db]);

  const persistObservation = useCallback(async (observation: DailyObservation) => {
    setSaving(true);
    try {
      await saveObservation(db, observation);
      setObservations((current) =>
        [...current.filter((item) => item.date !== observation.date), observation].sort((a, b) =>
          a.date.localeCompare(b.date),
        ),
      );
    } finally {
      setSaving(false);
    }
  }, [db]);

  const openCycle = (index: number) => {
    setSelectedCycle(index);
    setActiveTab('chart');
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.loading}>
        <ActivityIndicator color={colors.primary} size="large" />
        <Text style={styles.loadingText}>Opening your private chart…</Text>
      </SafeAreaView>
    );
  }

  if (!settings.onboardingComplete || showSetup) {
    return (
      <SafeAreaView style={styles.safeArea}>
        <OnboardingScreen initial={settings} onComplete={persistSettings} />
      </SafeAreaView>
    );
  }

  if (!todayInterpretation) {
    return (
      <SafeAreaView style={styles.loading}>
        <Text style={styles.loadingText}>Unable to prepare today’s chart.</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <View style={styles.screen}>
        {activeTab === 'today' ? (
          <TodayScreen
            date={today}
            settings={settings}
            observation={todayObservation}
            interpretation={todayInterpretation}
            saving={saving}
            onSave={persistObservation}
            onEditSetup={() => setShowSetup(true)}
          />
        ) : null}
        {activeTab === 'chart' ? (
          <ChartScreen cycles={savedCycles} selectedIndex={selectedCycle} onSelect={setSelectedCycle} />
        ) : null}
        {activeTab === 'history' ? (
          <HistoryScreen cycles={savedCycles} onOpenCycle={openCycle} />
        ) : null}
      </View>
      <TabBar active={activeTab} onChange={setActiveTab} />
    </SafeAreaView>
  );
}

function localDateId(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

const styles = StyleSheet.create({
  safeArea: { flex: 1, backgroundColor: colors.background },
  screen: { flex: 1 },
  loading: {
    flex: 1,
    backgroundColor: colors.background,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 16,
    padding: 24,
  },
  loadingText: { color: colors.muted, fontSize: 15, textAlign: 'center' },
});
