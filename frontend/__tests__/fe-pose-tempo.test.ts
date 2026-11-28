import {
  correctFormPct,
  createRepCounter,
  summarizeTempo,
  type RepEvent,
  type RepRule,
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

type Pair = [number, number];

function feed(counter: ReturnType<typeof createRepCounter>, pairs: Pair[]): void {
  pairs.forEach(([t_ms, angle_deg]) => counter.update({ t_ms, angle_deg }));
}

function firstRep(reps: RepEvent[]): RepEvent {
  const rep = reps[0];
  if (rep === undefined) throw new Error('không có rep 1');
  return rep;
}

/** Rep chỉ đặt các field `summarizeTempo` dùng; phần còn lại là giá trị trung tính. */
function rep(phases: [number, number, number, number], isFullRom: boolean): RepEvent {
  const [eccentric_ms, pause_bottom_ms, concentric_ms, pause_top_ms] = phases;
  return {
    rep_no: 1,
    start_offset_ms: 0,
    eccentric_ms,
    pause_bottom_ms,
    concentric_ms,
    pause_top_ms,
    min_joint_angle_deg: null,
    max_joint_angle_deg: null,
    is_full_rom: isFullRom,
  };
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

const REP_1_DONE: RepEvent = {
  rep_no: 1,
  start_offset_ms: 1000,
  eccentric_ms: 3000,
  pause_bottom_ms: 500,
  concentric_ms: 1000,
  pause_top_ms: 0,
  min_joint_angle_deg: 90,
  max_joint_angle_deg: 165,
  is_full_rom: true,
};

describe('createRepCounter + summarizeTempo: hai rep', () => {
  it('POSE-08 SQ: pause_top_ms của rep 1 cập nhật khi rep 2 rời S, rep 2 và tempo đúng', () => {
    const counter = createRepCounter(SQ);
    feed(counter, POSE_07_SAMPLES);
    expect(counter.getReps()).toEqual([REP_1_DONE]);

    feed(counter, [
      [6500, 170],
      [7000, 150],
    ]);
    expect(firstRep(counter.getReps()).pause_top_ms).toBe(1500);

    feed(counter, [
      [8000, 98],
      [8300, 120],
    ]);
    const last = counter.update({ t_ms: 9000, angle_deg: 162 });
    const reps = counter.getReps();

    expect(last.rep_count).toBe(2);
    expect(reps).toEqual([
      { ...REP_1_DONE, pause_top_ms: 1500 },
      {
        rep_no: 2,
        start_offset_ms: 7000,
        eccentric_ms: 1000,
        pause_bottom_ms: 300,
        concentric_ms: 700,
        pause_top_ms: 0,
        min_joint_angle_deg: 98,
        max_joint_angle_deg: 162,
        is_full_rom: true,
      },
    ]);
    expect(summarizeTempo(reps)).toEqual({
      rep_count: 2,
      avg_eccentric_ms: 2000,
      avg_pause_bottom_ms: 400,
      avg_concentric_ms: 850,
      avg_pause_top_ms: 750,
      time_under_tension_ms: 8000,
      full_rom_pct: 100,
    });
  });

  it('POSE-08 getReps trả bản sao: sửa mảng hoặc phần tử trả về không đổi lần gọi sau', () => {
    const counter = createRepCounter(SQ);
    feed(counter, POSE_07_SAMPLES);

    const copy = counter.getReps();
    copy.push({ ...REP_1_DONE, rep_no: 99 });
    firstRep(copy).eccentric_ms = 1;
    copy.splice(0, 1);

    expect(counter.getReps()).toEqual([REP_1_DONE]);
  });
});

describe('summarizeTempo', () => {
  it('POSE-14 (a) 3 rep: trung bình làm tròn, TUT là tổng 4 pha, full_rom_pct 1 chữ số', () => {
    const reps = [
      rep([3000, 200, 1000, 300], true),
      rep([2901, 100, 1100, 300], true),
      rep([2000, 0, 901, 0], false),
    ];

    expect(summarizeTempo(reps)).toEqual({
      rep_count: 3,
      avg_eccentric_ms: 2634,
      avg_pause_bottom_ms: 100,
      avg_concentric_ms: 1000,
      avg_pause_top_ms: 200,
      time_under_tension_ms: 11802,
      full_rom_pct: 66.7,
    });
  });

  it('POSE-14 (b) trung bình 1000,5 làm tròn lên 1001 như round() của PostgreSQL', () => {
    const reps = [rep([1000, 0, 0, 0], true), rep([1001, 0, 0, 0], true)];

    expect(summarizeTempo(reps)).toEqual({
      rep_count: 2,
      avg_eccentric_ms: 1001,
      avg_pause_bottom_ms: 0,
      avg_concentric_ms: 0,
      avg_pause_top_ms: 0,
      time_under_tension_ms: 2001,
      full_rom_pct: 100,
    });
  });

  it('POSE-14 (c) mảng rỗng trả null', () => {
    expect(summarizeTempo([])).toBeNull();
  });
});

describe('correctFormPct', () => {
  it('POSE-15 evaluated = 0 trả null', () => {
    expect(correctFormPct(0, 0)).toBeNull();
  });

  it('POSE-15 phần trăm frame đúng form làm tròn 2 chữ số', () => {
    expect(correctFormPct(10, 0)).toBe(100);
    expect(correctFormPct(3, 1)).toBe(66.67);
    expect(correctFormPct(3, 3)).toBe(0);
  });

  it('POSE-15 tham số sai hoặc violating > evaluated ném RangeError', () => {
    expect(() => correctFormPct(2, 3)).toThrow(RangeError);
    expect(() => correctFormPct(-1, 0)).toThrow(RangeError);
    expect(() => correctFormPct(2.5, 1)).toThrow(RangeError);
    expect(() => correctFormPct(3, NaN)).toThrow(RangeError);
  });
});
