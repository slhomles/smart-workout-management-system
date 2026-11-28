/**
 * Kiểu dữ liệu tab Báo cáo (spec fe-dashboard §2.3), khớp `backend/app/schemas/dashboard.py`, `body.py`,
 * `recovery.py`, `report.py`. UUID là `string`, ID danh mục là `number` (frontend-standards §3);
 * ngày là chuỗi `yyyy-mm-dd`, thời điểm là chuỗi ISO; đơn vị SI (kg, cm).
 */
import type { UserGoal } from '@/types/profile';

// --- /dashboard ---
export type TrendRange = 'week' | 'month' | '3months';

export type LatestMetrics = {
  measurement_id: string;
  measured_at: string;
  weight_kg: number;
  body_fat_pct: number | null;
  bmi: number | null;
  bmi_category: string | null;
  bmr_kcal: number | null;
  tdee_kcal: number | null;
};

export type TodaySummary = {
  sessions_completed: number;
  est_calories_burned_kcal: number;
  total_volume_kg: number;
  duration_minutes: number;
  has_session_in_progress: boolean;
};

export type WeekProgress = {
  week_start: string;
  planned_count: number;
  completed_planned_count: number;
  skipped_count: number;
  adherence_pct: number | null;
  sessions_completed: number;
};

export type Dashboard = {
  date: string;
  timezone: string;
  latest_metrics: LatestMetrics | null;
  active_goal: UserGoal | null;
  today: TodaySummary;
  this_week: WeekProgress;
  is_plateau: boolean;
};

export type WeightTrendPoint = {
  week_start: string;
  avg_weight_kg: number | null;
  min_weight_kg: number | null;
  max_weight_kg: number | null;
  avg_body_fat_pct: number | null;
  measurement_count: number;
  change_kg: number | null;
  is_plateau: boolean;
  sessions_completed: number;
  est_calories_burned_kcal: number;
};

export type WeightTrend = {
  range: TrendRange;
  from_date: string;
  to_date: string;
  points: WeightTrendPoint[];
  is_plateau: boolean;
};

// --- /body ---
export type Gender = 'male' | 'female' | 'other' | 'unspecified';

export type BodyProfile = {
  gender: Gender;
  date_of_birth: string | null;
  height_cm: number | null;
  activity_level_id: number | null;
  experience_level_id: number | null;
  /** `null` nếu user chưa tạo hồ sơ thể chất. */
  updated_at: string | null;
};

/** PUT phải gửi đủ mọi field, giá trị trống gửi `null` (spec §6 ý 10). */
export type ReplaceBodyProfileRequest = Omit<BodyProfile, 'updated_at'>;

/** Không gửi `measured_at`: server mặc định là hiện tại (spec §6 ý 9). */
export type CreateMeasurementRequest = {
  weight_kg: number;
  body_fat_pct?: number;
};

export type MeasurementSource = 'manual' | 'smart_scale' | 'imported';

export type BodyCircumference = {
  body_site_id: number;
  body_site_code: string;
  body_site_name: string;
  value_cm: number;
};

export type BodyMetrics = {
  age_years: number | null;
  bmi: number | null;
  bmi_category: 'underweight' | 'normal' | 'overweight' | 'obese' | null;
  lean_body_mass_kg: number | null;
  bmr_kcal: number | null;
  bmr_katch_mcardle_kcal: number | null;
  tdee_kcal: number | null;
  activity_level_code: string | null;
};

export type BodyMeasurement = {
  id: string;
  measured_at: string;
  weight_kg: number;
  body_fat_pct: number | null;
  muscle_mass_kg: number | null;
  source: MeasurementSource;
  note: string | null;
  circumferences: BodyCircumference[];
  metrics: BodyMetrics;
  created_at: string;
  updated_at: string;
};

// --- /recovery ---
export type RecoveryStatus = 'fatigued' | 'recovering' | 'ready';

export type MuscleRecoveryStatus = {
  muscle_group_id: number;
  muscle_code: string;
  muscle_name: string;
  heatmap_region_key: string;
  recovery_status: RecoveryStatus;
  recovery_pct: number;
  remaining_hours: number;
  fatigue_score: number | null;
  last_trained_at: string | null;
  recovered_at: string | null;
  last_session_id: string | null;
  model_version: string | null;
};

export type ListMuscleRecoveryParams = {
  limit?: number;
  cursor?: string;
};

// --- /reports ---
export type ReportType = 'weekly_summary' | 'monthly_summary';

export type ReportSummary = {
  sessions_completed: number;
  duration_minutes: number;
  total_volume_kg: number;
  est_calories_burned_kcal: number;
  completed_set_count: number;
  total_reps: number;
  planned_count: number;
  completed_planned_count: number;
  adherence_pct: number | null;
  avg_weight_kg: number | null;
  weight_change_kg: number | null;
};

export type ReportExport = {
  id: string;
  report_type: ReportType;
  period_start: string;
  /** Ngày đầu kỳ kế tiếp (không bao gồm). */
  period_end: string;
  media_id: string;
  /** Đường dẫn API tải ảnh PNG, cần Bearer token. */
  image_url: string;
  summary: ReportSummary;
  created_at: string;
};

export type CreateReportRequest = {
  report_type: ReportType;
  period_start: string;
};

export type ListReportsParams = {
  report_type?: ReportType;
  limit?: number;
  cursor?: string;
};
