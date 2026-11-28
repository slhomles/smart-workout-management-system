/** Điểm vào của module logic tư thế (spec fe-pose-logic §2.2): code và test import từ `@/utils/pose`. */
export { angleDeg } from './angle';
export type { AngleOptions } from './angle';
export { LANDMARK_INDEX, measureJoint, pickSide, toPixelLandmarks } from './landmarks';
export type {
  ExerciseRule,
  FormCheck,
  JointMeasurement,
  JointName,
  JointTriple,
  Landmark,
  Phase,
  Point,
  PoseRulesFile,
  PoseViolation,
  RepEvent,
  RepRule,
  RepSample,
  RepState,
  RepUpdate,
  Severity,
  Side,
  TempoSummary,
} from '@/types/pose';
