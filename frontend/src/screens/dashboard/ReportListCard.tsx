// Thẻ một báo cáo tuần đã xuất (spec fe-dashboard §2.2 "Báo cáo đã xuất"; thẻ danh sách theo ảnh mẫu 04).
// KHÔNG hiện calo tiêu hao `est_calories_burned_kcal` (spec §3, §6 ý 4).
import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/common';
import { radius, spacing, useTheme } from '@/styles/theme';
import type { UnitSystem } from '@/types/auth';
import type { ReportExport, ReportSummary } from '@/types/dashboard';
import { formatDate, formatNumber } from '@/utils/format';
import { formatWeight } from '@/utils/units';

import { lastDayOfPeriod } from './report-utils';

/** "Tuần 16/11/2026 – 22/11/2026": `period_end` không bao gồm nên hiện ngày liền trước. */
function periodTitle(report: ReportExport): string {
  return `Tuần ${formatDate(report.period_start)} – ${formatDate(lastDayOfPeriod(report.period_end))}`;
}

/** "3 buổi • 12.450 kg • 185 phút", khối lượng theo đơn vị hiển thị (`null` = metric). */
function totalsLine(summary: ReportSummary, unitSystem: UnitSystem | null): string {
  const volume = formatWeight(summary.total_volume_kg, unitSystem);
  return `${summary.sessions_completed} buổi • ${volume} • ${formatNumber(summary.duration_minutes, 0)} phút`;
}

type Props = { report: ReportExport; unitSystem: UnitSystem | null };

export function ReportListCard({ report, unitSystem }: Props) {
  const theme = useTheme();
  const { summary } = report;
  return (
    <View testID={`report-${report.id}`} style={[styles.card, { backgroundColor: theme.surface }]}>
      <AppText variant="itemTitle">{periodTitle(report)}</AppText>
      <AppText variant="meta" color={theme.textMuted}>
        {totalsLine(summary, unitSystem)}
      </AppText>
      {summary.adherence_pct !== null ? (
        <AppText variant="meta" color={theme.textMuted}>
          {`Tuân thủ ${formatNumber(summary.adherence_pct, 0)}%`}
        </AppText>
      ) : null}
      {summary.avg_weight_kg !== null ? (
        <AppText variant="meta" color={theme.textMuted}>
          {`Cân nặng TB ${formatWeight(summary.avg_weight_kg, unitSystem)}`}
        </AppText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: spacing.lg, gap: spacing.xs },
});
