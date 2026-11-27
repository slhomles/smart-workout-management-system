// Giữ chỗ cho tab "Tập luyện". Module `fe-workout` thay bằng trang chủ thật (frontend-standards §8.3).
import { useQuery } from '@tanstack/react-query';
import { StyleSheet, View } from 'react-native';

import { AppText, EmptyState, ErrorState, LoadingState, Screen, ScreenHeader, SectionHeader } from '@/components/common';
import { getErrorMessage } from '@/services/api/errors';
import { getHealth } from '@/services/health';
import { radius, spacing, useTheme } from '@/styles/theme';

export function HealthCard() {
  const theme = useTheme();
  const health = useQuery({ queryKey: ['health'], queryFn: getHealth });
  if (health.isPending) return <LoadingState label="Đang kiểm tra máy chủ" />;
  if (health.isError) return <ErrorState message={getErrorMessage(health.error)} onRetry={() => health.refetch()} />;
  const rows = [
    ['Cơ sở dữ liệu', health.data.database],
    ['Redis', health.data.redis],
    ['Dịch vụ AI', health.data.ai_service],
  ];
  return (
    <View style={[styles.card, { backgroundColor: theme.surface }]}>
      {rows.map(([label, value]) => (
        <View key={label} style={styles.row}>
          <AppText>{label}</AppText>
          <AppText variant="itemTitle" color={value === 'up' ? theme.primary : theme.accentOrange}>
            {value}
          </AppText>
        </View>
      ))}
    </View>
  );
}

export default function HomeScreen() {
  return (
    <Screen header={<ScreenHeader title="Smart Workout" streakDays={0} />}>
      <View>
        <SectionHeader title="Kết nối máy chủ" />
        <HealthCard />
      </View>
      <EmptyState title="Trang chủ đang được xây dựng" message="Giáo án, lịch tập và trạng thái phục hồi sẽ hiện ở đây." icon="barbell-outline" />
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: spacing.xl, gap: spacing.md },
  row: { flexDirection: 'row', justifyContent: 'space-between' },
});
