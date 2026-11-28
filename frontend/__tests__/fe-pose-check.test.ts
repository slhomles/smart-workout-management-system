import {
  checkPose,
  LANDMARK_INDEX,
  POSE_RULES,
  type ExerciseRule,
  type JointName,
  type Landmark,
  type Phase,
  type Point,
  type Side,
} from '@/utils/pose';

// Rule giả và số kỳ vọng chép từ spec fe-pose-logic §5 (POSE-13), không phải ngưỡng thật.
const RULE: ExerciseRule = {
  source: 'dữ liệu test',
  view: 'side',
  rep: {
    joint: ['hip', 'knee', 'ankle'],
    start: 'extended',
    first_phase: 'eccentric',
    extended_deg: 160,
    flexed_deg: 100,
    partial_deg: 130,
    partial_mistake_code: null,
  },
  checks: [
    {
      mistake_code: 'TEST_MIN_ANGLE',
      joint: ['shoulder', 'hip', 'knee'],
      min_deg: 90,
      max_deg: null,
      phases: ['eccentric', 'bottom', 'concentric'],
      severity: 'critical',
    },
    {
      mistake_code: 'TEST_MAX_ANGLE',
      joint: ['shoulder', 'elbow', 'wrist'],
      min_deg: null,
      max_deg: 90,
      phases: ['eccentric', 'bottom', 'concentric', 'top'],
      severity: 'warning',
    },
  ],
};

const MIN_VISIBILITY = 0.5;
const SIDE_JOINTS: JointName[] = ['shoulder', 'elbow', 'wrist', 'hip', 'knee', 'ankle'];

/** `L(vis)` của spec §5: 33 landmark `{ x: 0, y: 0, visibility: vis }`. */
function L(vis: number): Landmark[] {
  return Array.from({ length: 33 }, () => ({ x: 0, y: 0, visibility: vis }));
}

function setVisibility(landmarks: Landmark[], side: Side, visibility: number): void {
  for (const name of SIDE_JOINTS) {
    const index = LANDMARK_INDEX[name][side];
    landmarks[index] = { ...(landmarks[index] ?? { x: 0, y: 0 }), visibility };
  }
}

function place(landmarks: Landmark[], side: Side, name: JointName, point: Point): void {
  const index = LANDMARK_INDEX[name][side];
  landmarks[index] = { ...(landmarks[index] ?? { x: 0, y: 0 }), x: point.x, y: point.y };
}

/** Khuỷu đặt ngay dưới vai theo trục y, cổ tay dựng sao cho góc vai-khuỷu-cổ tay đúng `elbowDeg`. */
function placeArm(landmarks: Landmark[], side: Side, shoulder: Point, elbowDeg: number): void {
  const radians = (elbowDeg * Math.PI) / 180;
  const elbow = { x: shoulder.x, y: shoulder.y + 1 };
  place(landmarks, side, 'elbow', elbow);
  place(landmarks, side, 'wrist', { x: elbow.x + Math.sin(radians), y: elbow.y - Math.cos(radians) });
}

type PoseInput = { shoulder: Point; elbowDeg?: number; side?: Side };

/** Bên `side` rõ 0.9 (bên kia giữ 0.1 của `L`), hông (0,0), gối (1,0), vai theo đầu vào. */
function pose({ shoulder, elbowDeg = 90, side = 'left' }: PoseInput): Landmark[] {
  const landmarks = L(0.1);
  setVisibility(landmarks, side, 0.9);
  place(landmarks, side, 'hip', { x: 0, y: 0 });
  place(landmarks, side, 'knee', { x: 1, y: 0 });
  place(landmarks, side, 'shoulder', shoulder);
  placeArm(landmarks, side, shoulder, elbowDeg);
  return landmarks;
}

function codes(result: ReturnType<typeof checkPose>): string[] {
  return result.map((violation) => violation.mistake_code);
}

