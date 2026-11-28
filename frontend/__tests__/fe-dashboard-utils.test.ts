import {
  bmiCategoryLabel,
  formatDayMonth,
  lastDayOfPeriod,
  previousWeekStart,
  recoveryStatusLabel,
} from '@/screens/dashboard/report-utils';

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
