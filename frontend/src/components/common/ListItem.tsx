import { Ionicons } from '@expo/vector-icons';
import type { ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { radius, spacing, useTheme } from '@/styles/theme';

import { AppText } from './AppText';
import { DifficultyBolts } from './DifficultyBolts';

type Props = {
  title: string;
  meta?: string;
  thumb?: ReactNode;
  difficultyRank?: number;
  badge?: string;
  showArrow?: boolean;
  onPress?: () => void;
};

/** Dòng danh sách (ảnh mẫu 02, 04): ảnh vuông bo góc, tên đậm, dòng phụ xám, tia sét độ khó. */
export function ListItem({ title, meta, thumb, difficultyRank, badge, showArrow = false, onPress }: Props) {
  const theme = useTheme();
  return (
    <Pressable onPress={onPress} disabled={!onPress} accessibilityRole={onPress ? 'button' : undefined} style={styles.row}>
      {thumb}
      <View style={[styles.body, { borderBottomColor: theme.divider }]}>
        <View style={styles.titleRow}>
          <AppText variant="itemTitle" numberOfLines={2} style={styles.flex}>
            {title}
          </AppText>
          {badge && (
            <View style={[styles.badge, { backgroundColor: theme.primarySoft }]}>
              <AppText variant="label" color={theme.primary}>
                {badge}
              </AppText>
            </View>
          )}
        </View>
        {meta && (
          <AppText variant="meta" color={theme.textMuted}>
            {meta}
          </AppText>
        )}
        {difficultyRank != null && <DifficultyBolts rank={difficultyRank} />}
      </View>
      {showArrow && (
        <View style={[styles.arrow, { backgroundColor: theme.text }]}>
          <Ionicons name="arrow-forward" size={18} color={theme.surface} />
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.lg, paddingVertical: spacing.sm },
  body: { flex: 1, gap: spacing.xs, paddingVertical: spacing.md, borderBottomWidth: StyleSheet.hairlineWidth },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  flex: { flex: 1 },
  badge: { borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  arrow: { width: 32, height: 32, borderRadius: radius.pill, alignItems: 'center', justifyContent: 'center' },
});
