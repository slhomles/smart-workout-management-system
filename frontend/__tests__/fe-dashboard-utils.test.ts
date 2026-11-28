import {
  bmiCategoryLabel,
  formatDayMonth,
  lastDayOfPeriod,
  previousWeekStart,
  recoveryStatusLabel,
  weightChartPoints,
  weightExtremes,
} from '@/screens/dashboard/report-utils';
import type { WeightTrendPoint } from '@/types/dashboard';

describe('report-utils (spec fe-dashboard §2.3)', () => {
  it.each([
    ['Chủ nhật 29/11/2026 09:00', new Date(2026, 10, 29, 9, 0), '2026-11-16'],
    ['Thứ Hai 30/11/2026 00:05', new Date(2026, 10, 30, 0, 5), '2026-11-23'],
    ['Thứ Sáu 01/01/2027 12:00 (qua năm)', new Date(2027, 0, 1, 12, 0), '2026-12-21'],
    ['Thứ Hai 23/11/2026 00:30', new Date(2026, 10, 23, 0, 30), '2026-11-16'],
  ])('FEDASH-01 previousWeekStart %s → %s', (_label, today, expected) => {
    expect(previousWeekStart(today)).toBe(expected);
  });

  it('FEDASH-01 previousWeekStart sát nửa đêm vẫn tính theo giờ địa phương', () => {
    expect(previousWeekStart(new Date(2026, 10, 29, 23, 59))).toBe('2026-11-16');
    expect(previousWeekStart(new Date(2026, 2, 2, 0, 0))).toBe('2026-02-23');
  });

  it('FEDASH-01 previousWeekStart không đổi Date truyền vào', () => {
    const today = new Date(2026, 10, 29, 9, 0);
    previousWeekStart(today);
    expect(today.getTime()).toBe(new Date(2026, 10, 29, 9, 0).getTime());
  });

  it.each([
    ['2026-11-23', '2026-11-22'],
    ['2027-01-01', '2026-12-31'],
    ['2028-03-01', '2028-02-29'],
    ['2027-03-01', '2027-02-28'],
  ])('FEDASH-01 lastDayOfPeriod(%s) → %s', (periodEnd, expected) => {
    expect(lastDayOfPeriod(periodEnd)).toBe(expected);
  });

  it('FEDASH-01 lastDayOfPeriod xử lý năm chia hết cho 100/400 và đầu tháng 30 ngày', () => {
    expect(lastDayOfPeriod('2100-03-01')).toBe('2100-02-28');
    expect(lastDayOfPeriod('2000-03-01')).toBe('2000-02-29');
    expect(lastDayOfPeriod('2026-12-01')).toBe('2026-11-30');
  });

  it.each(['abc', '', '2026-13-01', '2026-02-30', '26-11-23'])(
    'FEDASH-01 lastDayOfPeriod giữ nguyên chuỗi sai dạng "%s"',
    (text) => {
      expect(lastDayOfPeriod(text)).toBe(text);
    },
  );

  it('FEDASH-01 formatDayMonth yyyy-mm-dd → dd/mm, sai dạng giữ nguyên', () => {
    expect(formatDayMonth('2026-11-02')).toBe('02/11');
    expect(formatDayMonth('abc')).toBe('abc');
    expect(formatDayMonth('')).toBe('');
    expect(formatDayMonth('2026-11-02T00:00:00Z')).toBe('2026-11-02T00:00:00Z');
  });

  it('FEDASH-01 bmiCategoryLabel đổi mã phân loại sang nhãn tiếng Việt', () => {
    expect(bmiCategoryLabel('underweight')).toBe('Thiếu cân');
    expect(bmiCategoryLabel('normal')).toBe('Bình thường');
    expect(bmiCategoryLabel('overweight')).toBe('Thừa cân');
    expect(bmiCategoryLabel('obese')).toBe('Béo phì');
    expect(bmiCategoryLabel(null)).toBe('');
  });

  it('FEDASH-01 bmiCategoryLabel giá trị lạ trả chuỗi rỗng', () => {
    expect(bmiCategoryLabel('morbid')).toBe('');
    expect(bmiCategoryLabel('')).toBe('');
    expect(bmiCategoryLabel('toString')).toBe('');
  });

  it('FEDASH-01 recoveryStatusLabel đổi trạng thái phục hồi sang nhãn tiếng Việt', () => {
    expect(recoveryStatusLabel('fatigued')).toBe('Mệt mỏi');
    expect(recoveryStatusLabel('recovering')).toBe('Đang hồi phục');
    expect(recoveryStatusLabel('ready')).toBe('Sẵn sàng');
  });
});

function weekPoint(weekStart: string, weights: { avg: number | null; min: number | null; max: number | null }): WeightTrendPoint {
  return {
    week_start: weekStart,
    avg_weight_kg: weights.avg,
    min_weight_kg: weights.min,
    max_weight_kg: weights.max,
    avg_body_fat_pct: null,
    measurement_count: weights.avg === null ? 0 : 2,
    change_kg: null,
    is_plateau: false,
    sessions_completed: 0,
    est_calories_burned_kcal: 0,
  };
}

const MIXED_POINTS = [
  weekPoint('2026-11-02', { avg: 71.2, min: 70.9, max: 71.5 }),
  weekPoint('2026-11-09', { avg: null, min: null, max: null }),
  weekPoint('2026-11-16', { avg: 70.4, min: 69.8, max: 70.6 }),
];

describe('report-utils: cân nặng (spec fe-dashboard §2.2 ý 4)', () => {
  it('FEDASH-07 weightExtremes lấy max của max_weight_kg và min của min_weight_kg, bỏ tuần null', () => {
    expect(weightExtremes(MIXED_POINTS)).toEqual({ heaviestKg: 71.5, lightestKg: 69.8 });
  });

  it('FEDASH-08 weightExtremes không có điểm hoặc mọi giá trị null thì trả null', () => {
    expect(weightExtremes([])).toEqual({ heaviestKg: null, lightestKg: null });
    expect(weightExtremes([MIXED_POINTS[1] as WeightTrendPoint])).toEqual({ heaviestKg: null, lightestKg: null });
  });

  it('FEDASH-07 weightChartPoints (metric) bỏ tuần không có avg_weight_kg, nhãn dd/mm, giá trị kg', () => {
    expect(weightChartPoints(MIXED_POINTS, 'metric')).toEqual([
      { label: '02/11', value: 71.2 },
      { label: '16/11', value: 70.4 },
    ]);
    expect(weightChartPoints(MIXED_POINTS, null)).toEqual(weightChartPoints(MIXED_POINTS, 'metric'));
    expect(weightChartPoints([], 'metric')).toEqual([]);
  });

  it('FEDASH-07 weightChartPoints (imperial) đổi giá trị sang lb', () => {
    const [first] = weightChartPoints(MIXED_POINTS, 'imperial');
    expect(first?.label).toBe('02/11');
    expect(first?.value).toBeCloseTo(156.969, 3);
  });
});
