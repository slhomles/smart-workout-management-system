// Giữ chỗ cho tab "Báo cáo". Module `fe-dashboard` thay bằng màn báo cáo thật (frontend-standards §8.3).
import { EmptyState, Screen, ScreenHeader } from '@/components/common';

export default function ReportScreen() {
  return (
    <Screen header={<ScreenHeader title="Báo cáo" />}>
      <EmptyState title="Báo cáo đang được xây dựng" message="Lịch sử tập, cân nặng, BMI và báo cáo tuần." icon="bar-chart-outline" />
    </Screen>
  );
}
