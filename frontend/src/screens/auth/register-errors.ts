/**
 * Lỗi của form đăng ký: kiểm tra phía client và quy lỗi `POST /auth/register` về thông điệp (spec fe-auth §2.4).
 * Mã lỗi đã đăng ký ở Claude_api_respone.md §10.
 */
import type { RegisterRequest } from '@/types/auth';
import {
  checkDisplayName,
  checkFullName,
  checkPasswordPolicy,
  EMAIL_MESSAGE,
  isValidEmail,
  PASSWORD_MISMATCH_MESSAGE,
} from '@/utils/validation';

import { toFormErrors, type FormErrors } from './form-errors';

/** Field của API (`RegisterRequest`); `password_confirm` chỉ có ở client và KHÔNG được gửi (backend `extra="forbid"`). */
export type RegisterField = 'email' | 'display_name' | 'full_name' | 'password' | 'password_confirm';
export type RegisterInput = Record<RegisterField, string>;

const REGISTER_API_FIELDS: readonly RegisterField[] = ['email', 'display_name', 'full_name', 'password'];
const EMAIL_ALREADY_EXISTS = 'email_already_exists';

export type RegisterValidation = { errors: FormErrors<RegisterField>; body: RegisterRequest };

/** Trả mọi lỗi client cùng lúc và body đã chuẩn hoá (trim, họ tên trống thành `null`) theo spec fe-auth §2.2. */
export function validateRegister(input: RegisterInput): RegisterValidation {
  const email = input.email.trim();
  const displayName = checkDisplayName(input.display_name);
  const fullName = checkFullName(input.full_name);
  const passwordError = checkPasswordPolicy(input.password);
  const fields: Partial<Record<RegisterField, string>> = {};
  if (!isValidEmail(email)) fields.email = EMAIL_MESSAGE;
  if (displayName.error) fields.display_name = displayName.error;
  if (fullName.error) fields.full_name = fullName.error;
  if (passwordError) fields.password = passwordError;
  if (input.password_confirm !== input.password) fields.password_confirm = PASSWORD_MISMATCH_MESSAGE;
  return {
    errors: { fields, form: null },
    body: { email, password: input.password, display_name: displayName.value, full_name: fullName.value },
  };
}

export function toRegisterErrors(err: unknown): FormErrors<RegisterField> {
  return toFormErrors<RegisterField>(err, {
    fields: REGISTER_API_FIELDS,
    messages: { [EMAIL_ALREADY_EXISTS]: 'Email đã được sử dụng' },
    fieldOf: { [EMAIL_ALREADY_EXISTS]: 'email' },
  });
}
