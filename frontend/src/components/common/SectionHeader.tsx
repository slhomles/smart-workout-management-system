import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, View } from 'react-native';

import { radius, spacing, useTheme } from '@/styles/theme';

import { AppText } from './AppText';

type Props = { title: string; isNew?: boolean; onMore?: () => void; moreLabel?: string };

/** Tiêu đề mục; tuỳ chọn nhãn vàng "MỚI" và link "Thêm ›" (ảnh mẫu 03, 04). */
export function SectionHeader({ title, isNew = false, onMore, moreLabel = 'Thêm' }: Props) {
  const theme = useTheme();
  return (
    <View style={styles.row}>
      <AppText variant="title" accessibilityRole="header">
        {title}
      </AppText>
      {isNew && (
        <View style={[styles.badge, { backgroundColor: theme.badgeYellow }]}>
          <AppText variant="label" color="#111318">
            MỚI
          </AppText>
        </View>
      )}
      <View style={styles.spacer} />
      {onMore && (
        <Pressable onPress={onMore} hitSlop={10} style={styles.more} accessibilityRole="button" accessibilityLabel={moreLabel}>
          <AppText color={theme.link}>{moreLabel}</AppText>
          <Ionicons name="chevron-forward" size={18} color={theme.link} />
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.md },
  badge: { borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: 2 },
  spacer: { flex: 1 },
  more: { flexDirection: 'row', alignItems: 'center' },
});
