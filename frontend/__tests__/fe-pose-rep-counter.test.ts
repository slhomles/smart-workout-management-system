import {
  createRepCounter,
  phaseOf,
  type RepRule,
  type RepState,
  type RepUpdate,
} from '@/utils/pose';

// Rule giả chép từ spec fe-pose-logic §5 (chỉ là dữ liệu test, không phải ngưỡng thật).
const SQ: RepRule = {
  joint: ['hip', 'knee', 'ankle'],
  start: 'extended',
  first_phase: 'eccentric',
  extended_deg: 160,
  flexed_deg: 100,
  partial_deg: 130,
  partial_mistake_code: 'SQUAT_SHALLOW_DEPTH',
};
const CURL: RepRule = {
  joint: ['shoulder', 'elbow', 'wrist'],
  start: 'extended',
  first_phase: 'concentric',
  extended_deg: 150,
  flexed_deg: 60,
  partial_deg: 100,
  partial_mistake_code: null,
};
const DL: RepRule = {
  joint: ['shoulder', 'hip', 'knee'],
  start: 'flexed',
  first_phase: 'concentric',
  extended_deg: 165,
  flexed_deg: 100,
  partial_deg: 130,
  partial_mistake_code: null,
};

type Pair = [number, number | null];

function feed(counter: ReturnType<typeof createRepCounter>, pairs: Pair[]): RepUpdate[] {
  return pairs.map(([t_ms, angle_deg]) => counter.update({ t_ms, angle_deg }));
}

function at(updates: RepUpdate[], index: number): RepUpdate {
  const update = updates[index];
  if (update === undefined) throw new Error(`không có update thứ ${index}`);
  return update;
}

const POSE_07_SAMPLES: Pair[] = [
  [0, 170],
  [500, 165],
  [1000, 150],
  [2500, 120],
  [4000, 95],
  [4200, 90],
  [4500, 110],
  [5000, 140],
  [5500, 165],
];

describe('createRepCounter: rep đủ biên độ', () => {
  it('POSE-07 SQ: trạng thái, pha và rep đủ biên độ đúng từng mẫu', () => {
    const updates = feed(createRepCounter(SQ), POSE_07_SAMPLES);

    expect(updates.map((u) => `${u.state}/${u.phase}`)).toEqual([
      'at_start/top',
      'at_start/top',
      'moving_out/eccentric',
      'moving_out/eccentric',
      'at_end/bottom',
      'at_end/bottom',
      'moving_back/concentric',
      'moving_back/concentric',
      'at_start/top',
    ]);
    updates.slice(0, -1).forEach((u) => {
      expect(u.completed_rep).toBeNull();
      expect(u.rep_count).toBe(0);
      expect(u.partial_mistake_code).toBeNull();
    });
    const last = at(updates, 8);
    expect(last.completed_rep).toEqual({
      rep_no: 1,
      start_offset_ms: 1000,
      eccentric_ms: 3000,
      pause_bottom_ms: 500,
      concentric_ms: 1000,
      pause_top_ms: 0,
      min_joint_angle_deg: 90,
      max_joint_angle_deg: 165,
      is_full_rom: true,
    });
    expect(last.rep_count).toBe(1);
    expect(last.partial_mistake_code).toBeNull();
  });

  it('POSE-07 nghỉ ở S tính cho rep trước khi rep sau rời S; completed_rep cũ không bị đổi', () => {
    const counter = createRepCounter(SQ);
    const updates = feed(counter, POSE_07_SAMPLES);
    expect(counter.getReps()[0]?.pause_top_ms).toBe(0);

    feed(counter, [
      [6500, 170],
      [7000, 150],
    ]);
    const reps = counter.getReps();
    expect(reps[0]?.pause_top_ms).toBe(1500);
    expect(at(updates, 8).completed_rep?.pause_top_ms).toBe(0);

    const end = feed(counter, [
      [8000, 98],
      [8300, 120],
      [9000, 162],
    ]);
    expect(at(end, 2).completed_rep).toMatchObject({ rep_no: 2, start_offset_ms: 7000, pause_top_ms: 0 });
    expect(at(end, 2).rep_count).toBe(2);
  });

  it('POSE-07 rời S thẳng vào O cũng cập nhật nghỉ của rep trước', () => {
    const counter = createRepCounter(SQ);
    feed(counter, POSE_07_SAMPLES);
    const updates = feed(counter, [[6000, 80]]);
    expect(at(updates, 0).state).toBe('at_end');
    expect(counter.getReps()[0]?.pause_top_ms).toBe(500);
  });

  it('POSE-07 getReps trả bản sao: sửa mảng hay phần tử không ảnh hưởng lần gọi sau', () => {
    const counter = createRepCounter(SQ);
    const updates = feed(counter, POSE_07_SAMPLES);
    const reps = counter.getReps();
    reps.pop();
    const again = counter.getReps();
    const first = again[0];
    if (first === undefined) throw new Error('thiếu rep 1');
    first.eccentric_ms = 1;
    const completed = at(updates, 8).completed_rep;
    if (completed === null) throw new Error('thiếu completed_rep');
    completed.concentric_ms = 1;

    expect(counter.getReps()).toHaveLength(1);
    expect(counter.getReps()[0]).toMatchObject({ eccentric_ms: 3000, concentric_ms: 1000 });
  });

  it('POSE-07 mọi field *_ms được làm tròn khi t_ms là số thực', () => {
    const updates = feed(createRepCounter(SQ), [
      [0.2, 170],
      [1000.4, 150],
      [2000.6, 90],
      [2500.5, 120],
      [3000.2, 170],
    ]);
    expect(at(updates, 4).completed_rep).toMatchObject({
      start_offset_ms: 1000,
      eccentric_ms: 1000,
      pause_bottom_ms: 500,
      concentric_ms: 500,
    });
  });
});

