// Giữ chỗ cho màn đăng nhập. Module `fe-auth` làm màn thật rồi bật AUTH_REQUIRED (src/constants/features.ts).
import { EmptyState, Screen, ScreenHeader } from '@/components/common';

export default function LoginScreen() {
  return (
    <Screen header={<ScreenHeader title="Đăng nhập" />}>
      <EmptyState title="Màn đăng nhập đang được xây dựng" icon="log-in-outline" />
    </Screen>
  );
}
