import { Ionicons } from '@expo/vector-icons';
import type { ComponentProps } from 'react';
import { Pressable, StyleSheet } from 'react-native';

import { radius, sizes, spacing, useTheme } from '@/styles/theme';

import { AppText } from './AppText';

export type IconName = ComponentProps<typeof Ionicons>['name'];

type Props = { label: string; icon: IconName; selected?: boolean; onPress?: () => void };

/** Ô lọc nhanh: nền xám nhạt, icon viền xanh + nhãn (ảnh mẫu 02, 06). */
export function FilterTile({ label, icon, selected = false, onPress }: Props) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected }}
      style={[
        styles.tile,
        { backgroundColor: selected ? theme.primarySoft : theme.surfaceMuted, borderColor: selected ? theme.primary : 'transparent' },
      ]}
    >
      <Ionicons name={icon} size={24} color={theme.primary} />
      <AppText variant="body">{label}</AppText>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tile: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    minHeight: sizes.button,
    paddingHorizontal: spacing.xl,
    borderRadius: radius.card,
    borderWidth: 2,
  },
});
