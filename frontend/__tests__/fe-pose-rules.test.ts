import {
  AI_RULE_SLUGS,
  canUseAiTrainer,
  getPoseRules,
  hasAiRules,
  POSE_RULES,
  PoseRulesError,
  validatePoseRules,
  type JointTriple,
  type Phase,
  type PoseRulesFile,
  type Severity,
} from '@/utils/pose';

// Bảng kỳ vọng chép từ spec fe-pose-logic §2.3 ("Nội dung bắt buộc của file thật"), không suy ra từ code.
type ExpectedCheck = {
  mistake_code: string;
  joint: JointTriple;
  min_deg: 'number' | null;
  max_deg: 'number' | null;
  phases: Phase[];
  severity: Severity;
};

type ExpectedRule = {
  view: 'side' | 'front';
  joint: JointTriple;
  start: 'extended' | 'flexed';
  first_phase: 'eccentric' | 'concentric';
  partial_mistake_code: string | null;
  checks: ExpectedCheck[];
};

const ALL_PHASES: Phase[] = ['eccentric', 'bottom', 'concentric', 'top'];

const EXPECTED_RULES: Record<string, ExpectedRule> = {
  'barbell-back-squat': {
    view: 'side',
    joint: ['hip', 'knee', 'ankle'],
    start: 'extended',
    first_phase: 'eccentric',
    partial_mistake_code: 'SQUAT_SHALLOW_DEPTH',
    checks: [
      {
        mistake_code: 'SQUAT_BACK_ROUNDING',
        joint: ['shoulder', 'hip', 'knee'],
        min_deg: 'number',
        max_deg: null,
        phases: ['eccentric', 'bottom', 'concentric'],
        severity: 'critical',
      },
    ],
  },
  'conventional-deadlift': {
    view: 'side',
    joint: ['shoulder', 'hip', 'knee'],
    start: 'flexed',
    first_phase: 'concentric',
    partial_mistake_code: null,
    checks: [],
  },
  'push-up': {
    view: 'side',
    joint: ['shoulder', 'elbow', 'wrist'],
    start: 'extended',
    first_phase: 'eccentric',
    partial_mistake_code: 'PUSHUP_PARTIAL_ROM',
    checks: [
      {
        mistake_code: 'PUSHUP_HIP_SAG',
        joint: ['shoulder', 'hip', 'ankle'],
        min_deg: 'number',
        max_deg: null,
        phases: ALL_PHASES,
        severity: 'warning',
      },
    ],
  },
  'barbell-curl': {
    view: 'side',
    joint: ['shoulder', 'elbow', 'wrist'],
    start: 'extended',
    first_phase: 'concentric',
    partial_mistake_code: null,
    checks: [
      {
        mistake_code: 'CURL_ELBOW_DRIFT',
        joint: ['hip', 'shoulder', 'elbow'],
        min_deg: null,
        max_deg: 'number',
        phases: ['concentric', 'top', 'eccentric'],
        severity: 'warning',
      },
      {
        mistake_code: 'CURL_BODY_SWING',
        joint: ['shoulder', 'hip', 'knee'],
        min_deg: 'number',
        max_deg: null,
        phases: ALL_PHASES,
        severity: 'warning',
      },
    ],
  },
  'overhead-press': {
    view: 'side',
    joint: ['shoulder', 'elbow', 'wrist'],
    start: 'flexed',
    first_phase: 'concentric',
    partial_mistake_code: null,
    checks: [
      {
        mistake_code: 'OHP_LUMBAR_ARCH',
        joint: ['shoulder', 'hip', 'knee'],
        min_deg: 'number',
        max_deg: null,
        phases: ['concentric', 'top', 'eccentric'],
        severity: 'warning',
      },
    ],
  },
  'walking-lunge': {
    view: 'side',
    joint: ['hip', 'knee', 'ankle'],
    start: 'extended',
    first_phase: 'eccentric',
    partial_mistake_code: null,
    checks: [],
  },
};

