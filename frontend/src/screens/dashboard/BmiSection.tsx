import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';

import { AppText, BmiScale, ErrorState, SectionHeader } from '@/components/common';
import { useBodyProfile } from '@/hooks/dashboard/useBodyProfile';
import { screenErrorMessage } from '@/screens/profile/screen-error';
import { radius, sizes, spacing, typography, useTheme } from '@/styles/theme';
import type { LatestMetrics } from '@/types/dashboard';
import { formatNumber } from '@/utils/format';

import { MetricRow } from './MetricRow';
import { CardDivider, ReportCard } from './ReportCard';
import { bmiCategoryLabel } from './report-utils';

const NO_VALUE = '—';

function formatKcal(value: number | null | undefined): string {
  return value == null ? NO_VALUE : `${formatNumber(value, 0)} kcal`;
}

function formatPercent(value: number | null | undefined): string {
  return value == null ? NO_VALUE : `${formatNumber(value, 1)}%`;
}

/** Số BMI lớn, chấm màu và nhãn phân loại của server, rồi `BmiScale` (ảnh 12). FE KHÔNG tự tính BMI (spec §6 ý 6). */
function BmiValue({ bmi, category }: { bmi: number; category: string | null }) {
  const theme = useTheme();
  return (
    <>
      <View style={styles.bmiRow}>
        <AppText style={[typography.number, styles.bmiNumber]}>{formatNumber(bmi, 1)}</AppText>
        <View style={[styles.dot, { backgroundColor: theme.primary }]} />
        <AppText variant="itemTitle">{bmiCategoryLabel(category)}</AppText>
      </View>
      <BmiScale bmi={bmi} />
    </>
  );
}

/** Dòng "Chiều cao" từ `GET /body/profile`, kèm nút bút chì "Sửa chiều cao" (ảnh 12). */
function HeightRow() {
  const theme = useTheme();
  const profile = useBodyProfile();
  const heightCm = profile.data?.height_cm;
  const value = heightCm == null ? 'Chưa có' : `${formatNumber(heightCm, 1)} cm`;
  if (profile.isError && !profile.data) {
    return <ErrorState message={screenErrorMessage(profile.error)} onRetry={() => profile.refetch()} />;
  }
  return (
    <View style={styles.heightRow}>
      <View style={styles.fill}>
        {profile.data ? (
          <MetricRow testID="bmi-height" label="Chiều cao" value={value} />
        ) : (
          <ActivityIndicator accessibilityLabel="Đang tải..." color={theme.primary} />
        )}
      </View>
      <Pressable
        onPress={() => router.push('/stats/height')}
        accessibilityRole="button"
        accessibilityLabel="Sửa chiều cao"
        style={styles.iconButton}
      >
        <Ionicons name="pencil" size={sizes.touch / 2} color={theme.textMuted} />
      </Pressable>
    </View>
  );
}

/** "BMI" (spec §2.2 ý 5): BMI, phân loại, thang BMI, BMR, TDEE, % mỡ và chiều cao. */
export function BmiSection({ metrics }: { metrics: LatestMetrics | null }) {
  const theme = useTheme();
  const bmi = metrics?.bmi ?? null;
  return (
    <View testID="bmi-section">
      <SectionHeader title="BMI" />
      <ReportCard>
        {bmi !== null ? (
          <BmiValue bmi={bmi} category={metrics?.bmi_category ?? null} />
        ) : (
          <AppText variant="meta" color={theme.textMuted}>
            Cần cân nặng và chiều cao để tính BMI
          </AppText>
        )}
        <CardDivider />
        <MetricRow testID="bmi-bmr" label="BMR" value={formatKcal(metrics?.bmr_kcal)} />
        <MetricRow testID="bmi-tdee" label="TDEE" value={formatKcal(metrics?.tdee_kcal)} />
        <MetricRow testID="bmi-body-fat" label="% mỡ" value={formatPercent(metrics?.body_fat_pct)} />
        <CardDivider />
        <HeightRow />
      </ReportCard>
    </View>
  );
}

const styles = StyleSheet.create({
  bmiRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  bmiNumber: { flex: 1 },
  dot: { width: spacing.md, height: spacing.md, borderRadius: radius.pill },
  heightRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  fill: { flex: 1 },
  iconButton: { width: sizes.touch, height: sizes.touch, alignItems: 'center', justifyContent: 'center' },
});