describe('checkPose (spec fe-pose-logic §2.6)', () => {
  const tilted = { x: 0.1, y: 1 };

  it('POSE-13 (a) góc hông 84.29 < min 90 ở pha eccentric: đúng 1 vi phạm', () => {
    expect(checkPose(RULE, pose({ shoulder: tilted }), 'eccentric', MIN_VISIBILITY)).toEqual([
      {
        mistake_code: 'TEST_MIN_ANGLE',
        severity: 'critical',
        joint: ['shoulder', 'hip', 'knee'],
        side: 'left',
        measured_angle_deg: 84.29,
      },
    ]);
  });

  it('POSE-13 (b) góc hông bằng ngưỡng 90 thì không vi phạm', () => {
    expect(checkPose(RULE, pose({ shoulder: { x: 0, y: 1 } }), 'eccentric', MIN_VISIBILITY)).toEqual([]);
  });

  it('POSE-13 (c) góc hông lớn hơn ngưỡng thì không vi phạm', () => {
    expect(checkPose(RULE, pose({ shoulder: { x: -0.1, y: 1 } }), 'eccentric', MIN_VISIBILITY)).toEqual([]);
  });

  it('POSE-13 (d) phase top không thuộc phases của TEST_MIN_ANGLE nên bỏ qua', () => {
    const result = checkPose(RULE, pose({ shoulder: tilted }), 'top', MIN_VISIBILITY);
    expect(codes(result)).not.toContain('TEST_MIN_ANGLE');
    expect(result).toEqual([]);
  });

  it('POSE-13 (e) phase null thì không kiểm luật nào', () => {
    expect(checkPose(RULE, pose({ shoulder: tilted, elbowDeg: 120 }), null, MIN_VISIBILITY)).toEqual([]);
  });

  it('POSE-13 (f) mọi visibility 0.3 thì không thấy khớp, không vi phạm', () => {
    const landmarks = pose({ shoulder: tilted, elbowDeg: 120 }).map((landmark) => ({ ...landmark, visibility: 0.3 }));
    expect(checkPose(RULE, landmarks, 'eccentric', MIN_VISIBILITY)).toEqual([]);
  });

  it('POSE-13 (g) bên phải rõ hơn thì vi phạm ghi side right', () => {
    const landmarks = pose({ shoulder: tilted, side: 'right' });
    setVisibility(landmarks, 'left', 0.2);
    const result = checkPose(RULE, landmarks, 'eccentric', MIN_VISIBILITY);
    const violation = result.find((item) => item.mistake_code === 'TEST_MIN_ANGLE');
    expect(violation).toEqual({
      mistake_code: 'TEST_MIN_ANGLE',
      severity: 'critical',
      joint: ['shoulder', 'hip', 'knee'],
      side: 'right',
      measured_angle_deg: 84.29,
    });
  });

  it('POSE-13 (h) góc khuỷu 120 > max 90: hai vi phạm theo thứ tự checks', () => {
    const result = checkPose(RULE, pose({ shoulder: tilted, elbowDeg: 120 }), 'eccentric', MIN_VISIBILITY);
    expect(codes(result)).toEqual(['TEST_MIN_ANGLE', 'TEST_MAX_ANGLE']);
    expect(result[1]).toEqual({
      mistake_code: 'TEST_MAX_ANGLE',
      severity: 'warning',
      joint: ['shoulder', 'elbow', 'wrist'],
      side: 'left',
      measured_angle_deg: 120,
    });
  });

  it('POSE-13 biên: góc khuỷu đúng 90 bằng max_deg thì không vi phạm ở pha top', () => {
    expect(checkPose(RULE, pose({ shoulder: tilted, elbowDeg: 90 }), 'top', MIN_VISIBILITY)).toEqual([]);
    expect(codes(checkPose(RULE, pose({ shoulder: tilted, elbowDeg: 90.5 }), 'top', MIN_VISIBILITY))).toEqual([
      'TEST_MAX_ANGLE',
    ]);
  });

  it('POSE-13 biên: phần tử trả về giữ bản sao joint, không chia sẻ mảng của rule', () => {
    const [violation] = checkPose(RULE, pose({ shoulder: tilted }), 'bottom', MIN_VISIBILITY);
    expect(violation?.joint).toEqual(RULE.checks[0]?.joint);
    expect(violation?.joint).not.toBe(RULE.checks[0]?.joint);
  });

  it.each<Phase>(['eccentric', 'bottom', 'concentric'])(
    'POSE-13 biên: minVisibility mặc định lấy từ POSE_RULES, pha %s vẫn kiểm',
    (phase) => {
      expect(POSE_RULES.min_visibility).toBeLessThanOrEqual(0.9);
      expect(codes(checkPose(RULE, pose({ shoulder: tilted }), phase))).toEqual(['TEST_MIN_ANGLE']);
    },
  );

  it('POSE-13 biên: rule không có checks thì trả mảng rỗng', () => {
    expect(checkPose({ ...RULE, checks: [] }, pose({ shoulder: tilted }), 'eccentric', MIN_VISIBILITY)).toEqual([]);
  });
});
