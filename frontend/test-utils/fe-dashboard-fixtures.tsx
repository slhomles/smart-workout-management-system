/**
 * Dữ liệu giả và helper dùng chung cho test màn của `fe-dashboard` (spec fe-dashboard §5 "Quy ước chung").
 * Đặt ngoài `__tests__/`: `testMatch` của jest-expo coi MỌI file trong `__tests__/` là bộ test, file không có `it`
 * sẽ làm jest báo lỗi "must contain at least one test" (jest.config.js là file core, không sửa).
 * File test PHẢI tự gọi `jest.mock('@/services/auth')`, `jest.mock('@/services/dashboard')` và mock `expo-router`.
 * Mọi giá trị theo persona seed (demo, other, editor, newbie), không phải người dùng thật.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, render } from '@testing-library/react-native';
import { AxiosError, AxiosHeaders } from 'axios';
import type { ReactElement } from 'react';

import type { ApiErrorDetail } from '@/services/api/errors';
import type { Me } from '@/types/auth';
import type { BodyProfile, Dashboard, MuscleRecoveryStatus, ReportExport, WeightTrend, WeightTrendPoint } from '@/types/dashboard';
import type { Page } from '@/types/page';

// --- /auth/me ---
export const DEMO_ME: Me = {
  id: '5eed0000-0000-4000-8000-000000000003',
  email: 'demo@smartworkout.local',
  status: 'active',
  email_verified_at: '2026-01-05T08:00:00Z',
  display_name: 'An',
  full_name: 'Nguyễn Văn An',
  avatar_media_id: null,
  locale: 'vi-VN',
  timezone: 'Asia/Ho_Chi_Minh',
  unit_system: 'metric',
  roles: ['user'],
  permissions: ['body_metric:manage_own', 'report:export_own', 'workout:manage_own'],
};

export const OTHER_ME: Me = {
  ...DEMO_ME,
  id: '5eed0000-0000-4000-8000-000000000010',
  email: 'other@smartworkout.local',
  display_name: 'Phương',
  full_name: 'Bùi Phương',
  unit_system: 'imperial',
};

export const EDITOR_ME: Me = {
  ...DEMO_ME,
  id: '5eed0000-0000-4000-8000-000000000002',
  email: 'editor@smartworkout.local',
  display_name: 'Biên tập',
  full_name: null,
  roles: ['content_editor'],
  permissions: ['exercise:read', 'exercise:manage', 'media:upload'],
};

export const SESSION_USER = {
  id: DEMO_ME.id,
  email: DEMO_ME.email,
  display_name: DEMO_ME.display_name,
  roles: DEMO_ME.roles,
};

// --- /dashboard ---
export const DASHBOARD_DEMO: Dashboard = {
  date: '2026-11-29',
  timezone: 'Asia/Ho_Chi_Minh',
  latest_metrics: {
    measurement_id: 'm-1',
    measured_at: '2026-11-29T00:00:00Z',
    weight_kg: 70,
    body_fat_pct: 18.4,
    bmi: 23.7,
    bmi_category: 'overweight',
    bmr_kcal: 1665,
    tdee_kcal: 2581,
  },
  active_goal: null,
  today: {
    sessions_completed: 1,
    est_calories_burned_kcal: 320,
    total_volume_kg: 4250,
    duration_minutes: 62.4,
    has_session_in_progress: false,
  },
  this_week: {
    week_start: '2026-11-23',
    planned_count: 3,
    completed_planned_count: 2,
    skipped_count: 1,
    adherence_pct: 66.67,
    sessions_completed: 3,
  },
  is_plateau: false,
};

export const DASHBOARD_NEWBIE: Dashboard = {
  ...DASHBOARD_DEMO,
  latest_metrics: null,
  today: {
    sessions_completed: 0,
    est_calories_burned_kcal: 0,
    total_volume_kg: 0,
    duration_minutes: 0,
    has_session_in_progress: false,
  },
  this_week: {
    week_start: '2026-11-23',
    planned_count: 0,
    completed_planned_count: 0,
    skipped_count: 0,
    adherence_pct: null,
    sessions_completed: 0,
  },
  is_plateau: false,
};

// --- /dashboard/weight-trend ---
const TREND_WEEKS: [string, number][] = [
  ['2026-10-26', 71.5],
  ['2026-11-02', 71.1],
  ['2026-11-09', 70.6],
  ['2026-11-16', 70.3],
  ['2026-11-23', 70],
];

function trendPoint(weekStart: string, weightKg: number | null): WeightTrendPoint {
  return {
    week_start: weekStart,
    avg_weight_kg: weightKg,
    min_weight_kg: weightKg,
    max_weight_kg: weightKg,
    avg_body_fat_pct: null,
    measurement_count: weightKg === null ? 0 : 1,
    change_kg: null,
    is_plateau: false,
    sessions_completed: 0,
    est_calories_burned_kcal: 0,
  };
}

export const TREND_DEMO: WeightTrend = {
  range: 'month',
  from_date: '2026-10-26',
  to_date: '2026-11-29',
  points: TREND_WEEKS.map(([week, kg]) => trendPoint(week, kg)),
  is_plateau: false,
};

export const TREND_NO_WEIGHT: WeightTrend = {
  ...TREND_DEMO,
  points: TREND_WEEKS.map(([week]) => trendPoint(week, null)),
};

export const TREND_EMPTY: WeightTrend = { ...TREND_DEMO, points: [] };

// --- /body/profile ---
export const PROFILE_DEMO: BodyProfile = {
  gender: 'male',
  date_of_birth: '2003-05-10',
  height_cm: 172,
  activity_level_id: 3,
  experience_level_id: 1,
  updated_at: '2026-11-01T00:00:00Z',
};

export const PROFILE_NEWBIE: BodyProfile = {
  gender: 'unspecified',
  date_of_birth: null,
  height_cm: null,
  activity_level_id: null,
  experience_level_id: null,
  updated_at: null,
};

// --- /recovery/muscle-groups ---
type RecoveryInput = Pick<MuscleRecoveryStatus, 'muscle_group_id' | 'muscle_code' | 'muscle_name' | 'recovery_status' | 'recovery_pct'>;

export function recoveryItem(input: RecoveryInput): MuscleRecoveryStatus {
  return {
    ...input,
    heatmap_region_key: input.muscle_code,
    remaining_hours: input.recovery_status === 'ready' ? 0 : 24,
    fatigue_score: null,
    last_trained_at: '2026-11-28T10:00:00Z',
    recovered_at: null,
    last_session_id: null,
    model_version: null,
  };
}

export function page<T>(data: T[], nextCursor: string | null = null): Page<T> {
  return { data, pagination: { next_cursor: nextCursor, has_more: nextCursor !== null } };
}

export const RECOVERY_DEMO: Page<MuscleRecoveryStatus> = page([
  recoveryItem({ muscle_group_id: 1, muscle_code: 'chest', muscle_name: 'Ngực', recovery_status: 'fatigued', recovery_pct: 2 }),
  recoveryItem({ muscle_group_id: 5, muscle_code: 'triceps', muscle_name: 'Tay sau', recovery_status: 'recovering', recovery_pct: 60 }),
  recoveryItem({ muscle_group_id: 4, muscle_code: 'biceps', muscle_name: 'Tay trước', recovery_status: 'ready', recovery_pct: 100 }),
]);

// --- /reports ---
export const REPORT_R1: ReportExport = {
  id: 'r-1',
  report_type: 'weekly_summary',
  period_start: '2026-11-16',
  period_end: '2026-11-23',
  media_id: 'media-r-1',
  image_url: '/api/v1/reports/r-1/image',
  summary: {
    sessions_completed: 3,
    duration_minutes: 185.2,
    total_volume_kg: 12450,
    est_calories_burned_kcal: 900,
    completed_set_count: 45,
    total_reps: 380,
    planned_count: 3,
    completed_planned_count: 2,
    adherence_pct: 66.67,
    avg_weight_kg: 70.3,
    weight_change_kg: -0.3,
  },
  created_at: '2026-11-23T01:00:00Z',
};

// --- Lỗi API (Claude_api_respone.md §3) ---
/** `message` cố ý khác thông điệp màn hiện để chứng minh rẽ nhánh theo `code`, trừ khi test truyền `message`. */
export function apiError(status: number, code: string, details: ApiErrorDetail[] = [], message?: string): AxiosError {
  const config = { headers: new AxiosHeaders() };
  const data = { error: { code, message: message ?? `Thông điệp server (${code})`, details, request_id: 'req-test' } };
  return new AxiosError('fail', 'ERR_BAD_RESPONSE', config, null, { status, statusText: '', headers: {}, config, data });
}

export function networkError(): AxiosError {
  return new AxiosError('Network Error');
}

export function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  let reject: (reason: unknown) => void = () => undefined;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

export function neverResolves<T>(): Promise<T> {
  return new Promise<T>(() => undefined);
}

// --- Render ---
const queryClients: QueryClient[] = [];

/** Bọc `QueryClientProvider` với `retry: false` (spec §5); trả client để test spy `invalidateQueries`. */
export async function renderWithClient(ui: ReactElement): Promise<QueryClient> {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClients.push(client);
  await render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
  return client;
}

/** Gỡ màn rồi xoá cache: nếu không, timer `gcTime` của React Query giữ tiến trình jest không thoát. */
export async function cleanupClients(): Promise<void> {
  await cleanup();
  for (const client of queryClients.splice(0)) client.clear();
}

/** Cho các promise đang chờ chạy xong, để khẳng định "không có lần gọi thêm". */
export async function flushPromises(): Promise<void> {
  await act(async () => {
    await new Promise((done) => setTimeout(done, 0));
  });
}