// Mã lỗi trong seed `03_exercises.sql`, `04_exercises_more.sql` (catalog.exercise_mistakes) của từng bài.
const SEED_MISTAKE_CODES: Record<string, string[]> = {
  'barbell-back-squat': ['SQUAT_BACK_ROUNDING', 'SQUAT_KNEE_VALGUS', 'SQUAT_HEEL_LIFT', 'SQUAT_SHALLOW_DEPTH'],
  'conventional-deadlift': ['DEADLIFT_BACK_ROUNDING', 'DEADLIFT_BAR_DRIFT', 'DEADLIFT_HIPS_RISE_FIRST'],
  'push-up': ['PUSHUP_HIP_SAG', 'PUSHUP_PARTIAL_ROM'],
  'barbell-curl': ['CURL_ELBOW_DRIFT', 'CURL_BODY_SWING'],
  'overhead-press': ['OHP_LUMBAR_ARCH', 'OHP_BAR_FORWARD'],
  'walking-lunge': ['LUNGE_KNEE_VALGUS'],
};

const SIX_SLUGS = [
  'barbell-back-squat',
  'barbell-curl',
  'conventional-deadlift',
  'overhead-press',
  'push-up',
  'walking-lunge',
];

function expectDegreeBound(value: number | null, expected: 'number' | null): void {
  if (expected === null) {
    expect(value).toBeNull();
    return;
  }
  expect(typeof value).toBe('number');
  expect(value).toBeGreaterThanOrEqual(0);
  expect(value).toBeLessThanOrEqual(180);
}

describe('POSE_RULES đọc từ shared/constants/pose-rules.json (spec fe-pose-logic §2.3)', () => {
  // Spec §5 POSE-04 yêu cầu test đọc JSON bằng `require` để so với dữ liệu module đã nạp.
  const raw: unknown = require('../../shared/constants/pose-rules.json');

  it('POSE-04 file thật hợp lệ và POSE_RULES chính là dữ liệu đó (một nguồn)', () => {
    expect(() => validatePoseRules(raw)).not.toThrow();
    expect(validatePoseRules(raw)).toEqual(raw);
    expect(POSE_RULES).toEqual(raw);
    expect(POSE_RULES.version).toBe(1);
    expect(POSE_RULES.min_visibility).toBeGreaterThan(0);
    expect(POSE_RULES.min_visibility).toBeLessThanOrEqual(1);
    expect(Object.keys(POSE_RULES.exercises).sort()).toEqual(SIX_SLUGS);
  });

  it.each(Object.keys(EXPECTED_RULES))('POSE-04 cấu trúc bài %s đúng bảng mục 2.3', (slug) => {
    const expected = EXPECTED_RULES[slug];
    const rule = POSE_RULES.exercises[slug];
    if (expected === undefined || rule === undefined) throw new Error(`thiếu bài ${slug}`);
    expect(rule.source.trim().length).toBeGreaterThan(0);
    expect(rule.view).toBe(expected.view);
    expect(rule.rep.joint).toEqual(expected.joint);
    expect(rule.rep.start).toBe(expected.start);
    expect(rule.rep.first_phase).toBe(expected.first_phase);
    expect(rule.rep.partial_mistake_code).toBe(expected.partial_mistake_code);
    expect(rule.checks).toHaveLength(expected.checks.length);
    rule.checks.forEach((check, index) => {
      const want = expected.checks[index];
      if (want === undefined) throw new Error(`thừa check ${index} ở ${slug}`);
      expect(check.mistake_code).toBe(want.mistake_code);
      expect(check.joint).toEqual(want.joint);
      expect(check.phases).toEqual(want.phases);
      expect(check.severity).toBe(want.severity);
      expectDegreeBound(check.min_deg, want.min_deg);
      expectDegreeBound(check.max_deg, want.max_deg);
    });
  });

  it.each(Object.keys(EXPECTED_RULES))('POSE-04 ngưỡng rep của %s là số trong [0, 180] theo thứ tự', (slug) => {
    const rule = POSE_RULES.exercises[slug];
    if (rule === undefined) throw new Error(`thiếu bài ${slug}`);
    const { flexed_deg: flexed, partial_deg: partial, extended_deg: extended } = rule.rep;
    for (const value of [flexed, partial, extended]) {
      expect(Number.isFinite(value)).toBe(true);
      expect(value).toBeGreaterThanOrEqual(0);
      expect(value).toBeLessThanOrEqual(180);
    }
    expect(flexed).toBeLessThan(partial);
    expect(partial).toBeLessThan(extended);
  });

  it.each(Object.keys(EXPECTED_RULES))('POSE-04 mọi mã lỗi của %s có trong seed của đúng bài đó', (slug) => {
    const rule = POSE_RULES.exercises[slug];
    const seedCodes = SEED_MISTAKE_CODES[slug];
    if (rule === undefined || seedCodes === undefined) throw new Error(`thiếu bài ${slug}`);
    const codes = rule.checks.map((check) => check.mistake_code);
    if (rule.rep.partial_mistake_code !== null) codes.push(rule.rep.partial_mistake_code);
    for (const code of codes) {
      expect(seedCodes).toContain(code);
    }
  });
});

