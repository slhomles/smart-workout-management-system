import { router } from 'expo-router';
import { StyleSheet, View } from 'react-native';

import { SettingsRow } from '@/components/common';
import { radius, spacing, useTheme } from '@/styles/theme';
import type { Me } from '@/types/auth';

import { unitSystemLabel } from './labels';

// Ẩn/hiện theo permission trong `me`, không suy từ tên role (doc 04 §7 ý 7; spec fe-auth §2.2 "Permission").
const MANAGE_OWN_BODY_METRIC = 'body_metric:manage_own';

/** Các dòng cần dữ liệu `me`; màu ô icon chỉ lấy từ theme (spec fe-auth §4, §6 ý 15). */
function AccountRows({ me }: { me: Me }) {
  const theme = useTheme();
  const canManageGoals = me.permissions.includes(MANAGE_OWN_BODY_METRIC);
  return (
    <>
      <SettingsRow icon="person" iconColor={theme.primary} label="Hồ sơ" onPress={() => router.push('/account/edit-profile')} />
      {canManageGoals && (
        <SettingsRow icon="flag" iconColor={theme.accentOrange} label="Mục tiêu" onPress={() => router.push('/account/goals')} />
      )}
      <SettingsRow
        icon="speedometer"
        iconColor={theme.primary}
        label="Đơn vị đo"
        sublabel={unitSystemLabel(me.unit_system)}
        onPress={() => router.push('/account/units')}
      />
      <SettingsRow
        icon="phone-portrait"
        iconColor={theme.primary}
        label="Thiết bị đăng nhập"
        onPress={() => router.push('/account/devices')}
      />
      <SettingsRow icon="key" iconColor={theme.primary} label="Đổi mật khẩu" onPress={() => router.push('/account/change-password')} />
    </>
  );
}

type Props = { me: Me | undefined; onLogout: () => void };

/**
 * Thẻ `surface` chứa các `SettingsRow` của tab Cá nhân (ảnh mẫu 13). Dòng "Đăng xuất" luôn hiện, kể cả khi
 * `GET /auth/me` đang tải hoặc lỗi; các dòng còn lại chỉ hiện khi đã có `me` (spec fe-auth §2.2).
 */
export function ProfileSettings({ me, onLogout }: Props) {
  const theme = useTheme();
  return (
    <View style={[styles.card, { backgroundColor: theme.surface }]}>
      {me ? <AccountRows me={me} /> : null}
      <SettingsRow icon="log-out" iconColor={theme.flame} label="Đăng xuất" onPress={onLogout} />
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, paddingHorizontal: spacing.lg },
});
