import { router } from 'expo-router';
import { View } from 'react-native';

import { AppText, buildWeek, SectionHeader, WeekStrip } from '@/components/common';
import { useTheme } from '@/styles/theme';
import type { WeekProgress } from '@/types/dashboard';
import { formatNumber } from '@/utils/format';

import { CardDivider, ReportCard } from './ReportCard';

type Props = { week: WeekProgress; canOpenReports: boolean };

const openReports = () => router.push('/stats/reports');

/**
 * "Lịch sử" tuần này (spec §2.2 ý 3). `WeekStrip` chỉ đánh dấu hôm nay: `/dashboard` chưa trả ngày đã tập
 * và chuỗi ngày (Q1), module KHÔNG gọi `/workout-sessions`.
 */
export function HistorySection({ week, canOpenReports }: Props) {
  const theme = useTheme();
  return (
    <View>
      <SectionHeader
        title="Lịch sử"
        onMore={canOpenReports ? openReports : undefined}
        moreLabel="Báo cáo đã xuất"
      />
      <ReportCard>
        <WeekStrip days={buildWeek(new Date(), [])} />
        <CardDivider />
        <AppText variant="meta" color={theme.textMuted}>
          {`Tuần này: ${week.sessions_completed} buổi`}
        </AppText>
        <AppText variant="meta" color={theme.textMuted}>
          {`Theo lịch: ${week.completed_planned_count}/${week.planned_count} buổi`}
        </AppText>
        {week.adherence_pct !== null && (
          <AppText variant="meta" color={theme.textMuted}>
            {`Tuân thủ ${formatNumber(week.adherence_pct, 0)}%`}
          </AppText>
        )}
      </ReportCard>
    </View>
  );
}
