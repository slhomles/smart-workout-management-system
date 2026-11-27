/**
 * Logic thuần của form Hồ sơ (spec fe-auth §2.2 "Sửa hồ sơ", §2.4): kiểm tra phía client, tính các field đã đổi
 * và quy lỗi `PATCH /auth/me` về thông điệp. Giới hạn theo `UpdateMeRequest` của backend.
 */
import { toFormErrors, type FormErrors } from '@/screens/auth/form-errors';
import type { Me, UpdateMeRequest } from '@/types/auth';
import { checkDisplayName, checkFullName } from '@/utils/validation';

export type ProfileField = 'display_name' | 'full_name';
export type ProfileInput = Record<ProfileField, string>;
export type ProfileValidation = { errors: FormErrors<ProfileField>; changes: UpdateMeRequest };

const PROFILE_FIELDS: readonly ProfileField[] = ['display_name', 'full_name'];

export function initialProfileInput(me: Me): ProfileInput {
  return { display_name: me.display_name ?? '', full_name: me.full_name ?? '' };
}

/**
 * Trả mọi lỗi client cùng lúc và chỉ các field khác giá trị server: `display_name` đã trim,
 * `full_name` đã trim (trống thành `null` để xoá họ tên).
 */
export function validateProfile(input: ProfileInput, me: Me): ProfileValidation {
  const displayName = checkDisplayName(input.display_name);
  const fullName = checkFullName(input.full_name);
  const fields: Partial<Record<ProfileField, string>> = {};
  if (displayName.error) fields.display_name = displayName.error;
  if (fullName.error) fields.full_name = fullName.error;
  const changes: UpdateMeRequest = {};
  if (displayName.value !== me.display_name) changes.display_name = displayName.value;
  if (fullName.value !== me.full_name) changes.full_name = fullName.value;
  return { errors: { fields, form: null }, changes };
}

export function hasChanges(changes: UpdateMeRequest): boolean {
  return Object.keys(changes).length > 0;
}

export function toProfileErrors(err: unknown): FormErrors<ProfileField> {
  return toFormErrors<ProfileField>(err, { fields: PROFILE_FIELDS });
}
