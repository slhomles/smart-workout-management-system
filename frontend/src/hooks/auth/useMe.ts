/**
 * `GET /auth/me` dùng chung (doc 04 §4.6; spec fe-auth §2.3, §6 ý 13). Module khác cần `unit_system`
 * hay `permissions` thì dùng hook này và `ME_QUERY_KEY`, không tự tạo query khác.
 */
import { useQuery } from '@tanstack/react-query';

import { getMe } from '@/services/auth';
import { useSession } from '@/store/session';

export const ME_QUERY_KEY = ['auth', 'me'] as const;

export function useMe() {
  // Tắt khi đã đăng xuất: sau `queryClient.clear()`, observer còn mount không được tự gọi lại `/auth/me`
  // (cache `['auth','me']` phải rỗng sau đăng xuất).
  const isSignedOut = useSession((state) => state.status === 'signedOut');
  return useQuery({ queryKey: ME_QUERY_KEY, queryFn: getMe, enabled: !isSignedOut });
}
