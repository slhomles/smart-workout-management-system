import { Ionicons } from '@expo/vector-icons';
import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/common';
import { radius, sizes, spacing, useTheme } from '@/styles/theme';
import type { Me } from '@/types/auth';

// Icon chiếm nửa ô tròn để kích thước đi theo token `sizes.thumbSmall`, không viết số pixel rời.
const AVATAR_ICON_SIZE = sizes.thumbSmall / 2;

/**
 * Thẻ tài khoản thay khối "Sao lưu & Khôi phục" của ảnh mẫu 13 (spec fe-auth §4 "Tab Cá nhân"):
 * icon người trong ô tròn `primarySoft`, tên `title` (chưa có tên hiển thị thì dùng email), email `meta`.
 */
export function AccountCard({ me }: { me: Me }) {
  const theme = useTheme();
  return (
    <View style={[styles.card, { backgroundColor: theme.surface }]}>
      <View style={[styles.avatar, { backgroundColor: theme.primarySoft }]}>
        <Ionicons name="person" size={AVATAR_ICON_SIZE} color={theme.primary} />
      </View>
      <View style={styles.body}>
        <AppText variant="title">{me.display_name ?? me.email}</AppText>
        <AppText variant="meta" color={theme.textMuted}>
          {me.email}
        </AppText>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg, borderRadius: radius.card, padding: spacing.lg },
  avatar: {
    width: sizes.thumbSmall,
    height: sizes.thumbSmall,
    borderRadius: radius.pill,
    alignItems: 'center',
    justifyContent: 'center',
  },
  body: { flex: 1, gap: spacing.xs },
});