// Fixture hợp lệ chỉ có `push-up` (spec §5 POSE-05); số ngưỡng ở đây chỉ là dữ liệu test.
const VALID_FIXTURE: PoseRulesFile = {
  version: 1,
  min_visibility: 0.5,
  exercises: {
    'push-up': {
      source: 'dữ liệu test',
      view: 'side',
      rep: {
        joint: ['shoulder', 'elbow', 'wrist'],
        start: 'extended',
        first_phase: 'eccentric',
        extended_deg: 160,
        flexed_deg: 90,
        partial_deg: 120,
        partial_mistake_code: 'PUSHUP_PARTIAL_ROM',
      },
      checks: [
        {
          mistake_code: 'PUSHUP_HIP_SAG',
          joint: ['shoulder', 'hip', 'ankle'],
          min_deg: 160,
          max_deg: null,
          phases: ['eccentric', 'bottom', 'concentric', 'top'],
          severity: 'warning',
        },
      ],
    },
  },
};

type MutableRule = { source: unknown; view: unknown; rep: Record<string, unknown>; checks: unknown };
type MutableFile = { version: unknown; min_visibility: unknown; exercises: Record<string, unknown> };

function cloneFixture(): MutableFile {
  // Bản sao sâu cho từng ca để các ca không ảnh hưởng nhau.
  return JSON.parse(JSON.stringify(VALID_FIXTURE)) as MutableFile;
}

function pushUp(file: MutableFile): MutableRule {
  const rule = file.exercises['push-up'];
  if (rule === undefined) throw new Error('fixture thiếu push-up');
  return rule as MutableRule;
}

function firstCheck(file: MutableFile): Record<string, unknown> {
  const checks = pushUp(file).checks as Record<string, unknown>[];
  const check = checks[0];
  if (check === undefined) throw new Error('fixture thiếu checks[0]');
  return check;
}

type InvalidCase = { label: string; path: string; build: (file: MutableFile) => unknown };

const EX = 'exercises.push-up';

// Thứ tự và `path` chép từ spec §5 POSE-05.
const INVALID_CASES: InvalidCase[] = [
  { label: 'gốc null', path: '', build: () => null },
  { label: 'gốc là mảng', path: '', build: () => [] },
  { label: 'version 2', path: 'version', build: (f) => ({ ...f, version: 2 }) },
  { label: 'min_visibility 0', path: 'min_visibility', build: (f) => ({ ...f, min_visibility: 0 }) },
  { label: 'min_visibility 1.5', path: 'min_visibility', build: (f) => ({ ...f, min_visibility: 1.5 }) },
  {
    label: 'slug "Push Up"',
    path: 'exercises.Push Up',
    build: (f) => ({ ...f, exercises: { 'Push Up': f.exercises['push-up'] } }),
  },
  { label: 'source chỉ có dấu cách', path: `${EX}.source`, build: (f) => ((pushUp(f).source = '  '), f) },
  { label: 'view "top"', path: `${EX}.view`, build: (f) => ((pushUp(f).view = 'top'), f) },
  {
    label: 'rep.joint có "hand"',
    path: `${EX}.rep.joint`,
    build: (f) => ((pushUp(f).rep.joint = ['shoulder', 'hand', 'wrist']), f),
  },
  {
    label: 'rep.joint dài 2',
    path: `${EX}.rep.joint`,
    build: (f) => ((pushUp(f).rep.joint = ['shoulder', 'elbow']), f),
  },
  { label: 'flexed_deg = extended_deg', path: `${EX}.rep.flexed_deg`, build: (f) => ((pushUp(f).rep.flexed_deg = 160), f) },
  { label: 'partial_deg = flexed_deg', path: `${EX}.rep.partial_deg`, build: (f) => ((pushUp(f).rep.partial_deg = 90), f) },
  { label: 'extended_deg 181', path: `${EX}.rep.extended_deg`, build: (f) => ((pushUp(f).rep.extended_deg = 181), f) },
  { label: 'start "middle"', path: `${EX}.rep.start`, build: (f) => ((pushUp(f).rep.start = 'middle'), f) },
  { label: 'first_phase "hold"', path: `${EX}.rep.first_phase`, build: (f) => ((pushUp(f).rep.first_phase = 'hold'), f) },
  {
    label: 'partial_mistake_code chữ thường',
    path: `${EX}.rep.partial_mistake_code`,
    build: (f) => ((pushUp(f).rep.partial_mistake_code = 'pushup_partial'), f),
  },
  {
    label: 'checks[0] có min_deg và max_deg cùng null',
    path: `${EX}.checks.0`,
    build: (f) => {
      Object.assign(firstCheck(f), { min_deg: null, max_deg: null });
      return f;
    },
  },
  {
    label: 'checks[0] có min_deg 120 > max_deg 90',
    path: `${EX}.checks.0.min_deg`,
    build: (f) => {
      Object.assign(firstCheck(f), { min_deg: 120, max_deg: 90 });
      return f;
    },
  },
  { label: 'checks[0].phases rỗng', path: `${EX}.checks.0.phases`, build: (f) => ((firstCheck(f).phases = []), f) },
  {
    label: 'checks[0].phases có "hold"',
    path: `${EX}.checks.0.phases`,
    build: (f) => ((firstCheck(f).phases = ['hold']), f),
  },
  {
    label: 'checks[0].severity "error"',
    path: `${EX}.checks.0.severity`,
    build: (f) => ((firstCheck(f).severity = 'error'), f),
  },
];

