/**
 * Logic thuần của form Ghi cân nặng (spec fe-dashboard §2.2 "Ghi cân nặng", §2.4, §6 ý 8, 9): kiểm tra phía client,
 * dựng body `POST /body/measurements` và quy lỗi server về thông điệp. Giới hạn theo CHECK của `05_body.sql`.
 */
import { hasFormErrors, toFormErrors, type FormErrors } from '@/screens/auth/form-errors';
import { toTargetWeightKg } from '@/screens/profile/new-goal-form';
import type { UnitSystem } from '@/types/auth';
import type { CreateMeasurementRequest } from '@/types/dashboard';
import { parseDecimalVi } from '@/utils/format';

/** Field của API có ô trên form. */
export type RecordWeightField = 'weight_kg' | 'body_fat_pct';
/** Giá trị đang nhập: cân nặng theo `unit_system` (kg hoặc lb), % mỡ tuỳ chọn. */
export type RecordWeightInput = { weight: string; body_fat: string };
export type RecordWeightValidation = { errors: FormErrors<RecordWeightField>; body: CreateMeasurementRequest | null };

const WEIGHT_RANGE_MESSAGE = 'Cân nặng phải từ 20 đến 400 kg';
const BODY_FAT_RANGE_MESSAGE = 'Tỷ lệ mỡ phải từ 2 đến 70%';
const MEASUREMENT_ALREADY_EXISTS = 'measurement_already_exists';
const MEASUREMENT_ALREADY_EXISTS_MESSAGE = 'Đã có lần đo tại thời điểm này';

export const EMPTY_RECORD_WEIGHT_INPUT: RecordWeightInput = { weight: '', body_fat: '' };

const RECORD_WEIGHT_FIELDS: readonly RecordWeightField[] = ['weight_kg', 'body_fat_pct'];
// CHECK của `body_measurements` (05_body.sql): cân nặng 20–400 kg, % mỡ 2–70 (spec §6 ý 8).
const MIN_WEIGHT_KG = 20;
const MAX_WEIGHT_KG = 400;
const MIN_BODY_FAT_PCT = 2;
const MAX_BODY_FAT_PCT = 70;

type FieldCheck = { value?: number; error?: string };

function isWithin(value: number, min: number, max: number): boolean {
  return value >= min && value <= max;
}

// Cùng quy tắc với cân nặng mục tiêu: đổi lb sang kg rồi làm tròn 2 chữ số (`numeric(5,2)`); kiểm khoảng trên
// giá trị đã làm tròn vì đó là giá trị gửi lên server. Ô bắt buộc nên rỗng cũng là lỗi.
function checkWeight(text: string, unitSystem: UnitSystem): FieldCheck {
  const kg = toTargetWeightKg(text, unitSystem);
  if (kg === null || !isWithin(kg, MIN_WEIGHT_KG, MAX_WEIGHT_KG)) return { error: WEIGHT_RANGE_MESSAGE };
  return { value: kg };
}

/** Ô trống thì không có `value` lẫn `error`: không gửi key `body_fat_pct` (spec §2.2). */
function checkBodyFat(text: string): FieldCheck {
  const trimmed = text.trim();
  if (trimmed === '') return {};
  const parsed = parseDecimalVi(trimmed);
  // Làm tròn 1 chữ số theo cột `numeric(4,1)`.
  const pct = parsed === null ? null : Math.round(parsed * 10) / 10;
  if (pct === null || !isWithin(pct, MIN_BODY_FAT_PCT, MAX_BODY_FAT_PCT)) return { error: BODY_FAT_RANGE_MESSAGE };
  return { value: pct };
}

/** Trả mọi lỗi client cùng lúc; `body` chỉ có khi không còn lỗi. Không bao giờ gửi `measured_at` (spec §6 ý 9). */
export function validateRecordWeight(input: RecordWeightInput, unitSystem: UnitSystem): RecordWeightValidation {
  const weight = checkWeight(input.weight, unitSystem);
  const bodyFat = checkBodyFat(input.body_fat);
  const fields: Partial<Record<RecordWeightField, string>> = {};
  if (weight.error) fields.weight_kg = weight.error;
  if (bodyFat.error) fields.body_fat_pct = bodyFat.error;
  const errors: FormErrors<RecordWeightField> = { fields, form: null };
  if (weight.value === undefined || hasFormErrors(errors)) return { errors, body: null };
  const body: CreateMeasurementRequest = { weight_kg: weight.value };
  if (bodyFat.value !== undefined) body.body_fat_pct = bodyFat.value;
  return { errors, body };
}

/** 409 hiện thông điệp chung; 422 hiện dưới ô theo `details[].field`; 403 và lỗi mạng do `toFormErrors` xử lý. */
export function toRecordWeightErrors(err: unknown): FormErrors<RecordWeightField> {
  return toFormErrors<RecordWeightField>(err, {
    fields: RECORD_WEIGHT_FIELDS,
    messages: { [MEASUREMENT_ALREADY_EXISTS]: MEASUREMENT_ALREADY_EXISTS_MESSAGE },
  });
}