describe('createRepCounter: pha đầu concentric, bắt đầu ở flexed và phaseOf', () => {
  it('POSE-09 CURL: pha từng mẫu và rep gán field theo first_phase concentric', () => {
    const updates = feed(createRepCounter(CURL), [
      [0, 160],
      [400, 140],
      [1200, 55],
      [1500, 58],
      [1800, 80],
      [4800, 155],
    ]);
    expect(updates.map((u) => u.phase)).toEqual(['bottom', 'concentric', 'top', 'top', 'eccentric', 'bottom']);
    expect(at(updates, 5).completed_rep).toEqual({
      rep_no: 1,
      start_offset_ms: 400,
      concentric_ms: 800,
      pause_top_ms: 600,
      eccentric_ms: 3000,
      pause_bottom_ms: 0,
      min_joint_angle_deg: 55,
      max_joint_angle_deg: 155,
      is_full_rom: true,
    });
  });

  it('POSE-09 DL: bắt đầu ở flexed, trạng thái và rep đúng', () => {
    const updates = feed(createRepCounter(DL), [
      [0, 90],
      [300, 120],
      [1300, 170],
      [2300, 150],
      [4300, 95],
    ]);
    expect(updates.map((u) => u.state)).toEqual(['at_start', 'moving_out', 'at_end', 'moving_back', 'at_start']);
    expect(at(updates, 4).completed_rep).toMatchObject({
      start_offset_ms: 300,
      concentric_ms: 1000,
      pause_top_ms: 1000,
      eccentric_ms: 2000,
      pause_bottom_ms: 0,
      min_joint_angle_deg: 95,
      max_joint_angle_deg: 170,
    });
  });

  it('POSE-09 phaseOf với 5 trạng thái cho SQ và CURL', () => {
    const states: RepState[] = ['idle', 'at_start', 'moving_out', 'at_end', 'moving_back'];
    expect(states.map((s) => phaseOf(s, SQ))).toEqual([null, 'top', 'eccentric', 'bottom', 'concentric']);
    expect(states.map((s) => phaseOf(s, CURL))).toEqual([null, 'bottom', 'concentric', 'top', 'eccentric']);
  });
});

