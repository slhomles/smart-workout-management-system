import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText, Chip, ErrorState, LineChartCard, LoadingState } from '@/components/common';
import { useWeightTrend, type WeightTrendQuery } from '@/hooks/dashboard/useWeightTrend';
import { screenErrorMessage } from '@/screens/profile/screen-error';
import { spacing, typography, useTheme } from '@/styles/theme';
import type { UnitSystem } from '@/types/auth';
import type { TrendRange, WeightTrendPoint } from '@/types/dashboard';
import { formatNumber } from '@/utils/format';
import { formatWeight } from '@/utils/units';

import { MetricRow } from './MetricRow';
import { weightChartPoints, weightExtremes } from './report-utils';

type Unit = UnitSystem | null;

const RANGE_OPTIONS: { range: TrendRange; label: string }[] = [
  { range: 'month', label: 'Tháng' },
  { range: '3months', label: '3 Tháng' },
];
const NO_VALUE = '—';

function formatOptionalWeight(kg: number | null, unitSystem: Unit): string {
  return kg === null ? NO_VALUE : formatWeight(kg, unitSystem);
}

// Nhãn điểm không kèm đơn vị ("23/11: 70"): đơn vị đã có ở "Hiện tại", "Nặng nhất", "Nhẹ nhất".
const formatChartValue = (value: number) => formatNumber(value);

type SummaryProps = { currentKg: number; points: WeightTrendPoint[]; unitSystem: Unit };

/** "Hiện tại" số lớn bên trái, "Nặng nhất/Nhẹ nhất" bên phải (ảnh 11, 12). Chưa có trend thì hiện "—". */
function WeightSummary({ currentKg, points, unitSystem }: SummaryProps) {
  const theme = useTheme();
  const { heaviestKg, lightestKg } = weightExtremes(points);
  return (
    <View style={styles.summary}>
      <View testID="weight-current" style={styles.current}>
        <AppText variant="body" color={theme.textMuted}>
          Hiện tại
        </AppText>
        <AppText style={typography.number}>{formatWeight(currentKg, unitSystem)}</AppText>
      </View>
      <View style={styles.extremes}>
        <MetricRow testID="weight-heaviest" label="Nặng nhất" value={formatOptionalWeight(heaviestKg, unitSystem)} />
        <MetricRow testID="weight-lightest" label="Nhẹ nhất" value={formatOptionalWeight(lightestKg, unitSystem)} />
      </View>
    </View>
  );
}

function RangeChips({ range, onChange }: { range: TrendRange; onChange: (range: TrendRange) => void }) {
  return (
    <View style={styles.chips}>
      {RANGE_OPTIONS.map((option) => (
        <Chip
          key={option.range}
          label={option.label}
          solid
          selected={option.range === range}
          onPress={() => onChange(option.range)}
        />
      ))}
    </View>
  );
}

/** Trend tải/lỗi hiện ngay trong thẻ, các mục khác của tab vẫn hiện (spec §2.2 ý 4). */
function TrendChart({ trend, unitSystem }: { trend: WeightTrendQuery; unitSystem: Unit }) {
  if (trend.data) {
    return <LineChartCard points={weightChartPoints(trend.data.points, unitSystem)} formatValue={formatChartValue} />;
  }
  if (trend.isError) return <ErrorState message={screenErrorMessage(trend.error)} onRetry={() => trend.refetch()} />;
  return <LoadingState />;
}

/** Cân nặng hiện tại, nặng/nhẹ nhất và biểu đồ theo "Tháng" (mặc định) hoặc "3 Tháng" (spec §2.2 ý 4, §6 ý 7). */
export function WeightTrendBlock({ currentKg, unitSystem }: { currentKg: number; unitSystem: Unit }) {
  const [range, setRange] = useState<TrendRange>('month');
  const trend = useWeightTrend(range);
  return (
    <>
      <WeightSummary currentKg={currentKg} points={trend.data?.points ?? []} unitSystem={unitSystem} />
      <RangeChips range={range} onChange={setRange} />
      <TrendChart trend={trend} unitSystem={unitSystem} />
    </>
  );
}

const styles = StyleSheet.create({
  summary: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.lg },
  current: { flex: 1, gap: spacing.xs },
  extremes: { flex: 1, gap: spacing.sm, paddingTop: spacing.xs },
  chips: { flexDirection: 'row', gap: spacing.sm },
});
