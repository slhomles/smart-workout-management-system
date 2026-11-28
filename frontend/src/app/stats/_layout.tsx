// Stack cho các màn phụ của tab Báo cáo (spec fe-dashboard §2.1, §6 ý 12): chưa đăng nhập thì chuyển về /login,
// giống `account/_layout.tsx`. Mỗi màn tự có nút "Quay lại" nên ẩn header mặc định.
import { Redirect, Stack } from 'expo-router';

import { AUTH_REQUIRED } from '@/constants/features';
import { useSession } from '@/store/session';

export default function StatsLayout() {
  const status = useSession((state) => state.status);
  if (AUTH_REQUIRED && status === 'signedOut') return <Redirect href="/login" />;
  return <Stack screenOptions={{ headerShown: false }} />;
}
