/**
 * Hàm thuần của tab Báo cáo (spec fe-dashboard §2.3). Ngày xử lý theo giờ địa phương hoặc chuỗi,
 * KHÔNG dùng `toISOString()`: đổi sang UTC sẽ lệch ngày ở múi giờ dương (vd Asia/Ho_Chi_Minh lúc 00:30).
 */
import { startOfWeek } from '@/components/common/WeekStrip';
import type { RecoveryStatus } from '@/types/dashboard';

const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const DAYS_PER_WEEK = 7;

// Map thay cho object literal để khoá lạ như `toString` không trúng thuộc tính của prototype.
const BMI_CATEGORY_LABELS = new Map<string, string>([
  ['underweight', 'Thiếu cân'],
  ['normal', 'Bình thường'],
  ['overweight', 'Thừa cân'],
  ['obese', 'Béo phì'],
]);

const RECOVERY_STATUS_LABELS: Record<RecoveryStatus, string> = {
  fatigued: 'Mệt mỏi',
  recovering: 'Đang hồi phục',
  ready: 'Sẵn sàng',
};

function pad2(value: number): string {
  return String(value).padStart(2, '0');
}

/** `Date` → `yyyy-mm-dd` theo giờ địa phương. */
function toLocalDateKey(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

/** `yyyy-mm-dd` → `Date` 00:00 giờ địa phương, hoặc `null` nếu sai dạng hay ngày không có thật. */
function parseLocalDate(isoDate: string): Date | null {
  const match = ISO_DATE_PATTERN.exec(isoDate);
  if (!match) return null;
  const [year, month, day] = match.slice(1).map(Number) as [number, number, number];
  const date = new Date(year, month - 1, day);
  // `new Date` tự cuộn ngày tràn (30/02 → 02/03), so lại từng phần để loại ngày không có thật.
  const isSameDay = date.getFullYear() === year && date.getMonth() === month - 1 && date.getDate() === day;
  return isSameDay ? date : null;
}

/** Thứ Hai của tuần trước tuần chứa `today` (tuần bắt đầu Thứ Hai), dạng `yyyy-mm-dd`. */
export function previousWeekStart(today: Date): string {
  const monday = startOfWeek(today);
  monday.setDate(monday.getDate() - DAYS_PER_WEEK);
  return toLocalDateKey(monday);
}

/** `period_end` của báo cáo là ngày không bao gồm, nên ngày cuối kỳ là ngày liền trước. Sai dạng giữ nguyên. */
export function lastDayOfPeriod(periodEnd: string): string {
  const date = parseLocalDate(periodEnd);
  if (!date) return periodEnd;
  date.setDate(date.getDate() - 1);
  return toLocalDateKey(date);
}

/** `yyyy-mm-dd` → `dd/mm`; sai dạng thì giữ nguyên để không hiện ngày sai. */
export function formatDayMonth(isoDate: string): string {
  const match = ISO_DATE_PATTERN.exec(isoDate);
  if (!match) return isoDate;
  const [, , month = '', day = ''] = match;
  return `${day}/${month}`;
}

/** Nhãn của `bmi_category` do server tính; `null` hoặc giá trị lạ trả chuỗi rỗng. */
export function bmiCategoryLabel(category: string | null): string {
  if (category === null) return '';
  return BMI_CATEGORY_LABELS.get(category) ?? '';
}

export function recoveryStatusLabel(status: RecoveryStatus): string {
  return RECOVERY_STATUS_LABELS[status];
}
