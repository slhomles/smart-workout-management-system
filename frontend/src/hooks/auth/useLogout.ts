/** Đăng xuất thiết bị này (doc 04 §4.5, §7 ý 6; spec fe-auth §2.2 "Đăng xuất"). */
import { getRefreshToken } from '@/services/api/session-storage';
import { logout } from '@/services/auth';

import { useEndSession } from './useEndSession';
import { useSingleFlight } from './useSingleFlight';

async function revokeRefreshToken(): Promise<void> {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) return;
  try {
    await logout(refreshToken);
  } catch {
    // Cố ý bỏ qua MỌI lỗi của lời gọi này (mạng hay server): `/auth/logout` idempotent và máy luôn phải
    // xoá phiên (doc 04 §4.5, §7 ý 6). Không log vì lỗi gắn với refresh token.
  }
}

export function useLogout() {
  const endSession = useEndSession();
  const { run, isPending } = useSingleFlight(async () => {
    await revokeRefreshToken();
    await endSession('/login');
  });
  return { logout: run, isPending };
}
