import type { SQLiteDatabase } from 'expo-sqlite';

import {
  DEFAULT_SETTINGS,
  type AppSettings,
  type DailyObservation,
} from './types';

export async function migrateDatabase(db: SQLiteDatabase): Promise<void> {
  await db.execAsync(`
    PRAGMA journal_mode = WAL;
    CREATE TABLE IF NOT EXISTS app_settings (
      setting_key TEXT PRIMARY KEY NOT NULL,
      payload_json TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS observations (
      observation_date TEXT PRIMARY KEY NOT NULL,
      payload_json TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_observations_date
      ON observations(observation_date);
  `);
}

export async function loadSettings(db: SQLiteDatabase): Promise<AppSettings> {
  const row = await db.getFirstAsync<{ payload_json: string }>(
    `SELECT payload_json FROM app_settings WHERE setting_key = ?`,
    'primary',
  );
  if (!row) {
    return { ...DEFAULT_SETTINGS };
  }
  try {
    return { ...DEFAULT_SETTINGS, ...(JSON.parse(row.payload_json) as AppSettings) };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export async function saveSettings(
  db: SQLiteDatabase,
  settings: AppSettings,
): Promise<void> {
  await db.runAsync(
    `INSERT INTO app_settings(setting_key, payload_json, updated_at)
     VALUES (?, ?, ?)
     ON CONFLICT(setting_key) DO UPDATE SET
       payload_json = excluded.payload_json,
       updated_at = excluded.updated_at`,
    'primary',
    JSON.stringify(settings),
    new Date().toISOString(),
  );
}

export async function listObservations(
  db: SQLiteDatabase,
): Promise<DailyObservation[]> {
  const rows = await db.getAllAsync<{ payload_json: string }>(
    `SELECT payload_json FROM observations ORDER BY observation_date`,
  );
  const observations: DailyObservation[] = [];
  for (const row of rows) {
    try {
      observations.push(JSON.parse(row.payload_json) as DailyObservation);
    } catch {
      // Ignore a corrupt row; do not let one record block all chart access.
    }
  }
  return observations;
}

export async function saveObservation(
  db: SQLiteDatabase,
  observation: DailyObservation,
): Promise<void> {
  await db.runAsync(
    `INSERT INTO observations(observation_date, payload_json, updated_at)
     VALUES (?, ?, ?)
     ON CONFLICT(observation_date) DO UPDATE SET
       payload_json = excluded.payload_json,
       updated_at = excluded.updated_at`,
    observation.date,
    JSON.stringify(observation),
    new Date().toISOString(),
  );
}
