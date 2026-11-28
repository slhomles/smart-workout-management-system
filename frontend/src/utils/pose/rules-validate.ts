/**
 * Kiểm `shared/constants/pose-rules.json` theo bảng quy tắc của spec fe-pose-logic §2.3.
 * Lỗi dữ liệu ném `PoseRulesError` có `path` chỉ đúng field sai (spec §6 ý 11).
 */
import type { JointName, Phase, PoseRulesFile, Severity } from '@/types/pose';

export class PoseRulesError extends Error {
  readonly path: string;

  constructor(path: string, reason: string) {
    super(`pose-rules.json không hợp lệ tại "${path}": ${reason}`);
    this.name = 'PoseRulesError';
    this.path = path;
    // Babel hạ `class extends Error` có thể làm mất prototype, khiến `instanceof PoseRulesError` sai.
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

type JsonObject = Record<string, unknown>;

// Giống `catalog.exercises.slug` và ràng buộc `ck_exercise_mistakes_code_format` của DB.
const SLUG_PATTERN = /^[a-z0-9]+(-[a-z0-9]+)*$/;
const MISTAKE_CODE_PATTERN = /^[A-Z][A-Z0-9_]*$/;
const JOINT_NAMES: readonly JointName[] = ['shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle'];
const PHASES: readonly Phase[] = ['eccentric', 'bottom', 'concentric', 'top'];
const SEVERITIES: readonly Severity[] = ['info', 'warning', 'critical'];
const VIEWS = ['side', 'front'] as const;
const REP_STARTS = ['extended', 'flexed'] as const;
const FIRST_PHASES = ['eccentric', 'concentric'] as const;
const JOINT_TRIPLE_LENGTH = 3;
const MAX_DEGREE = 180;
const SUPPORTED_VERSION = 1;

function fail(path: string, reason: string): never {
  throw new PoseRulesError(path, reason);
}

function isPlainObject(value: unknown): value is JsonObject {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function expectObject(value: unknown, path: string): JsonObject {
  if (!isPlainObject(value)) fail(path, 'phải là object');
  return value;
}

function isOneOf(value: unknown, options: readonly string[]): boolean {
  return typeof value === 'string' && options.includes(value);
}

function expectOneOf(value: unknown, options: readonly string[], path: string): void {
  if (!isOneOf(value, options)) fail(path, `phải là một trong ${options.join(', ')}`);
}

function isDegree(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 && value <= MAX_DEGREE;
}

function expectDegree(value: unknown, path: string): number {
  if (!isDegree(value)) fail(path, `phải là số hữu hạn trong [0, ${MAX_DEGREE}]`);
  return value;
}

function expectDegreeOrNull(value: unknown, path: string): number | null {
  return value === null ? null : expectDegree(value, path);
}

function expectJoint(value: unknown, path: string): void {
  const isTriple = Array.isArray(value) && value.length === JOINT_TRIPLE_LENGTH;
  if (!isTriple || !value.every((name) => isOneOf(name, JOINT_NAMES))) {
    fail(path, `phải là mảng ${JOINT_TRIPLE_LENGTH} khớp thuộc ${JOINT_NAMES.join(', ')}`);
  }
}

function expectMistakeCode(value: unknown, path: string): void {
  if (typeof value !== 'string' || !MISTAKE_CODE_PATTERN.test(value)) {
    fail(path, `phải là chuỗi khớp ${MISTAKE_CODE_PATTERN.source}`);
  }
}

function validateRepThresholds(rep: JsonObject, path: string): void {
  const extended = expectDegree(rep.extended_deg, `${path}.extended_deg`);
  const flexed = expectDegree(rep.flexed_deg, `${path}.flexed_deg`);
  const partial = expectDegree(rep.partial_deg, `${path}.partial_deg`);
  if (flexed >= extended) fail(`${path}.flexed_deg`, 'phải nhỏ hơn extended_deg');
  if (partial <= flexed || partial >= extended) {
    fail(`${path}.partial_deg`, 'phải nằm giữa flexed_deg và extended_deg');
  }
}

function validateRep(value: unknown, path: string): void {
  const rep = expectObject(value, path);
  expectJoint(rep.joint, `${path}.joint`);
  expectOneOf(rep.start, REP_STARTS, `${path}.start`);
  expectOneOf(rep.first_phase, FIRST_PHASES, `${path}.first_phase`);
  validateRepThresholds(rep, path);
  if (rep.partial_mistake_code !== null) expectMistakeCode(rep.partial_mistake_code, `${path}.partial_mistake_code`);
}

function validateBounds(check: JsonObject, path: string): void {
  const min = expectDegreeOrNull(check.min_deg, `${path}.min_deg`);
  const max = expectDegreeOrNull(check.max_deg, `${path}.max_deg`);
  if (min === null && max === null) fail(path, 'min_deg và max_deg không được cùng null');
  if (min !== null && max !== null && min > max) fail(`${path}.min_deg`, 'không được lớn hơn max_deg');
}

function validatePhases(value: unknown, path: string): void {
  const isNonEmpty = Array.isArray(value) && value.length > 0;
  if (!isNonEmpty || !value.every((phase) => isOneOf(phase, PHASES))) {
    fail(path, `phải là mảng không rỗng thuộc ${PHASES.join(', ')}`);
  }
}

function validateCheck(value: unknown, path: string): void {
  const check = expectObject(value, path);
  expectJoint(check.joint, `${path}.joint`);
  expectMistakeCode(check.mistake_code, `${path}.mistake_code`);
  validateBounds(check, path);
  validatePhases(check.phases, `${path}.phases`);
  expectOneOf(check.severity, SEVERITIES, `${path}.severity`);
}

function validateChecks(value: unknown, path: string): void {
  if (!Array.isArray(value)) fail(path, 'phải là mảng');
  value.forEach((check: unknown, index) => validateCheck(check, `${path}.${index}`));
}

function validateExercise(slug: string, value: unknown): void {
  const path = `exercises.${slug}`;
  if (!SLUG_PATTERN.test(slug)) fail(path, `slug phải khớp ${SLUG_PATTERN.source}`);
  const exercise = expectObject(value, path);
  if (typeof exercise.source !== 'string' || exercise.source.trim() === '') {
    fail(`${path}.source`, 'phải là chuỗi ghi nguồn, không rỗng');
  }
  expectOneOf(exercise.view, VIEWS, `${path}.view`);
  validateRep(exercise.rep, `${path}.rep`);
  validateChecks(exercise.checks, `${path}.checks`);
}

function assertPoseRulesFile(raw: unknown): asserts raw is PoseRulesFile {
  const root = expectObject(raw, '');
  if (root.version !== SUPPORTED_VERSION) fail('version', `phải là ${SUPPORTED_VERSION}`);
  const minVisibility = root.min_visibility;
  const isVisibilityValid = typeof minVisibility === 'number' && minVisibility > 0 && minVisibility <= 1;
  if (!isVisibilityValid) fail('min_visibility', 'phải là số trong (0, 1]');
  const exercises = expectObject(root.exercises, 'exercises');
  for (const [slug, exercise] of Object.entries(exercises)) validateExercise(slug, exercise);
}

/** Kiểm dữ liệu luật và trả về chính `raw` với kiểu `PoseRulesFile` (không sao chép, không biến đổi). */
export function validatePoseRules(raw: unknown): PoseRulesFile {
  assertPoseRulesFile(raw);
  return raw;
}
