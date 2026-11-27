/**
 * Lỗi của form Đổi mật khẩu: kiểm tra phía client và quy lỗi `PATCH /auth/change-password` về thông điệp
 * (doc 04 §4.7, §6.1; spec fe-auth §2.4). Mã lỗi đã đăng ký ở Claude_api_respone.md §10, §10.1.
 */
import { toFormErrors, type FormErrors } from '@/screens/auth/form-errors';
import type { ChangePasswordRequest } from '@/types/auth';
import {
  checkPasswordPolicy,
  PASSWORD_MISMATCH_MESSAGE,
  PASSWORD_REQUIRED_MESSAGE,
} from '@/utils/validation';

/** Field của API (`ChangePasswordRequest`); `new_password_confirm` chỉ có ở client và KHÔNG được gửi. */
export type ChangePasswordField = 'current_password' | 'new_password' | 'new_password_confirm';
export type ChangePasswordInput = Record<ChangePasswordField, string>;
export type ChangePasswordValidation = {
  errors: FormErrors<ChangePasswordField>;
  body: ChangePasswordRequest;
};

const CHANGE_PASSWORD_API_FIELDS: readonly ChangePasswordField[] = ['current_password', 'new_password'];
const INVALID_CREDENTIALS = 'invalid_credentials';

/** Trả mọi lỗi client cùng lúc. Mật khẩu KHÔNG trim: khoảng trắng là một phần của mật khẩu. */
export function validateChangePassword(input: ChangePasswordInput): ChangePasswordValidation {
  const fields: Partial<Record<ChangePasswordField, string>> = {};
  if (input.current_password.length === 0) fields.current_password = PASSWORD_REQUIRED_MESSAGE;
  const policyError = checkPasswordPolicy(input.new_password);
  if (policyError) fields.new_password = policyError;
  if (input.new_password_confirm !== input.new_password)
    fields.new_password_confirm = PASSWORD_MISMATCH_MESSAGE;
  return {
    errors: { fields, form: null },
    body: { current_password: input.current_password, new_password: input.new_password },
  };
}

/** Sai mật khẩu hiện tại là 401 `invalid_credentials` (doc 04 §4.7): hiện dưới ô Mật khẩu hiện tại. */
export function toChangePasswordErrors(err: unknown): FormErrors<ChangePasswordField> {
  return toFormErrors<ChangePasswordField>(err, {
    fields: CHANGE_PASSWORD_API_FIELDS,
    messages: { [INVALID_CREDENTIALS]: 'Mật khẩu hiện tại không đúng' },
    fieldOf: { [INVALID_CREDENTIALS]: 'current_password' },
  });
}
