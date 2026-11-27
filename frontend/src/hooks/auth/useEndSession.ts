/**
 * Kết thúc phiên trên máy (spec fe-auth §2.2, §6 ý 5): dùng chung cho đăng xuất, đăng xuất mọi thiết bị
 * và đổi mật khẩu. Không gọi API: việc thu hồi token ở server do nơi gọi quyết định.
 */
import { useQueryClient } from '@tanstack/react-query';
import { router, type Href } from 'expo-router';
import { useCallback } from 'react';

import { useSession } from '@/store/session';

export function useEndSession(): (target: Href) => Promise<void> {
  const queryClient = useQueryClient();
  const signOut = useSession((state) => state.signOut);
  return useCallback(
    async (target: Href) => {
      // Thứ tự bắt buộc: `signOut()` (xoá access/refresh token, giữ device_id) đặt status `signedOut` trước
      // để `useMe` bị tắt; nếu `clear()` trước, observer còn mount sẽ gọi lại `/auth/me` và nạp lại cache.
      await signOut();
      queryClient.clear();
      router.replace(target);
    },
    [queryClient, signOut],
  );
}
