/**
 * Logic thuần của form Chiều cao (spec fe-dashboard §2.2 "Chiều cao", §2.4, §6 ý 8, 10): điền sẵn từ
 * `GET /body/profile`, kiểm tra phía client, dựng body `PUT /body/profile` và quy lỗi server về thông điệp.
 */
import { hasFormErrors, toFormErrors, type FormErrors } from '@/screens/auth/form-errors';
import type { BodyProfile, ReplaceBodyProfileRequest } from '@/types/dashboard';
import { formatNumber, parseDecimalVi } from '@/utils/format';

/** Field của API có ô trên form. */
export type HeightField = 'height_cm';
export type HeightValidation = { errors: FormErrors<HeightField>; body: ReplaceBodyProfileRequest | null };

const HEIGHT_RANGE_MESSAGE = 'Chiều cao phải từ 80 đến 250 cm';
const HEIGHT_FIELDS: readonly HeightField[] = ['height_cm'];
// CHECK của `user_body_profiles` (05_body.sql): 80–250 cm (spec §6 ý 8).
const MIN_HEIGHT_CM = 80;
const MAX_HEIGHT_CM = 250;

/** Giá trị điền sẵn của ô: chiều cao luôn tính bằng cm (spec §6 ý 8, Q5); chưa có thì để trống. */
export function initialHeightText(profile: BodyProfile): string {
  return profile.height_cm === null ? '' : formatNumber(profile.height_cm, 1);
}

/** Làm tròn 1 chữ số theo cột `numeric(5,1)`; không phải số thì `null`. */
function toHeightCm(text: string): number | null {
  const value = parseDecimalVi(text);
  return value === null ? null : Math.round(value * 10) / 10;
}

/**
 * PUT thay toàn bộ hồ sơ nên gửi đủ 5 field: giữ nguyên các field khác của `profile`, chỉ thay `height_cm`
 * (spec §6 ý 10). Liệt kê từng field để không gửi kèm `updated_at`.
 */
export function validateHeight(text: string, profile: BodyProfile): HeightValidation {
  const heightCm = toHeightCm(text);
  const isValid = heightCm !== null && heightCm >= MIN_HEIGHT_CM && heightCm <= MAX_HEIGHT_CM;
  const errors: FormErrors<HeightField> = { fields: isValid ? {} : { height_cm: HEIGHT_RANGE_MESSAGE }, form: null };
  if (heightCm === null || hasFormErrors(errors)) return { errors, body: null };
  const body: ReplaceBodyProfileRequest = {
    gender: profile.gender,
    date_of_birth: profile.date_of_birth,
    height_cm: heightCm,
    activity_level_id: profile.activity_level_id,
    experience_level_id: profile.experience_level_id,
  };
  return { errors, body };
}

/** 422 hiện dưới ô theo `details[].field`; 403 và lỗi mạng hiện thông điệp chung do `toFormErrors` xử lý. */
export function toHeightErrors(err: unknown): FormErrors<HeightField> {
  return toFormErrors<HeightField>(err, { fields: HEIGHT_FIELDS });
}
