import {
  angleDeg,
  LANDMARK_INDEX,
  measureJoint,
  pickSide,
  toPixelLandmarks,
  type JointTriple,
  type Landmark,
  type Side,
} from '@/utils/pose';

// Số kỳ vọng chép từ spec fe-pose-logic §5 (POSE-01..03), không suy ra từ code.
const LEG: JointTriple = ['hip', 'knee', 'ankle'];
const MIN_VISIBILITY = 0.5;

/** `L(vis)` của spec §5: 33 landmark `{ x: 0, y: 0, visibility: vis }`. */
function L(vis: number): Landmark[] {
  return Array.from({ length: 33 }, () => ({ x: 0, y: 0, visibility: vis }));
}

function setSide(landmarks: Landmark[], side: Side, patch: Partial<Landmark>, joint: JointTriple = LEG): void {
  for (const name of joint) {
    const index = LANDMARK_INDEX[name][side];
    landmarks[index] = { ...(landmarks[index] ?? { x: 0, y: 0 }), ...patch };
  }
}

/** Hai bên có điểm khác nhau (toạ độ hai bên khác nhau để góc đo được). */
function legs(leftVis: number, rightVis: number): Landmark[] {
  const landmarks = L(0.1);
  setSide(landmarks, 'left', { visibility: leftVis });
  setSide(landmarks, 'right', { visibility: rightVis });
  return landmarks;
}

function hasAtMost2Decimals(value: number): boolean {
  return Math.round(value * 100) / 100 === value;
}

describe('angleDeg (spec fe-pose-logic §2.4)', () => {
  const origin = { x: 0, y: 0 };
  const a = { x: 1, y: 0 };

  it.each([
    { c: { x: 0, y: 1 }, expected: 90 },
    { c: { x: 1, y: 1 }, expected: 45 },
    { c: { x: -1, y: 0 }, expected: 180 },
    { c: { x: 2, y: 0 }, expected: 0 },
    { c: { x: 0.1, y: 1 }, expected: 84.29 },
  ])('POSE-01 góc tại b=(0,0) giữa a=(1,0) và c=($c.x,$c.y) đúng bằng $expected', ({ c, expected }) => {
    expect(angleDeg(a, origin, c)).toBe(expected);
  });

  it('POSE-01 đảo thứ tự a và c vẫn ra 90', () => {
    expect(angleDeg({ x: 0, y: 1 }, origin, a)).toBe(90);
  });

  it('POSE-01 chế độ 3D dùng z; mặc định 2D bỏ z nên c trùng b thì null', () => {
    const a3 = { x: 1, y: 0, z: 0 };
    const b3 = { x: 0, y: 0, z: 0 };
    const c3 = { x: 0, y: 0, z: 1 };
    expect(angleDeg(a3, b3, c3, { use3d: true })).toBe(90);
    expect(angleDeg(a3, b3, c3)).toBeNull();
    expect(angleDeg(a3, b3, c3, { use3d: false })).toBeNull();
  });

  it('POSE-01 use3d: true khi a thiếu z thì trả null', () => {
    expect(angleDeg({ x: 1, y: 0 }, { x: 0, y: 0, z: 0 }, { x: 0, y: 0, z: 1 }, { use3d: true })).toBeNull();
  });

  it('POSE-01 use3d: true khi b thiếu z cũng trả null', () => {
    expect(angleDeg({ x: 1, y: 0, z: 0 }, { x: 0, y: 0 }, { x: 0, y: 0, z: 1 }, { use3d: true })).toBeNull();
  });
});

