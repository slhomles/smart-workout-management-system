/**
 * Quy lỗi API về lỗi của form (spec fe-auth §2.4): lỗi theo ô và một thông điệp chung.
 * Rẽ nhánh theo `getErrorCode`, KHÔNG so `message` (Claude_api_respone.md §3; frontend-standards §3).
 * Dùng lại ở đăng nhập, đăng ký, đổi mật khẩu, sửa hồ sơ, đặt mục tiêu.
 */
import { getErrorCode, getErrorMessage, getFieldErrors } from '@/services/api/errors';

export const PERMISSION_DENIED_MESSAGE = 'Bạn không có quyền thực hiện thao tác này';

const VALIDATION_ERROR = 'validation_error';
const PERMISSION_DENIED = 'permission_denied';

export type FormErrors<F extends string> = { fields: Partial<Record<F, string>>; form: string | null };

export type FormErrorOptions<F extends string> = {
  /** Tên field của API có ô trên form (vd `email`, `new_password`). */
  fields: readonly F[];
  /** Thông điệp riêng theo `error.code`. */
  messages?: Partial<Record<string, string>>;
  /** `error.code` nào thì hiện dưới ô nào (vd `email_already_exists` → `email`). */
  fieldOf?: Partial<Record<string, F>>;
};

export function emptyFormErrors<F extends string>(): FormErrors<F> {
  return { fields: {}, form: null };
}

// `code` do server gửi: chỉ đọc thuộc tính riêng để mã trùng tên thuộc tính của Object (vd "constructor") không bị coi là đã map.
function ownValue<V>(record: Partial<Record<string, V>> | undefined, key: string): V | undefined {
  return record && Object.prototype.hasOwnProperty.call(record, key) ? record[key] : undefined;
}

function isFormField<F extends string>(key: string, fields: readonly F[]): key is F {
  return (fields as readonly string[]).includes(key);
}

function fromValidation<F extends string>(err: unknown, fields: readonly F[]): FormErrors<F> {
  const result = emptyFormErrors<F>();
  let hasOrphanDetail = false;
  for (const [field, message] of Object.entries(getFieldErrors(err))) {
    if (isFormField(field, fields)) result.fields[field] = message;
    else hasOrphanDetail = true;
  }
  // Field không có ô (hoặc không có field nào) thì người dùng vẫn phải thấy lỗi.
  if (hasOrphanDetail || Object.keys(result.fields).length === 0) result.form = getErrorMessage(err);
  return result;
}

function messageOf(code: string, messages: FormErrorOptions<string>['messages']): string | undefined {
  return ownValue(messages, code) ?? (code === PERMISSION_DENIED ? PERMISSION_DENIED_MESSAGE : undefined);
}

export function toFormErrors<F extends string>(err: unknown, options: FormErrorOptions<F>): FormErrors<F> {
  const code = getErrorCode(err) ?? '';
  if (code === VALIDATION_ERROR) return fromValidation(err, options.fields);
  const message = messageOf(code, options.messages);
  if (message === undefined) return { fields: {}, form: getErrorMessage(err) };
  const field = ownValue(options.fieldOf, code);
  if (field === undefined) return { fields: {}, form: message };
  const fields: Partial<Record<F, string>> = {};
  fields[field] = message;
  return { fields, form: null };
}

export function hasFormErrors<F extends string>(errors: FormErrors<F>): boolean {
  return errors.form !== null || Object.keys(errors.fields).length > 0;
}
