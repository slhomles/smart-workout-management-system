import { Pressable, StyleSheet } from 'react-native';

import { levelColors, radius, sizes, spacing, useTheme, type LevelCode } from '@/styles/theme';

import { AppText } from './AppText';

type ChipProps = { label: string; selected?: boolean; solid?: boolean; onPress?: () => void };

/**
 * Chip viên thuốc (ảnh mẫu 02, 05, 07). Đang chọn: nền xanh nhạt + viền xanh 2px, hoặc `solid` nền xanh đặc.
 * Chưa chọn: nền xám, chữ xám.
 */
export function Chip({ label, selected = false, solid = false, onPress }: ChipProps) {
  const theme = useTheme();
  const active = selected && !solid;
  const filled = selected && solid;
  const bg = filled ? theme.primary : active ? theme.primarySoft : theme.surfaceMuted;
  const fg = filled ? theme.onPrimary : active ? theme.primary : theme.textMuted;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      style={[styles.chip, { backgroundColor: bg, borderColor: active ? theme.primary : 'transparent' }]}
    >
      <AppText variant="itemTitle" color={fg}>
        {label}
      </AppText>
    </Pressable>
  );
}

type LevelChipProps = { level: LevelCode; label?: string; onPress?: () => void };

/** Chip cấp độ 3 màu (ảnh mẫu 06). */
export function LevelChip({ level, label, onPress }: LevelChipProps) {
  const color = levelColors[level];
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={[styles.chip, { backgroundColor: color.bg }]}>
      <AppText variant="itemTitle" color={color.fg}>
        {label ?? color.label}
      </AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  chip: {
    minHeight: sizes.touch,
    justifyContent: 'center',
    borderRadius: radius.pill,
    borderWidth: 2,
    borderColor: 'transparent',
    paddingHorizontal: spacing.xl,
  },
});