describe('angleDeg: lỗi và biên số học (spec fe-pose-logic §2.4)', () => {
  const b = { x: 0.2, y: 0.4 };

  it.each([
    { label: 'a trùng b', a: { x: 0.2, y: 0.4 }, c: { x: 1, y: 1 } },
    { label: 'c trùng b', a: { x: 1, y: 1 }, c: { x: 0.2, y: 0.4 } },
    { label: 'toạ độ NaN', a: { x: Number.NaN, y: 1 }, c: { x: 1, y: 0 } },
    { label: 'toạ độ Infinity', a: { x: 1, y: 1 }, c: { x: 1, y: Number.POSITIVE_INFINITY } },
    { label: 'toạ độ -Infinity', a: { x: Number.NEGATIVE_INFINITY, y: 1 }, c: { x: 1, y: 0 } },
  ])('POSE-02 $label thì trả null', ({ a, c }) => {
    expect(angleDeg(a, b, c)).toBeNull();
  });

  it('POSE-02 toạ độ NaN ở b hoặc z NaN khi use3d thì trả null', () => {
    expect(angleDeg({ x: 1, y: 0 }, { x: 0, y: Number.NaN }, { x: 0, y: 1 })).toBeNull();
    expect(angleDeg({ x: 1, y: 0, z: Number.NaN }, { x: 0, y: 0, z: 0 }, { x: 0, y: 1, z: 0 }, { use3d: true })).toBeNull();
  });

  it('POSE-02 gần thẳng hàng trả đúng 180, không NaN', () => {
    const value = angleDeg({ x: 0.1, y: 0.2 }, { x: 0.2, y: 0.4 }, { x: 0.3, y: 0.6 });
    expect(value).toBe(180);
  });

  it('POSE-02 cùng hướng trả đúng 0 (không phải -0), không NaN', () => {
    const value = angleDeg({ x: 0.2, y: 0.4 }, { x: 0.1, y: 0.2 }, { x: 0.3, y: 0.6 });
    expect(value).toBe(0);
    expect(Object.is(value, -0)).toBe(false);
  });

  it('POSE-02 mọi kết quả số có tối đa 2 chữ số thập phân và nằm trong [0, 180]', () => {
    const cases: [number, number][] = [
      [0.1, 1],
      [0.3, 0.7],
      [-0.123, 0.456],
      [1, 1e-9],
      [-1, 1e-9],
      [0.333, -0.777],
    ];
    for (const [x, y] of cases) {
      const value = angleDeg({ x: 1, y: 0 }, { x: 0, y: 0 }, { x, y });
      expect(value).not.toBeNull();
      const angle = value ?? Number.NaN;
      expect(Number.isNaN(angle)).toBe(false);
      expect(hasAtMost2Decimals(angle)).toBe(true);
      expect(angle).toBeGreaterThanOrEqual(0);
      expect(angle).toBeLessThanOrEqual(180);
    }
  });
});

