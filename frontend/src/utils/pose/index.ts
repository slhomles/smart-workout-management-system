/** Điểm vào của module logic tư thế (spec fe-pose-logic §2.2): code và test import từ `@/utils/pose`. */
export { angleDeg } from './angle';
export type { AngleOptions } from './angle';
export { LANDMARK_INDEX, measureJoint, pickSide, toPixelLandmarks } from './landmarks';
export {
  AI_RULE_SLUGS,
  canUseAiTrainer,
  getPoseRules,
  hasAiRules,
  POSE_RULES,
  PoseRulesError,
  validatePoseRules,
} from './rules';
export type { AiTrainerCandidate } from './rules';
export { checkPose } from './check';
export { createRepCounter, phaseOf } from './rep-counter';
export type { RepCounter } from './rep-counter';
export { correctFormPct, summarizeTempo } from './tempo';
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
