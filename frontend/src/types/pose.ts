/**
 * Kiểu của module logic tư thế và đếm rep (spec fe-pose-logic §2.3, §2.4).
 * Field giữ snake_case như `shared/constants/pose-rules.json` và schema backend
 * (`RepEventInput`, `SetTempoSchema` trong `backend/app/schemas/workout.py`).
 */

/** Sáu khớp có ở cả MediaPipe Pose và COCO-17 (spec §6 ý 5). */
export type JointName = 'shoulder' | 'elbow' | 'wrist' | 'hip' | 'knee' | 'ankle';

/** Ba khớp của một góc; góc đo tại phần tử giữa. */
export type JointTriple = [JointName, JointName, JointName];

export type Phase = 'eccentric' | 'bottom' | 'concentric' | 'top';

/** Khớp enum `IssueSeverity` của backend. */
export type Severity = 'info' | 'warning' | 'critical';

export type Side = 'left' | 'right';

export type RepState = 'idle' | 'at_start' | 'moving_out' | 'at_end' | 'moving_back';

/** Landmark MediaPipe: toạ độ chuẩn hoá [0, 1] hoặc pixel sau `toPixelLandmarks`. */
export type Landmark = { x: number; y: number; z?: number; visibility?: number };

export type Point = { x: number; y: number; z?: number };

export type RepRule = {
  joint: JointTriple;
  start: 'extended' | 'flexed';
  first_phase: 'eccentric' | 'concentric';
  extended_deg: number;
  flexed_deg: number;
  partial_deg: number;
  partial_mistake_code: string | null;
};

export type FormCheck = {
  mistake_code: string;
  joint: JointTriple;
  min_deg: number | null;
  max_deg: number | null;
  phases: Phase[];
  severity: Severity;
};

export type ExerciseRule = {
  source: string;
  view: 'side' | 'front';
  rep: RepRule;
  checks: FormCheck[];
};

export type PoseRulesFile = {
  version: 1;
  min_visibility: number;
  exercises: Record<string, ExerciseRule>;
};

export type RepSample = { t_ms: number; angle_deg: number | null };

/** Khớp đúng `RepEventInput` của backend. */
export type RepEvent = {
  rep_no: number;
  start_offset_ms: number;
  eccentric_ms: number;
  pause_bottom_ms: number;
  concentric_ms: number;
  pause_top_ms: number;
  min_joint_angle_deg: number | null;
  max_joint_angle_deg: number | null;
  is_full_rom: boolean;
};

export type RepUpdate = {
  state: RepState;
  phase: Phase | null;
  rep_count: number;
  completed_rep: RepEvent | null;
  partial_mistake_code: string | null;
};

/** Khớp `SetTempoSchema` của backend. */
export type TempoSummary = {
  rep_count: number;
  avg_eccentric_ms: number;
  avg_pause_bottom_ms: number;
  avg_concentric_ms: number;
  avg_pause_top_ms: number;
  time_under_tension_ms: number;
  full_rom_pct: number;
};

export type PoseViolation = {
  mistake_code: string;
  severity: Severity;
  joint: JointTriple;
  side: Side;
  measured_angle_deg: number;
};

/** Kết quả `measureJoint`: góc tại khớp giữa, đo ở bên nhìn rõ hơn. */
export type JointMeasurement = { side: Side; angle_deg: number };
