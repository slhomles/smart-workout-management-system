/**
 * Lỗi của form đăng nhập: kiểm tra phía client và quy lỗi `POST /auth/login` về thông điệp (spec fe-auth §2.4).
 * Mã lỗi đã đăng ký ở Claude_api_respone.md §10.1, §11.
 */
import { isAxiosError } from 'axios';

import { getErrorCode, type ApiErrorBody } from '@/services/api/errors';
import { formatRetryAfter } from '@/utils/format';
import { EMAIL_MESSAGE, isValidEmail, PASSWORD_REQUIRED_MESSAGE } from '@/utils/validation';

import { toFormErrors, type FormErrors } from './form-errors';

export type LoginField = 'email' | 'password';

const LOGIN_FIELDS: readonly LoginField[] = ['email', 'password'];
const ACCOUNT_LOCKED = 'account_locked';
const RETRY_AFTER_SECONDS = 'retry_after_seconds';

const LOGIN_MESSAGES: Record<string, string> = {
  invalid_credentials: 'Email hoặc mật khẩu không đúng',
  account_disabled: 'Tài khoản đã bị vô hiệu hoá. Vui lòng liên hệ hỗ trợ.',
  email_not_verified: 'Email chưa được xác thực. Vui lòng kiểm tra hộp thư.',
  // Không có `retry_after_seconds` nghĩa là admin khoá (spec fe-auth §6 ý 7).
  [ACCOUNT_LOCKED]: 'Tài khoản đã bị khoá. Vui lòng liên hệ quản trị viên.',
};

/** `email` đã trim; mật khẩu chỉ cần khác rỗng, chính sách mật khẩu do server quyết định khi đăng nhập. */
export function validateLogin(email: string, password: string): FormErrors<LoginField> {
  const fields: Partial<Record<LoginField, string>> = {};
  if (!isValidEmail(email)) fields.email = EMAIL_MESSAGE;
  if (password.length === 0) fields.password = PASSWORD_REQUIRED_MESSAGE;
  return { fields, form: null };
}

/** Khoá tạm do brute-force: `auth_service.py` để số giây ở `message` của detail `retry_after_seconds`. */
function retryAfterSeconds(err: unknown): number | null {
  if (!isAxiosError(err)) return null;
  const body = err.response?.data as Partial<ApiErrorBody> | undefined;
  const detail = body?.error?.details?.find((item) => item.code === RETRY_AFTER_SECONDS);
  const seconds = Number(detail?.message);
  // Giá trị hỏng thì coi như không có, tránh hiện "NaN phút".
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null;
}

export function toLoginErrors(err: unknown): FormErrors<LoginField> {
  const seconds = getErrorCode(err) === ACCOUNT_LOCKED ? retryAfterSeconds(err) : null;
  const messages =
    seconds === null
      ? LOGIN_MESSAGES
      : { ...LOGIN_MESSAGES, [ACCOUNT_LOCKED]: `Tài khoản tạm khoá. Thử lại sau ${formatRetryAfter(seconds)}.` };
  return toFormErrors(err, { fields: LOGIN_FIELDS, messages });
}
