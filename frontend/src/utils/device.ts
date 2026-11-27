/** Thông tin thiết bị gửi kèm đăng nhập (doc 04 §4.3). */
import type { DevicePlatform } from '@/types/auth';

/** `Platform.OS` → `platform` của API; hệ khác (windows, macos) gửi `web` vì server chỉ nhận 3 giá trị. */
export function toDevicePlatform(os: string): DevicePlatform {
  if (os === 'ios' || os === 'android') return os;
  return 'web';
}
