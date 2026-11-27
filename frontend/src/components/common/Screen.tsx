import type { ReactNode } from 'react';
import { RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { spacing, useTheme } from '@/styles/theme';

type Props = {
  children: ReactNode;
  scroll?: boolean;
  refreshing?: boolean;
  onRefresh?: () => void;
  header?: ReactNode;
};

/** Khung màn hình: nền `background`, lề 16, tuỳ chọn cuộn và kéo để tải lại. */
export function Screen({ children, scroll = true, refreshing = false, onRefresh, header }: Props) {
  const theme = useTheme();
  const refresh = onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} /> : undefined;
  return (
    <SafeAreaView edges={['top']} style={[styles.safe, { backgroundColor: theme.background }]}>
      {header}
      {scroll ? (
        <ScrollView contentContainerStyle={styles.content} refreshControl={refresh}>
          {children}
        </ScrollView>
      ) : (
        <View style={[styles.content, styles.fill]}>{children}</View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1 },
  fill: { flex: 1 },
  content: { paddingHorizontal: spacing.lg, paddingBottom: spacing.section, gap: spacing.section },
});