// Các ca biên khác của bảng quy tắc mục 2.3 (ngoài danh sách bắt buộc của POSE-05).
const EXTRA_INVALID_CASES: InvalidCase[] = [
  { label: 'min_visibility là chuỗi', path: 'min_visibility', build: (f) => ({ ...f, min_visibility: '0.5' }) },
  { label: 'exercises là mảng', path: 'exercises', build: (f) => ({ ...f, exercises: [] }) },
  { label: 'bài không phải object', path: EX, build: (f) => ({ ...f, exercises: { 'push-up': 1 } }) },
  { label: 'source thiếu', path: `${EX}.source`, build: (f) => ((pushUp(f).source = undefined), f) },
  { label: 'rep là null', path: `${EX}.rep`, build: (f) => ({ ...f, exercises: { 'push-up': { ...pushUp(f), rep: null } } }) },
  { label: 'rep.joint không phải mảng', path: `${EX}.rep.joint`, build: (f) => ((pushUp(f).rep.joint = 'knee'), f) },
  { label: 'flexed_deg NaN', path: `${EX}.rep.flexed_deg`, build: (f) => ((pushUp(f).rep.flexed_deg = Number.NaN), f) },
  { label: 'partial_deg âm', path: `${EX}.rep.partial_deg`, build: (f) => ((pushUp(f).rep.partial_deg = -1), f) },
  { label: 'partial_deg = extended_deg', path: `${EX}.rep.partial_deg`, build: (f) => ((pushUp(f).rep.partial_deg = 160), f) },
  { label: 'checks không phải mảng', path: `${EX}.checks`, build: (f) => ((pushUp(f).checks = {}), f) },
  {
    label: 'checks[0] là null',
    path: `${EX}.checks.0`,
    build: (f) => ((pushUp(f).checks = [null]), f),
  },
  {
    label: 'checks[0].joint có "toe"',
    path: `${EX}.checks.0.joint`,
    build: (f) => ((firstCheck(f).joint = ['shoulder', 'hip', 'toe']), f),
  },
  {
    label: 'checks[0].mistake_code có dấu gạch ngang',
    path: `${EX}.checks.0.mistake_code`,
    build: (f) => ((firstCheck(f).mistake_code = 'PUSHUP-HIP'), f),
  },
  { label: 'checks[0].max_deg 200', path: `${EX}.checks.0.max_deg`, build: (f) => ((firstCheck(f).max_deg = 200), f) },
  { label: 'checks[0].min_deg thiếu', path: `${EX}.checks.0.min_deg`, build: (f) => ((firstCheck(f).min_deg = undefined), f) },
];

