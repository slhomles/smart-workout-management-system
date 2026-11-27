import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/common';
import { sizes, spacing, useTheme } from '@/styles/theme';

/**
 * Header của các màn trong `account/` (spec fe-auth §2.1): nút "Quay lại" rồi tiêu đề `display` như `ScreenHeader`.
 * `ScreenHeader` chỉ có chỗ trống bên phải nên nút quay lại cần header riêng.
 */
export function AccountHeader({ title }: { title: string }) {
  const theme = useTheme();
  return (
    <View style={styles.row}>
      <Pressable onPress={() => router.back()} accessibilityRole="button" accessibilityLabel="Quay lại" style={styles.back}>
        <Ionicons name="chevron-back" size={sizes.tabIcon} color={theme.text} />
      </Pressable>
      <AppText variant="display" accessibilityRole="header" style={styles.title}>
        {title}
      </AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, paddingHorizontal: spacing.sm, paddingVertical: spacing.lg },
  back: { minWidth: sizes.touch, minHeight: sizes.touch, alignItems: 'center', justifyContent: 'center' },
  title: { flex: 1 },
});
