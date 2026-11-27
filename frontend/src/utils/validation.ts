/**
 * Kiểm tra dữ liệu nhập phía client để báo lỗi sớm; server vẫn là nguồn quyết định
 * (422 `validation_error`, spec fe-auth §6 ý 9). Thông điệp theo spec §2.4.
 */

export const PASSWORD_POLICY_MESSAGE = 'Mật khẩu cần 8–72 byte, có ít nhất 1 chữ cái và 1 chữ số';
export const DISPLAY_NAME_MESSAGE = 'Tên hiển thị cần 1–50 ký tự';
export const EMAIL_MESSAGE = 'Email không hợp lệ';
export const PASSWORD_REQUIRED_MESSAGE = 'Vui lòng nhập mật khẩu';
export const PASSWORD_MISMATCH_MESSAGE = 'Mật khẩu nhập lại không khớp';
export const FULL_NAME_MESSAGE = 'Họ và tên tối đa 100 ký tự';

// Chính sách mật khẩu doc 04 §6.1: bcrypt bỏ qua phần sau byte thứ 72 nên đếm byte UTF-8, không đếm ký tự.
const PASSWORD_MIN_BYTES = 8;
const PASSWORD_MAX_BYTES = 72;
// Backend dùng str.isalpha()/isdigit(): chữ có dấu ("é") cũng là chữ cái.
const LETTER_PATTERN = /\p{L}/u;
const DIGIT_PATTERN = /\p{Nd}/u;
// Trùng CHECK ck_users_email_format và EMAIL_PATTERN của backend; độ dài tối đa theo EmailAddress.
const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const EMAIL_MAX_CHARS = 254;
const DISPLAY_NAME_MAX_CHARS = 50;
const FULL_NAME_MAX_CHARS = 100;

export type DisplayNameCheck = { value: string; error: string | null };
export type FullNameCheck = { value: string | null; error: string | null };

/** Đếm theo code point để khớp `len()` của Python và `varchar(n)` của PostgreSQL. */
function countChars(value: string): number {
  return Array.from(value).length;
}

/** Tự tính thay vì dùng TextEncoder để không phụ thuộc runtime (Hermes đời cũ không có). */
function utf8ByteLength(value: string): number {
  let bytes = 0;
  for (const char of value) {
    const codePoint = char.codePointAt(0) ?? 0;
    if (codePoint < 0x80) bytes += 1;
    else if (codePoint < 0x800) bytes += 2;
    else if (codePoint < 0x10000) bytes += 3;
    else bytes += 4;
  }
  return bytes;
}

/** Trả thông điệp lỗi, hoặc `null` nếu mật khẩu đạt chính sách. */
export function checkPasswordPolicy(password: string): string | null {
  const size = utf8ByteLength(password);
  const hasValidSize = size >= PASSWORD_MIN_BYTES && size <= PASSWORD_MAX_BYTES;
  const hasLetterAndDigit = LETTER_PATTERN.test(password) && DIGIT_PATTERN.test(password);
  return hasValidSize && hasLetterAndDigit ? null : PASSWORD_POLICY_MESSAGE;
}

/** Không tự trim: màn hình trim trước khi kiểm tra và gửi. */
export function isValidEmail(email: string): boolean {
  return countChars(email) <= EMAIL_MAX_CHARS && EMAIL_PATTERN.test(email);
}

/** `value` là tên đã bỏ khoảng trắng hai đầu, đúng giá trị server sẽ lưu. */
export function checkDisplayName(input: string): DisplayNameCheck {
  const value = input.trim();
  const length = countChars(value);
  const isValid = length >= 1 && length <= DISPLAY_NAME_MAX_CHARS;
  return { value, error: isValid ? null : DISPLAY_NAME_MESSAGE };
}

/**
 * `value` là họ tên đã trim; trống thì `null` vì spec fe-auth §2.2 gửi `full_name: null` khi ô trống.
 * Giới hạn theo `full_name: str | None = Field(None, max_length=100)` của backend.
 */
export function checkFullName(input: string): FullNameCheck {
  const value = input.trim();
  if (value.length === 0) return { value: null, error: null };
  return { value, error: countChars(value) <= FULL_NAME_MAX_CHARS ? null : FULL_NAME_MESSAGE };
}
