import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, View } from 'react-native';

import { radius, sizes, spacing, useTheme } from '@/styles/theme';

import { AppText } from './AppText';
import type { IconName } from './FilterTile';

type Props = { icon: IconName; iconColor: string; label: string; sublabel?: string; hasDot?: boolean; onPress?: () => void };

/** Dòng cài đặt (ảnh mẫu 13): icon trắng trong ô vuông bo màu, nhãn, chấm đỏ báo mới, mũi tên ›. */
export function SettingsRow({ icon, iconColor, label, sublabel, hasDot = false, onPress }: Props) {
  const theme = useTheme();
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={[styles.row, { borderBottomColor: theme.divider }]}>
      <View style={[styles.icon, { backgroundColor: iconColor }]}>
        <Ionicons name={icon} size={24} color={theme.onPrimary} />
      </View>
      <View style={styles.body}>
        <AppText variant="itemTitle">{label}</AppText>
        {sublabel && (
          <AppText variant="meta" color={theme.link}>
            {sublabel}
          </AppText>
        )}
      </View>
      {hasDot && <View style={[styles.dot, { backgroundColor: theme.flame }]} />}
      <Ionicons name="chevron-forward" size={22} color={theme.textMuted} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.lg,
    minHeight: sizes.button + 16,
    borderBottomWidth: StyleSheet.hairlineWidth,
  },
  icon: { width: 48, height: 48, borderRadius: radius.icon, alignItems: 'center', justifyContent: 'center' },
  body: { flex: 1 },
  dot: { width: 10, height: 10, borderRadius: radius.pill },
});
