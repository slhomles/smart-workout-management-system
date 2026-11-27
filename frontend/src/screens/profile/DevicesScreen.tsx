// Thiết bị đăng nhập (spec fe-auth §2.1; ảnh mẫu 13). Backend chưa có `/auth/devices` nên màn chỉ có
// "Đăng xuất khỏi mọi thiết bị" (`POST /auth/logout-all`); danh sách thiết bị chờ câu hỏi Q1 (spec §6 ý 1).
import { StyleSheet, View } from 'react-native';

import { AppText, GradientButton, Screen } from '@/components/common';
import { radius, spacing, useTheme } from '@/styles/theme';

import { AccountHeader } from './AccountHeader';
import { useLogoutAll } from './useLogoutAll';

export default function DevicesScreen() {
  const theme = useTheme();
  const { confirm, isPending, error } = useLogoutAll();
  return (
    <Screen header={<AccountHeader title="Thiết bị đăng nhập" />}>
      <View style={[styles.card, { backgroundColor: theme.surface }]}>
        <AppText color={theme.textMuted}>
          Đăng xuất tài khoản trên mọi thiết bị, kể cả máy này. Sau đó bạn cần đăng nhập lại.
        </AppText>
        {error ? (
          <AppText variant="meta" color={theme.flame} accessibilityRole="alert">
            {error}
          </AppText>
        ) : null}
        <GradientButton label="Đăng xuất khỏi mọi thiết bị" onPress={confirm} loading={isPending} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: spacing.lg, gap: spacing.lg },
});
