/**
 * Định dạng và đọc số, ngày theo kiểu Việt Nam (frontend-standards §4: `1.234,5`, `dd/mm/yyyy`).
 * Ngày xử lý bằng chuỗi, KHÔNG qua `new Date`, để không lệch ngày theo múi giờ của máy.
 */

const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const VI_DATE_PATTERN = /^(\d{2})\/(\d{2})\/(\d{4})$/;
// Một dấu thập phân (phẩy hoặc chấm), không nhận dấu phân cách hàng nghìn để tránh nhập nhằng.
const DECIMAL_PATTERN = /^-?\d+([.,]\d+)?$/;
const DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];

export function formatNumber(value: number, maxFractionDigits = 1): string {
  return new Intl.NumberFormat('vi-VN', { maximumFractionDigits: maxFractionDigits }).format(value);
}

/** `yyyy-mm-dd` → `dd/mm/yyyy`; chuỗi không đúng dạng thì giữ nguyên để không hiện ngày sai. */
export function formatDate(isoDate: string): string {
  const match = ISO_DATE_PATTERN.exec(isoDate);
  if (!match) return isoDate;
  const [, year = '', month = '', day = ''] = match;
  return `${day}/${month}/${year}`;
}

function isLeapYear(year: number): boolean {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

function daysInMonth(year: number, month: number): number {
  if (month === 2 && isLeapYear(year)) return 29;
  return DAYS_IN_MONTH[month - 1] ?? 0;
}

/** Không có năm 0 trong lịch Gregorian; tháng ngoài 1–12 có `daysInMonth` = 0 nên tự bị loại. */
function isRealDate(year: number, month: number, day: number): boolean {
  return year >= 1 && day >= 1 && day <= daysInMonth(year, month);
}

/** `dd/mm/yyyy` → `yyyy-mm-dd`, hoặc `null` nếu sai định dạng hay ngày không có thật. */
export function parseDateVi(text: string): string | null {
  const match = VI_DATE_PATTERN.exec(text.trim());
  if (!match) return null;
  const [, day = '', month = '', year = ''] = match;
  if (!isRealDate(Number(year), Number(month), Number(day))) return null;
  return `${year}-${month}-${day}`;
}

/** Nhận `70,5` hoặc `70.5`; chuỗi rỗng hay không phải số trả `null`. */
export function parseDecimalVi(text: string): number | null {
  const normalized = text.trim();
  if (!DECIMAL_PATTERN.test(normalized)) return null;
  return Number(normalized.replace(',', '.'));
}

/** Số giây chờ (vd `retry_after_seconds` của `account_locked`) → số phút làm tròn lên. */
export function formatRetryAfter(seconds: number): string {
  return `${Math.ceil(seconds / 60)} phút`;
}