describe('createRepCounter: biên ngưỡng, nảy ở đáy, nhảy vùng', () => {
  it('POSE-10 (a) chỉ sang at_start khi góc bằng extended_deg', () => {
    const updates = feed(createRepCounter(SQ), [
      [0, 130],
      [100, 90],
      [200, 159.9],
      [300, 160],
    ]);
    updates.slice(0, 3).forEach((u) => {
      expect(u.state).toBe('idle');
      expect(u.phase).toBeNull();
    });
    expect(at(updates, 3).state).toBe('at_start');
  });

  it('POSE-10 (b) nảy ở đáy: enterO giữ nguyên, leaveO lấy lần rời O sau cùng', () => {
    const updates = feed(createRepCounter(SQ), [
      [0, 170],
      [1000, 100.1],
      [2000, 100],
      [2500, 100.1],
      [3000, 100],
      [3500, 159.9],
      [4000, 160],
    ]);
    expect(updates.slice(1).map((u) => u.state)).toEqual([
      'moving_out',
      'at_end',
      'moving_back',
      'at_end',
      'moving_back',
      'at_start',
    ]);
    const last = at(updates, 6);
    expect(last.completed_rep).toMatchObject({
      start_offset_ms: 1000,
      eccentric_ms: 1000,
      pause_bottom_ms: 1500,
      concentric_ms: 500,
      min_joint_angle_deg: 100,
      max_joint_angle_deg: 160,
      is_full_rom: true,
    });
    expect(last.rep_count).toBe(1);
  });

  it('POSE-10 (c) nhảy thẳng S → O → S trong một mẫu', () => {
    const updates = feed(createRepCounter(SQ), [
      [0, 170],
      [1000, 90],
      [2000, 170],
    ]);
    expect(at(updates, 1).state).toBe('at_end');
    expect(at(updates, 2).completed_rep).toMatchObject({
      start_offset_ms: 1000,
      eccentric_ms: 0,
      pause_bottom_ms: 1000,
      concentric_ms: 0,
      is_full_rom: true,
    });
  });

  it('POSE-10 DL (start flexed): biên ngưỡng S và O tính là trong vùng', () => {
    const updates = feed(createRepCounter(DL), [
      [0, 100.1],
      [100, 100],
      [200, 164.9],
      [300, 165],
      [400, 100],
    ]);
    expect(updates.map((u) => u.state)).toEqual(['idle', 'at_start', 'moving_out', 'at_end', 'at_start']);
    expect(at(updates, 4).rep_count).toBe(1);
  });
});