function captureError(raw: unknown): unknown {
  try {
    validatePoseRules(raw);
  } catch (error) {
    return error;
  }
  return null;
}

describe('validatePoseRules: dữ liệu sai (spec fe-pose-logic §2.3)', () => {
  it('POSE-05 fixture gốc hợp lệ, trả về chính dữ liệu đầu vào', () => {
    const raw = cloneFixture();
    expect(() => validatePoseRules(raw)).not.toThrow();
    expect(validatePoseRules(raw)).toBe(raw);
    expect(validatePoseRules(raw)).toEqual(VALID_FIXTURE);
  });

  it.each(INVALID_CASES)('POSE-05 $label ném PoseRulesError tại "$path"', ({ path, build }) => {
    const error = captureError(build(cloneFixture()));
    expect(error).toBeInstanceOf(PoseRulesError);
    expect(error).toBeInstanceOf(Error);
    if (!(error instanceof PoseRulesError)) return;
    expect(error.path).toBe(path);
    expect(error.message).toContain(`"${path}"`);
    expect(error.name).toBe('PoseRulesError');
  });

  it.each(EXTRA_INVALID_CASES)('POSE-05 biên: $label ném PoseRulesError tại "$path"', ({ path, build }) => {
    const error = captureError(build(cloneFixture()));
    expect(error).toBeInstanceOf(PoseRulesError);
    if (!(error instanceof PoseRulesError)) return;
    expect(error.path).toBe(path);
    expect(error.message).toContain(`"${path}"`);
  });

  it('POSE-05 biên: cận hợp lệ ở mép khoảng và key lạ được chấp nhận', () => {
    const file = cloneFixture();
    file.min_visibility = 1;
    Object.assign(firstCheck(file), { min_deg: 0, max_deg: 180, phases: ['top'], severity: 'info' });
    Object.assign(pushUp(file).rep, { flexed_deg: 0, extended_deg: 180, partial_mistake_code: null });
    Object.assign(file, { note: 'key lạ' });
    expect(() => validatePoseRules(file)).not.toThrow();
    const sameBounds = cloneFixture();
    Object.assign(firstCheck(sameBounds), { min_deg: 90, max_deg: 90 });
    expect(() => validatePoseRules(sameBounds)).not.toThrow();
    const noBodies = { ...cloneFixture(), exercises: {} };
    expect(() => validatePoseRules(noBodies)).not.toThrow();
  });
});

describe('hasAiRules, getPoseRules, AI_RULE_SLUGS, canUseAiTrainer (spec fe-pose-logic §2.4)', () => {
  it.each(SIX_SLUGS)('POSE-06 hasAiRules(%s) là true', (slug) => {
    expect(hasAiRules(slug)).toBe(true);
  });

  it.each(['goblet-squat', 'leg-press', '', 'Barbell-Back-Squat', ' push-up', '__proto__', 'constructor', 'toString'])(
    'POSE-06 hasAiRules(%j) là false',
    (slug) => {
      expect(hasAiRules(slug)).toBe(false);
    },
  );

  it('POSE-06 getPoseRules trả luật của bài có luật, null cho slug lạ', () => {
    expect(getPoseRules('push-up')?.rep.joint).toEqual(['shoulder', 'elbow', 'wrist']);
    expect(getPoseRules('khong-co')).toBeNull();
    expect(getPoseRules('__proto__')).toBeNull();
    expect(getPoseRules('toString')).toBeNull();
  });

  it('POSE-06 AI_RULE_SLUGS là 6 slug sắp theo bảng chữ cái', () => {
    expect(AI_RULE_SLUGS).toEqual([
      'barbell-back-squat',
      'barbell-curl',
      'conventional-deadlift',
      'overhead-press',
      'push-up',
      'walking-lunge',
    ]);
  });

  it('POSE-06 canUseAiTrainer cần cả supports_ai_tracking lẫn luật tư thế', () => {
    expect(canUseAiTrainer({ slug: 'barbell-back-squat', supports_ai_tracking: true })).toBe(true);
    expect(canUseAiTrainer({ slug: 'walking-lunge', supports_ai_tracking: false })).toBe(false);
    expect(canUseAiTrainer({ slug: 'goblet-squat', supports_ai_tracking: true })).toBe(false);
  });
});
