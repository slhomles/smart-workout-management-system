// Mục tiêu (spec fe-auth §2.1, §2.2 "Mục tiêu", §2.4, §4; phong cách ảnh mẫu 13, thẻ danh sách theo ảnh 04,
// nút theo ảnh 08). Đủ 4 trạng thái: tải, lỗi có "Thử lại", rỗng, có dữ liệu (frontend-standards §4).
import { router } from 'expo-router';
import { ActivityIndicator, FlatList, StyleSheet, View } from 'react-native';

import { EmptyState, ErrorState, GradientButton, LoadingState, Screen } from '@/components/common';
import { useGoals, type GoalsQuery } from '@/hooks/profile/useGoals';
import { spacing, useTheme } from '@/styles/theme';
import type { UnitSystem } from '@/types/auth';

import { AccountHeader } from './AccountHeader';
import { FormAlert } from './FormAlert';
import { GoalCard } from './GoalCard';
import { MeStates } from './MeStates';
import { screenErrorMessage } from './screen-error';
import { useCloseGoal } from './useCloseGoal';

/** Trạng thái tải trang sau ở cuối danh sách; trang sau lỗi thì giữ các trang đã có và cho thử lại. */
function GoalListFooter({ query }: { query: GoalsQuery }) {
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

function GoalList({ query, unitSystem }: { query: GoalsQuery; unitSystem: UnitSystem | null }) {
  const closeGoal = useCloseGoal();
  const goals = (query.data?.pages ?? []).flatMap((page) => page.data);
  const loadMore = () => {
    // `onEndReached` có thể gọi lặp: chỉ tải khi còn trang và không đang tải, `cancelRefetch: false` để
    // lần gọi chen giữa không gửi trùng request.
    if (query.hasNextPage && !query.isFetchingNextPage) void query.fetchNextPage({ cancelRefetch: false });
  };
  return (
    <View style={styles.fill}>
      <GradientButton label="Đặt mục tiêu mới" onPress={() => router.push('/account/new-goal')} />
      <FormAlert message={closeGoal.error} />
      <FlatList
        testID="goals-list"
        data={goals}
        keyExtractor={(goal) => goal.id}
        renderItem={({ item }) => (
          <GoalCard goal={item} unitSystem={unitSystem} isClosing={closeGoal.isPending} onClose={closeGoal.close} />
        )}
        ListEmptyComponent={<EmptyState title="Chưa có mục tiêu" icon="flag-outline" />}
        ListFooterComponent={<GoalListFooter query={query} />}
        onEndReached={loadMore}
        onEndReachedThreshold={0.5}
        contentContainerStyle={styles.list}
      />
    </View>
  );
}

/** Đã có dữ liệu thì luôn hiện danh sách, kể cả khi lần tải lại sau đó lỗi, để không mất các trang đã tải. */
function GoalsContent({ unitSystem }: { unitSystem: UnitSystem | null }) {
  const query = useGoals();
  if (query.data) return <GoalList query={query} unitSystem={unitSystem} />;
  if (query.isError) return <ErrorState message={screenErrorMessage(query.error)} onRetry={() => query.refetch()} />;
  return <LoadingState />;
}

export default function GoalsScreen() {
  return (
    <Screen scroll={false} header={<AccountHeader title="Mục tiêu" />}>
      <MeStates>{(me) => <GoalsContent unitSystem={me.unit_system} />}</MeStates>
    </Screen>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, gap: spacing.lg },
  list: { gap: spacing.md, paddingBottom: spacing.lg },
  footer: { gap: spacing.md, paddingVertical: spacing.lg },
});
