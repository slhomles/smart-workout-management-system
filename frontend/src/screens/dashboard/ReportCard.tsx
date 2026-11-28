import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import { radius, spacing, useTheme } from '@/styles/theme';

/** Thẻ của một mục trên tab Báo cáo: nền `surface`, bo `card`, đệm trong 16–20 (spec §4 Giao diện; ảnh 11, 12). */
export function ReportCard({ children }: { children: ReactNode }) {
  const theme = useTheme();
  return <View style={[styles.card, { backgroundColor: theme.surface }]}>{children}</View>;
}

/** Đường kẻ `divider` giữa các phần trong thẻ (ảnh 11). */
export function CardDivider() {
  const theme = useTheme();
  return <View style={[styles.divider, { backgroundColor: theme.divider }]} />;
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: spacing.xl, gap: spacing.md },
  divider: { height: StyleSheet.hairlineWidth },
});
