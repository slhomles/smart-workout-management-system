// Giữ chỗ cho tab "Khám phá". Module `fe-exercise-wiki` thay bằng màn tìm kiếm thật (frontend-standards §8.3).
import { EmptyState, Screen, ScreenHeader } from '@/components/common';

export default function ExploreScreen() {
  return (
    <Screen header={<ScreenHeader title="Khám phá" />}>
      <EmptyState title="Thư viện bài tập đang được xây dựng" message="Tìm kiếm, lọc theo nhóm cơ, thiết bị, cấp độ." icon="compass-outline" />
    </Screen>
  );
}
