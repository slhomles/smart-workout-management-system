import { Ionicons } from '@expo/vector-icons';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { spacing, useTheme } from '@/styles/theme';

import { AppText } from './AppText';
import type { IconName } from './FilterTile';
import { GradientButton } from './GradientButton';

/** Bốn trạng thái bắt buộc của màn gọi API (frontend-standards §4): tải, lỗi, rỗng (dữ liệu do màn hiện). */
export function LoadingState({ label = 'Đang tải...' }: { label?: string }) {
  const theme = useTheme();
  return (
    <View style={styles.box} accessibilityLabel={label}>
      <ActivityIndicator size="large" color={theme.primary} />
    </View>
  );
}

export function EmptyState({ title, message, icon = 'file-tray-outline' }: { title: string; message?: string; icon?: IconName }) {
  const theme = useTheme();
  return (
    <View style={styles.box}>
      <Ionicons name={icon} size={48} color={theme.textMuted} />
      <AppText variant="itemTitle" align="center">
        {title}
      </AppText>
      {message && (
        <AppText variant="meta" color={theme.textMuted} align="center">
          {message}
        </AppText>
      )}
    </View>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const theme = useTheme();
  return (
    <View style={styles.box}>
      <Ionicons name="cloud-offline-outline" size={48} color={theme.flame} />
      <AppText variant="body" align="center">
        {message}
      </AppText>
      {onRetry && <GradientButton label="Thử lại" onPress={onRetry} />}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { alignItems: 'center', justifyContent: 'center', gap: spacing.md, paddingVertical: spacing.section },
});
