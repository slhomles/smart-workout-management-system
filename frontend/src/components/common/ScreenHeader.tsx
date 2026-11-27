import { Ionicons } from '@expo/vector-icons';
import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import { spacing, useTheme } from '@/styles/theme';

import { AppText } from './AppText';

type Props = { title: string; streakDays?: number | null; right?: ReactNode };

/** Tiêu đề màn VIẾT HOA đậm; bên phải là ngọn lửa + số ngày tập liên tiếp (ảnh mẫu 01, 11). */
export function ScreenHeader({ title, streakDays, right }: Props) {
  const theme = useTheme();
  return (
    <View style={styles.row}>
      <AppText variant="display" style={styles.title} accessibilityRole="header">
        {title}
      </AppText>
      {streakDays != null && (
        <View style={styles.streak} accessibilityLabel={`Chuỗi ${streakDays} ngày tập`}>
          <Ionicons name="flame" size={30} color={theme.flame} />
          <AppText variant="label">{streakDays}</AppText>
        </View>
      )}
      {right}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: spacing.lg, paddingVertical: spacing.lg },
  title: { flex: 1 },
  streak: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginLeft: spacing.md },
});
