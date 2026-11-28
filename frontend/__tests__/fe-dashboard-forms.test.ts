import { initialHeightText, toHeightErrors, validateHeight } from '@/screens/dashboard/height-form';
import { toRecordWeightErrors, validateRecordWeight } from '@/screens/dashboard/record-weight-form';

import { apiError, networkError, PROFILE_DEMO, PROFILE_NEWBIE } from '../test-utils/fe-dashboard-fixtures';

// Chuỗi kỳ vọng chép nguyên từ spec fe-dashboard §2.4 (không dùng lại hằng của code để bắt lỗi chính tả).
const WEIGHT_RANGE = 'Cân nặng phải từ 20 đến 400 kg';
const BODY_FAT_RANGE = 'Tỷ lệ mỡ phải từ 2 đến 70%';
const HEIGHT_RANGE = 'Chiều cao phải từ 80 đến 250 cm';

describe('validateRecordWeight', () => {
  it.each([
    { weight: '20', unit: 'metric', kg: 20 },
    { weight: '400', unit: 'metric', kg: 400 },
    // Kiểm khoảng sau khi làm tròn 2 chữ số: 400,004 gửi lên là 400.
    { weight: '400,004', unit: 'metric', kg: 400 },
    { weight: ' 70,5 ', unit: 'metric', kg: 70.5 },
    // 44,1 lb = 20,003 kg → 20.
    { weight: '44,1', unit: 'imperial', kg: 20 },
  ] as const)('FEDASH-19 cân nặng "$weight" ($unit) hợp lệ → weight_kg $kg, không có body_fat_pct', ({ weight, unit, kg }) => {
    const result = validateRecordWeight({ weight, body_fat: '  ' }, unit);

    expect(result.errors).toStrictEqual({ fields: {}, form: null });
    expect(result.body).toStrictEqual({ weight_kg: kg });
  });

  it.each([
    { body_fat: '2', pct: 2 },
    { body_fat: '70', pct: 70 },
    { body_fat: '18,24', pct: 18.2 },
    { body_fat: '70,04', pct: 70 },
  ])('FEDASH-19 % mỡ "$body_fat" hợp lệ → body_fat_pct $pct (làm tròn 1 chữ số)', ({ body_fat, pct }) => {
    expect(validateRecordWeight({ weight: '70', body_fat }, 'metric').body).toStrictEqual({ weight_kg: 70, body_fat_pct: pct });
  });

  it.each([
    { weight: '19,99', unit: 'metric' },
    { weight: '400,01', unit: 'metric' },
    { weight: '-70', unit: 'metric' },
    { weight: '70,5kg', unit: 'metric' },
    { weight: '   ', unit: 'metric' },
    // 44 lb = 19,96 kg.
    { weight: '44', unit: 'imperial' },
    { weight: '882', unit: 'imperial' },
  ] as const)('FEDASH-20 cân nặng "$weight" ($unit) sai → lỗi dưới ô Cân nặng, không có body', ({ weight, unit }) => {
    const result = validateRecordWeight({ weight, body_fat: '' }, unit);

    expect(result.errors).toStrictEqual({ fields: { weight_kg: WEIGHT_RANGE }, form: null });
    expect(result.body).toBeNull();
  });

  it.each(['1,9', '70,1', 'abc', '-5'])('FEDASH-20 % mỡ "%s" sai → lỗi dưới ô Tỷ lệ mỡ, không có body', (bodyFat) => {
    const result = validateRecordWeight({ weight: '70', body_fat: bodyFat }, 'metric');

    expect(result.errors).toStrictEqual({ fields: { body_fat_pct: BODY_FAT_RANGE }, form: null });
    expect(result.body).toBeNull();
  });

  it('FEDASH-20 báo cả hai lỗi cùng lúc', () => {
    const result = validateRecordWeight({ weight: '15', body_fat: '1' }, 'metric');

    expect(result.errors.fields).toStrictEqual({ weight_kg: WEIGHT_RANGE, body_fat_pct: BODY_FAT_RANGE });
    expect(result.body).toBeNull();
  });
});

describe('toRecordWeightErrors', () => {
  it('FEDASH-20 quy lỗi server theo error.code', () => {
    expect(toRecordWeightErrors(apiError(409, 'measurement_already_exists'))).toStrictEqual({
      fields: {},
      form: 'Đã có lần đo tại thời điểm này',
    });
    const details = [
      { field: 'weight_kg', message: 'Cân nặng không hợp lệ', code: 'value_error' },
      { field: 'body_fat_pct', message: 'Tỷ lệ mỡ không hợp lệ', code: 'value_error' },
    ];
    expect(toRecordWeightErrors(apiError(422, 'validation_error', details))).toStrictEqual({
      fields: { weight_kg: 'Cân nặng không hợp lệ', body_fat_pct: 'Tỷ lệ mỡ không hợp lệ' },
      form: null,
    });
    expect(toRecordWeightErrors(apiError(403, 'permission_denied')).form).toBe('Bạn không có quyền thực hiện thao tác này');
    expect(toRecordWeightErrors(networkError()).form).toBe('Không kết nối được máy chủ');
  });
});

describe('initialHeightText', () => {
  it('FEDASH-21 điền sẵn theo vi-VN, chưa có chiều cao thì để trống', () => {
    expect(initialHeightText(PROFILE_DEMO)).toBe('172');
    expect(initialHeightText({ ...PROFILE_DEMO, height_cm: 172.5 })).toBe('172,5');
    expect(initialHeightText(PROFILE_NEWBIE)).toBe('');
  });
});

describe('validateHeight', () => {
  it.each([
    { text: '80', cm: 80 },
    { text: '250', cm: 250 },
    { text: '172,54', cm: 172.5 },
    { text: '250,04', cm: 250 },
    { text: '172.5', cm: 172.5 },
  ])('FEDASH-21 "$text" hợp lệ → height_cm $cm, giữ nguyên 4 field khác, không có updated_at', ({ text, cm }) => {
    const result = validateHeight(text, PROFILE_DEMO);

    expect(result.errors).toStrictEqual({ fields: {}, form: null });
    expect(result.body).toStrictEqual({
      gender: 'male',
      date_of_birth: '2003-05-10',
      height_cm: cm,
      activity_level_id: 3,
      experience_level_id: 1,
    });
  });

  it.each(['79,9', '250,1', '', 'abc', '-170', '1,7m'])('FEDASH-22 "%s" sai → lỗi dưới ô Chiều cao, không có body', (text) => {
    const result = validateHeight(text, PROFILE_NEWBIE);

    expect(result.errors).toStrictEqual({ fields: { height_cm: HEIGHT_RANGE }, form: null });
    expect(result.body).toBeNull();
  });
});

describe('toHeightErrors', () => {
  it('FEDASH-22 quy lỗi server theo error.code', () => {
    const details = [{ field: 'height_cm', message: 'Chiều cao không hợp lệ', code: 'value_error' }];
    expect(toHeightErrors(apiError(422, 'validation_error', details))).toStrictEqual({
      fields: { height_cm: 'Chiều cao không hợp lệ' },
      form: null,
    });
    expect(toHeightErrors(apiError(403, 'permission_denied'))).toStrictEqual({
      fields: {},
      form: 'Bạn không có quyền thực hiện thao tác này',
    });
    expect(toHeightErrors(networkError()).form).toBe('Không kết nối được máy chủ');
  });
});
