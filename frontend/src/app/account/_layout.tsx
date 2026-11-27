// Stack cho các màn tài khoản (spec fe-auth §2.1, §6 ý 16): chưa đăng nhập thì chuyển về /login,
// giống `(tabs)/_layout.tsx`. Mỗi màn tự có nút "Quay lại" nên ẩn header mặc định.
import { Redirect, Stack } from 'expo-router';

import { AUTH_REQUIRED } from '@/constants/features';
import { useSession } from '@/store/session';

export default function AccountLayout() {
  const status = useSession((state) => state.status);
  if (AUTH_REQUIRED && status === 'signedOut') return <Redirect href="/login" />;
  return <Stack screenOptions={{ headerShown: false }} />;
}
