/**
 * Kiểm luật tư thế theo bảng ngưỡng của bài (spec fe-pose-logic §2.6).
 * Không thấy khớp thì không tính vi phạm; bằng ngưỡng cũng không vi phạm (spec §6 ý 6).
 */
import type { ExerciseRule, FormCheck, Landmark, Phase, PoseViolation } from '@/types/pose';

import { measureJoint } from './landmarks';
import { POSE_RULES } from './rules';

function isOutOfRange(angle: number, check: FormCheck): boolean {
  const isBelowMin = check.min_deg !== null && angle < check.min_deg;
  const isAboveMax = check.max_deg !== null && angle > check.max_deg;
  return isBelowMin || isAboveMax;
}

function evaluateCheck(
  check: FormCheck,
  landmarks: readonly Landmark[],
  phase: Phase,
  minVisibility: number,
): PoseViolation | null {
  if (!check.phases.includes(phase)) return null;
  const measurement = measureJoint(landmarks, check.joint, minVisibility);
  if (measurement === null || !isOutOfRange(measurement.angle_deg, check)) return null;
  const [first, middle, last] = check.joint;
  return {
    mistake_code: check.mistake_code,
    severity: check.severity,
    // Bản sao để bên dùng sửa kết quả không làm đổi luật gốc.
    joint: [first, middle, last],
    side: measurement.side,
    measured_angle_deg: measurement.angle_deg,
  };
}

/** Các vi phạm của khung hình, theo đúng thứ tự `rule.checks`; `phase` null (chưa vào rep) thì không kiểm. */
export function checkPose(
  rule: ExerciseRule,
  landmarks: readonly Landmark[],
  phase: Phase | null,
  minVisibility: number = POSE_RULES.min_visibility,
): PoseViolation[] {
  if (phase === null) return [];
  const violations: PoseViolation[] = [];
  for (const check of rule.checks) {
    const violation = evaluateCheck(check, landmarks, phase, minVisibility);
    if (violation !== null) violations.push(violation);
  }
  return violations;
}
