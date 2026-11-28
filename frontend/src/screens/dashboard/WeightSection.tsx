import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText, EmptyState } from '@/components/common';
import { radius, sizes, spacing, useTheme } from '@/styles/theme';
import type { UnitSystem } from '@/types/auth';
import type { LatestMetrics } from '@/types/dashboard';

import { ReportCard } from './ReportCard';
import { WeightTrendBlock } from './WeightTrendBlock';

type Props = { metrics: LatestMetrics | null; isPlateau: boolean; unitSystem: UnitSystem | null };

const PLATEAU_MESSAGE = 'Cân nặng đang chững lại. Hãy xem lại chế độ ăn và cường độ tập.';

/** Tiêu đề "Cân nặng" và nút nhỏ nền `primary` "Ghi lại" (ảnh 11). */
function WeightHeader() {
  const theme = useTheme();
  return (
    <View style={styles.header}>
      <AppText variant="title" accessibilityRole="header" style={styles.title}>
        Cân nặng
      </AppText>
      <Pressable
        onPress={() => router.push('/stats/record-weight')}
        accessibilityRole="button"
        accessibilityLabel="Ghi lại"
        style={[styles.recordButton, { backgroundColor: theme.primary }]}
      >
        <AppText variant="button" color={theme.onPrimary}>
          Ghi lại
        </AppText>
      </Pressable>
    </View>
  );
}

/** Cảnh báo chững cân theo `dashboard.is_plateau`, màu `flame` (spec §2.2 ý 4, §6 ý 7). */
function PlateauWarning() {
  const theme = useTheme();
  return (
    <View style={styles.warning} accessibilityRole="alert">
      <Ionicons name="warning" size={sizes.touch / 2} color={theme.flame} />
      <AppText variant="meta" color={theme.flame} style={styles.warningText}>
        {PLATEAU_MESSAGE}
      </AppText>
    </View>
  );
}

/** "Cân nặng" (spec §2.2 ý 4): chưa có số đo thì trạng thái rỗng, nút "Ghi lại" vẫn hiện. */
export function WeightSection({ metrics, isPlateau, unitSystem }: Props) {
  return (
    <View testID="weight-section">
      <WeightHeader />
      <ReportCard>
        {metrics ? (
          <WeightTrendBlock currentKg={metrics.weight_kg} unitSystem={unitSystem} />
        ) : (
          <EmptyState title="Chưa có số đo cơ thể" icon="scale-outline" />
        )}
        {isPlateau && <PlateauWarning />}
      </ReportCard>
    </View>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.md },
  title: { flex: 1 },
  recordButton: {
    minHeight: sizes.touch,
    justifyContent: 'center',
    borderRadius: radius.pill,
    paddingHorizontal: spacing.xl,
  },
  warning: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  warningText: { flex: 1 },
});