describe('landmark (spec fe-pose-logic §2.4)', () => {
  it('POSE-03 LANDMARK_INDEX đúng chỉ số MediaPipe Pose của 6 khớp', () => {
    expect(LANDMARK_INDEX).toEqual({
      shoulder: { left: 11, right: 12 },
      elbow: { left: 13, right: 14 },
      wrist: { left: 15, right: 16 },
      hip: { left: 23, right: 24 },
      knee: { left: 25, right: 26 },
      ankle: { left: 27, right: 28 },
    });
    expect(LANDMARK_INDEX.hip.left).toBe(23);
    expect(LANDMARK_INDEX.ankle.right).toBe(28);
  });

  it('POSE-03 toPixelLandmarks đổi sang pixel, z theo width, giữ visibility', () => {
    expect(toPixelLandmarks([{ x: 0.5, y: 0.25, z: 0.1, visibility: 0.8 }], 640, 480)).toEqual([
      { x: 320, y: 120, z: 64, visibility: 0.8 },
    ]);
  });

  it('POSE-03 toPixelLandmarks không thêm z hay visibility khi đầu vào không có', () => {
    const result = toPixelLandmarks([{ x: 0.5, y: 0.5 }], 640, 480);
    expect(result).toEqual([{ x: 320, y: 240 }]);
    expect(result[0]).not.toHaveProperty('z');
    expect(result[0]).not.toHaveProperty('visibility');
  });

  it('POSE-03 toPixelLandmarks trả mảng mới, không sửa đầu vào', () => {
    const input: Landmark[] = [{ x: 0.5, y: 0.25 }];
    const result = toPixelLandmarks(input, 640, 480);
    expect(result).not.toBe(input);
    expect(result[0]).not.toBe(input[0]);
    expect(input).toEqual([{ x: 0.5, y: 0.25 }]);
    expect(toPixelLandmarks([], 640, 480)).toEqual([]);
  });

  it.each([
    { width: 0, height: 480 },
    { width: 640, height: 0 },
    { width: -640, height: 480 },
    { width: Number.NaN, height: 480 },
    { width: 640, height: Number.POSITIVE_INFINITY },
  ])('POSE-03 toPixelLandmarks ném RangeError với width=$width, height=$height', ({ width, height }) => {
    expect(() => toPixelLandmarks([{ x: 0.5, y: 0.5 }], width, height)).toThrow(RangeError);
  });

  it('POSE-03 pickSide (a) trái 0.9, phải 0.3 chọn left', () => {
    expect(pickSide(legs(0.9, 0.3), LEG, MIN_VISIBILITY)).toBe('left');
  });

  it('POSE-03 pickSide (b) trái có một landmark 0.4, phải 0.6 chọn right', () => {
    const landmarks = legs(0.9, 0.6);
    landmarks[LANDMARK_INDEX.knee.left] = { x: 0, y: 0, visibility: 0.4 };
    expect(pickSide(landmarks, LEG, MIN_VISIBILITY)).toBe('right');
  });

  it('POSE-03 pickSide (c) hai bên 0.49 trả null', () => {
    expect(pickSide(L(0.49), LEG, MIN_VISIBILITY)).toBeNull();
  });

  it('POSE-03 pickSide (d) hai bên đúng 0.5 chọn left', () => {
    expect(pickSide(L(0.5), LEG, MIN_VISIBILITY)).toBe('left');
  });

  it('POSE-03 pickSide (e) không có visibility coi là 1, chọn left', () => {
    const landmarks: Landmark[] = Array.from({ length: 33 }, () => ({ x: 0, y: 0 }));
    expect(pickSide(landmarks, LEG, MIN_VISIBILITY)).toBe('left');
    expect(pickSide(landmarks, LEG, 1)).toBe('left');
  });

  it('POSE-03 pickSide (f) mảng chỉ có 20 phần tử trả null', () => {
    expect(pickSide(L(0.9).slice(0, 20), LEG, MIN_VISIBILITY)).toBeNull();
  });

  it('POSE-03 pickSide (g) phải 0.9 nhưng x gối phải là NaN, trái 0.8 chọn left', () => {
    const landmarks = legs(0.8, 0.9);
    landmarks[LANDMARK_INDEX.knee.right] = { x: Number.NaN, y: 0, visibility: 0.9 };
    expect(pickSide(landmarks, LEG, MIN_VISIBILITY)).toBe('left');
  });

  it('POSE-03 pickSide bỏ bên có y vô hạn, và trả null khi cả hai bên bị loại', () => {
    const landmarks = legs(0.6, 0.9);
    landmarks[LANDMARK_INDEX.ankle.right] = { x: 0, y: Number.POSITIVE_INFINITY, visibility: 0.9 };
    expect(pickSide(landmarks, LEG, MIN_VISIBILITY)).toBe('left');
    landmarks[LANDMARK_INDEX.hip.left] = { x: 0, y: Number.NaN, visibility: 0.6 };
    expect(pickSide(landmarks, LEG, MIN_VISIBILITY)).toBeNull();
  });

  it('POSE-03 pickSide chỉ bên trái thiếu landmark thì chọn right nếu đủ visibility', () => {
    const landmarks = legs(0.9, 0.7);
    // Mảng thưa: chỉ số cổ chân trái không có phần tử.
    delete landmarks[LANDMARK_INDEX.ankle.left];
    expect(pickSide(landmarks, LEG, MIN_VISIBILITY)).toBe('right');
  });

  it('POSE-03 measureJoint đo góc tại gối giữa hông (0,0) và cổ chân (1,1)', () => {
    const landmarks = L(0.1);
    landmarks[LANDMARK_INDEX.hip.left] = { x: 0, y: 0, visibility: 0.9 };
    landmarks[LANDMARK_INDEX.knee.left] = { x: 1, y: 0, visibility: 0.9 };
    landmarks[LANDMARK_INDEX.ankle.left] = { x: 1, y: 1, visibility: 0.9 };
    expect(measureJoint(landmarks, LEG, MIN_VISIBILITY)).toEqual({ side: 'left', angle_deg: 90 });
  });

  it('POSE-03 measureJoint đo ở bên phải khi bên phải rõ hơn', () => {
    const landmarks = L(0.1);
    landmarks[LANDMARK_INDEX.hip.right] = { x: 0, y: 0, visibility: 0.9 };
    landmarks[LANDMARK_INDEX.knee.right] = { x: 1, y: 0, visibility: 0.9 };
    landmarks[LANDMARK_INDEX.ankle.right] = { x: 0.1, y: 1, visibility: 0.9 };
    expect(measureJoint(landmarks, LEG, MIN_VISIBILITY)).toEqual({ side: 'right', angle_deg: 48.01 });
  });

  it('POSE-03 measureJoint trả null khi không chọn được bên', () => {
    expect(measureJoint(L(0.3), LEG, MIN_VISIBILITY)).toBeNull();
  });

  it('POSE-03 measureJoint trả null khi góc không đo được (hông trùng gối)', () => {
    // L(0.9): mọi landmark ở (0,0) nên vector gối→hông có độ dài 0.
    expect(measureJoint(L(0.9), LEG, MIN_VISIBILITY)).toBeNull();
  });
});
