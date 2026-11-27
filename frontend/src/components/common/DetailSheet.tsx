import { Ionicons } from '@expo/vector-icons';
import type { ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { radius, spacing, useTheme } from '@/styles/theme';

type Props = { media: ReactNode; children: ReactNode; onBack?: () => void; onMenu?: () => void; mediaHeight?: number };

/** Màn chi tiết (ảnh mẫu 08): media lớn phía trên, tấm trắng bo góc 24 phủ lên; nút tròn mờ trên ảnh. */
export function DetailSheet({ media, children, onBack, onMenu, mediaHeight = 300 }: Props) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  return (
    <View style={[styles.fill, { backgroundColor: theme.surface }]}>
      <ScrollView bounces={false}>
        <View style={{ height: mediaHeight }}>{media}</View>
        <View style={[styles.sheet, { backgroundColor: theme.surface }]}>{children}</View>
      </ScrollView>
      <View style={[styles.topBar, { top: insets.top + spacing.sm }]} pointerEvents="box-none">
        {onBack && (
          <Pressable onPress={onBack} style={[styles.round, { backgroundColor: theme.scrim }]} accessibilityLabel="Quay lại">
            <Ionicons name="arrow-back" size={24} color={theme.onPrimary} />
          </Pressable>
        )}
        <View style={styles.fill} />
        {onMenu && (
          <Pressable onPress={onMenu} style={[styles.round, { backgroundColor: theme.scrim }]} accessibilityLabel="Tuỳ chọn">
            <Ionicons name="ellipsis-vertical" size={22} color={theme.onPrimary} />
          </Pressable>
        )}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  sheet: {
    marginTop: -radius.hero,
    borderTopLeftRadius: radius.hero,
    borderTopRightRadius: radius.hero,
    padding: spacing.xl,
    gap: spacing.xl,
    minHeight: 400,
  },
  topBar: { position: 'absolute', left: spacing.lg, right: spacing.lg, flexDirection: 'row' },
  round: { width: 44, height: 44, borderRadius: radius.pill, alignItems: 'center', justifyContent: 'center' },
});
