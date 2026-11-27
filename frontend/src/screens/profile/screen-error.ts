/**
 * Thông điệp lỗi của màn hoặc thao tác không gắn ô nhập nào (spec fe-auth §2.4): mã có thông điệp riêng
 * (`messages`, `permission_denied`) hiện thông điệp đó; `validation_error`, mã khác và lỗi mạng dùng
 * `getErrorMessage`. Rẽ nhánh theo `error.code` qua `toFormErrors`, KHÔNG so `message`.
 */
import { toFormErrors } from '@/screens/auth/form-errors';
import { getErrorMessage } from '@/services/api/errors';

export function screenErrorMessage(err: unknown, messages?: Partial<Record<string, string>>): string {
  return toFormErrors(err, { fields: [], messages }).form ?? getErrorMessage(err);
}
