// Báo cáo đã xuất (spec fe-dashboard §2.1, §2.2 "Báo cáo đã xuất", §2.4; thẻ danh sách theo ảnh mẫu 04).
// Đủ 4 trạng thái theo `GET /reports`: tải, lỗi có "Thử lại", rỗng, có dữ liệu (frontend-standards §4).
import { ActivityIndicator, FlatList, StyleSheet, View } from 'react-native';

import { EmptyState, ErrorState, GradientButton, LoadingState, Screen } from '@/components/common';
import { useWeeklyReports, type WeeklyReportsQuery } from '@/hooks/dashboard/useWeeklyReports';
import { AccountHeader } from '@/screens/profile/AccountHeader';
import { FormAlert } from '@/screens/profile/FormAlert';
import { MeStates } from '@/screens/profile/MeStates';
import { screenErrorMessage } from '@/screens/profile/screen-error';
import { spacing, useTheme } from '@/styles/theme';
import type { UnitSystem } from '@/types/auth';

import { ReportListCard } from './ReportListCard';

/** Trạng thái tải trang sau ở cuối danh sách; trang sau lỗi thì giữ các trang đã có và cho thử lại. */
function ReportListFooter({ query }: { query: WeeklyReportsQuery }) {
  const theme = useTheme();
  if (query.isFetchingNextPage) return <ActivityIndicator color={theme.primary} style={styles.footer} />;
  if (!query.isFetchNextPageError) return null;
  return (
    <View style={styles.footer}>
      <FormAlert message={screenErrorMessage(query.error)} />
      <GradientButton label="Thử lại" onPress={() => void query.fetchNextPage()} />
    </View>
  );
}

function ReportList({ query, unitSystem }: { query: WeeklyReportsQuery; unitSystem: UnitSystem | null }) {
  const reports = (query.data?.pages ?? []).flatMap((page) => page.data);
  const loadMore = () => {
    // `onEndReached` có thể gọi lặp: chỉ tải khi còn trang và không đang tải, `cancelRefetch: false` để
    // lần gọi chen giữa không gửi trùng request.
    if (query.hasNextPage && !query.isFetchingNextPage) void query.fetchNextPage({ cancelRefetch: false });
  };
  return (
    <FlatList
      testID="reports-list"
      data={reports}
      keyExtractor={(report) => report.id}
      renderItem={({ item }) => <ReportListCard report={item} unitSystem={unitSystem} />}
      ListEmptyComponent={<EmptyState title="Chưa có báo cáo nào" icon="document-text-outline" />}
      ListFooterComponent={<ReportListFooter query={query} />}
      onEndReached={loadMore}
      onEndReachedThreshold={0.5}
      contentContainerStyle={styles.list}
    />
  );
}

/** Đã có dữ liệu thì luôn hiện danh sách, kể cả khi lần tải lại sau đó lỗi, để không mất các trang đã tải. */
function ReportsContent({ unitSystem }: { unitSystem: UnitSystem | null }) {
  const query = useWeeklyReports();
  if (query.data) return <ReportList query={query} unitSystem={unitSystem} />;
  if (query.isError) return <ErrorState message={screenErrorMessage(query.error)} onRetry={() => query.refetch()} />;
  return <LoadingState />;
}

export default function ReportsScreen() {
  return (
    <Screen scroll={false} header={<AccountHeader title="Báo cáo đã xuất" />}>
      <MeStates>{(me) => <ReportsContent unitSystem={me.unit_system} />}</MeStates>
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { gap: spacing.md, paddingBottom: spacing.lg },
  footer: { gap: spacing.md, paddingVertical: spacing.lg },
});
