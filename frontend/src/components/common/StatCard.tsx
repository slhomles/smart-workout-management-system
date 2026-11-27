import { Ionicons } from '@expo/vector-icons';
import { StyleSheet, View } from 'react-native';

import { radius, spacing, typography, useTheme } from '@/styles/theme';

import { AppText } from './AppText';
import type { IconName } from './FilterTile';

export type Stat = { icon: IconName; value: string; label: string };

/** Thẻ 3 chỉ số: icon, số lớn, nhãn (ảnh mẫu 11). */
export function StatCard({ stats }: { stats: Stat[] }) {
  const theme = useTheme();
  return (
    <View style={[styles.card, { backgroundColor: theme.surface }]}>
      {stats.map((s) => (
        <View key={s.label} style={styles.col}>
          <Ionicons name={s.icon} size={28} color={theme.primary} />
          <AppText style={[typography.number, styles.value]}>{s.value}</AppText>
          <AppText variant="body" color={theme.textMuted}>
            {s.label}
          </AppText>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { flexDirection: 'row', borderRadius: radius.card, paddingVertical: spacing.xl },
  col: { flex: 1, alignItems: 'center', gap: spacing.xs },
  value: { fontSize: 36, lineHeight: 42 },
});