describe('createRepCounter: rep thiếu biên độ và nhiễu', () => {
  it('POSE-11 (a) rep thiếu biên độ, nhiễu không đếm, nghỉ S lấy lần rời S thật', () => {
    const counter = createRepCounter(SQ);
    const updates = feed(counter, [
      [0, 170],
      [1000, 150],
      [2000, 125],
      [2600, 128],
      [3000, 165],
      [4000, 145],
      [4500, 140],
      [5000, 170],
      [6000, 150],
      [7000, 95],
      [8000, 165],
    ]);
    const partial = at(updates, 4);
    expect(partial.completed_rep).toEqual({
      rep_no: 1,
      start_offset_ms: 1000,
      eccentric_ms: 1000,
      pause_bottom_ms: 0,
      concentric_ms: 1000,
      pause_top_ms: 0,
      min_joint_angle_deg: 125,
      max_joint_angle_deg: 165,
      is_full_rom: false,
    });
    expect(partial.partial_mistake_code).toBe('SQUAT_SHALLOW_DEPTH');
    expect(partial.rep_count).toBe(1);

    const noise = at(updates, 7);
    expect(noise.state).toBe('at_start');
    expect(noise.completed_rep).toBeNull();
    expect(noise.partial_mistake_code).toBeNull();
    expect(noise.rep_count).toBe(1);

    const second = at(updates, 10);
    expect(second.completed_rep).toMatchObject({ rep_no: 2, start_offset_ms: 6000, is_full_rom: true });
    expect(second.partial_mistake_code).toBeNull();
    expect(counter.getReps()[0]?.pause_top_ms).toBe(3000);
  });

  it('POSE-11 SQ: nhiễu quay về S đặt lại pause_top_ms của rep cuối về 0', () => {
    const counter = createRepCounter(SQ);
    feed(counter, [
      [0, 170],
      [1000, 150],
      [2000, 95],
      [3000, 165],
    ]);
    const leave = feed(counter, [[4000, 145]]);
    expect(at(leave, 0).state).toBe('moving_out');
    expect(counter.getReps()[0]?.pause_top_ms).toBe(1000);

    const back = feed(counter, [[5000, 170]]);
    expect(at(back, 0).state).toBe('at_start');
    expect(at(back, 0).rep_count).toBe(1);
    expect(counter.getReps()[0]?.pause_top_ms).toBe(0);
  });

  it('POSE-11 CURL: nhiễu quay về S đặt lại pause_bottom_ms của rep cuối về 0', () => {
    const counter = createRepCounter(CURL);
    feed(counter, [
      [0, 160],
      [1000, 140],
      [2000, 55],
      [3000, 155],
    ]);
    const leave = feed(counter, [[4000, 140]]);
    expect(at(leave, 0).state).toBe('moving_out');
    expect(counter.getReps()[0]?.pause_bottom_ms).toBe(1000);

    const back = feed(counter, [[5000, 160]]);
    expect(at(back, 0).state).toBe('at_start');
    expect(at(back, 0).rep_count).toBe(1);
    expect(counter.getReps()[0]?.pause_bottom_ms).toBe(0);
  });

  // Giá trị pha của (b) và (c) chốt theo spec §2.5 (người dùng chọn phương án A cho Q1 ngày 28/11/2026):
  // tTurn = leaveS = 1000 nên phase1 = 0, phase2 = 1000. Kỳ vọng "1000 + 1000" ở spec §5 lệch §2.5.
  it('POSE-11 (b) SQ: mẫu bằng partial_deg được tính là rep thiếu biên độ', () => {
    const updates = feed(createRepCounter(SQ), [
      [0, 170],
      [1000, 130],
      [2000, 170],
    ]);
    const last = at(updates, 2);
    expect(last.completed_rep).toMatchObject({
      rep_no: 1,
      start_offset_ms: 1000,
      eccentric_ms: 0,
      pause_bottom_ms: 0,
      concentric_ms: 1000,
      min_joint_angle_deg: 130,
      max_joint_angle_deg: 170,
      is_full_rom: false,
    });
    expect(last.partial_mistake_code).toBe('SQUAT_SHALLOW_DEPTH');
    expect(last.rep_count).toBe(1);
  });

  it('POSE-11 (c) DL: rep thiếu biên độ, partial_mistake_code null', () => {
    const updates = feed(createRepCounter(DL), [
      [0, 90],
      [1000, 130],
      [2000, 95],
    ]);
    const last = at(updates, 2);
    expect(last.completed_rep).toMatchObject({
      rep_no: 1,
      start_offset_ms: 1000,
      concentric_ms: 0,
      pause_top_ms: 0,
      eccentric_ms: 1000,
      min_joint_angle_deg: 95,
      max_joint_angle_deg: 130,
      is_full_rom: false,
    });
    expect(last.partial_mistake_code).toBeNull();
  });

  it('POSE-11 tTurn là mẫu ĐẦU TIÊN có góc cực trị', () => {
    const updates = feed(createRepCounter(SQ), [
      [0, 170],
      [1000, 140],
      [2000, 125],
      [3000, 125],
      [4000, 150],
      [5000, 170],
    ]);
    expect(at(updates, 5).completed_rep).toMatchObject({
      eccentric_ms: 1000,
      pause_bottom_ms: 0,
      concentric_ms: 3000,
      min_joint_angle_deg: 125,
      max_joint_angle_deg: 170,
      is_full_rom: false,
    });
  });

  it('POSE-11 DL: dao động chưa vượt partial là nhiễu, không đếm', () => {
    const updates = feed(createRepCounter(DL), [
      [0, 90],
      [1000, 129.9],
      [2000, 95],
    ]);
    expect(at(updates, 2).state).toBe('at_start');
    expect(at(updates, 2).completed_rep).toBeNull();
    expect(at(updates, 2).rep_count).toBe(0);
  });
});

describe('createRepCounter: mẫu không hợp lệ, reset, ngưỡng sai', () => {
  const POSE_12_SAMPLES: Pair[] = [
    [0, null],
    [100, 170],
    [1100, 150],
    [2100, 95],
    [2200, NaN],
    [2300, Infinity],
    [2400, -0.1],
    [2500, 180.1],
    [2000, 170],
    [3100, 165],
  ];

  // concentric_ms của mẫu (3100) chốt theo spec §2.5 ý 4 (người dùng chọn phương án A cho Q1 ngày
  // 28/11/2026): đi thẳng O → S nên leaveO = enterS = 3100, concentric_ms = 0. Kỳ vọng 1000 ở spec §5 lệch §2.5.
  it('POSE-12 (a) mẫu lỗi bị bỏ qua, không đổi trạng thái hay mốc thời gian', () => {
    const updates = feed(createRepCounter(SQ), POSE_12_SAMPLES);
    expect(at(updates, 0).state).toBe('idle');
    updates.slice(4, 9).forEach((u) => {
      expect(u.state).toBe('at_end');
      expect(u.phase).toBe('bottom');
      expect(u.completed_rep).toBeNull();
      expect(u.partial_mistake_code).toBeNull();
      expect(u.rep_count).toBe(0);
    });
    expect(at(updates, 9).completed_rep).toMatchObject({
      start_offset_ms: 1000,
      eccentric_ms: 1000,
      pause_bottom_ms: 1000,
      concentric_ms: 0,
      min_joint_angle_deg: 95,
      max_joint_angle_deg: 165,
    });
  });

  it('POSE-12 (a) t_ms không hữu hạn bị bỏ qua; t_ms bằng mẫu trước vẫn nhận', () => {
    const updates = feed(createRepCounter(SQ), [
      [100, 170],
      [NaN, 150],
      [Infinity, 150],
      [100, 150],
    ]);
    expect(updates.map((u) => u.state)).toEqual(['at_start', 'at_start', 'at_start', 'moving_out']);
  });

  it('POSE-12 (b) góc 0 và 180 được nhận', () => {
    const counter = createRepCounter(SQ);
    expect(counter.update({ t_ms: 0, angle_deg: 0 }).state).toBe('idle');
    expect(counter.update({ t_ms: 100, angle_deg: 180 }).state).toBe('at_start');
    expect(counter.update({ t_ms: 200, angle_deg: 0 }).state).toBe('at_end');
  });

  it('POSE-12 (b) mẫu idle đầu tiên đặt t0 cho start_offset', () => {
    const updates = feed(createRepCounter(SQ), [
      [0, 0],
      [100, 180],
      [500, 90],
      [900, 170],
    ]);
    expect(at(updates, 3).completed_rep).toMatchObject({ start_offset_ms: 500 });
  });

  it('POSE-12 (c) reset xoá rep, t0 và đưa về idle', () => {
    const counter = createRepCounter(SQ);
    feed(counter, POSE_12_SAMPLES);
    counter.reset();
    expect(counter.getReps()).toEqual([]);
    const update = counter.update({ t_ms: 5000, angle_deg: 170 });
    expect(update.state).toBe('at_start');
    expect(update.rep_count).toBe(0);

    // t0 mới là 5000, nên start_offset của rep đầu sau reset tính từ 5000.
    const after = feed(counter, [
      [6000, 90],
      [7000, 170],
    ]);
    expect(at(after, 1).completed_rep).toMatchObject({ rep_no: 1, start_offset_ms: 1000 });
  });

  it('POSE-12 (d) ngưỡng sai ném RangeError', () => {
    const broken: Partial<RepRule>[] = [
      { flexed_deg: 160 },
      { partial_deg: 100 },
      { partial_deg: 160 },
      { extended_deg: 181 },
      { flexed_deg: NaN },
    ];
    broken.forEach((patch) => {
      expect(() => createRepCounter({ ...SQ, ...patch })).toThrow(RangeError);
    });
  });

  it('POSE-12 (d) ngưỡng âm hoặc vô hạn ném RangeError; ngưỡng biên 0 và 180 hợp lệ', () => {
    expect(() => createRepCounter({ ...SQ, flexed_deg: -1 })).toThrow(RangeError);
    expect(() => createRepCounter({ ...SQ, extended_deg: Infinity })).toThrow(RangeError);
    expect(() => createRepCounter({ ...SQ, flexed_deg: 0, extended_deg: 180 })).not.toThrow();
  });
});
