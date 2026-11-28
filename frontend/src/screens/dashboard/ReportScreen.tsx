// Tab "Báo cáo" (spec fe-dashboard §2.1, §2.2; frontend-standards §8.3; ảnh mẫu 11, 12).
// Đủ 4 trạng thái theo `GET /dashboard`: tải, lỗi có "Thử lại", rỗng (newbie), có dữ liệu (frontend-standards §4).
import { EmptyState, ErrorState, LoadingState, Screen, ScreenHeader } from '@/components/common';
import { useDashboard } from '@/hooks/dashboard/useDashboard';
import { MeStates } from '@/screens/profile/MeStates';
import { screenErrorMessage } from '@/screens/profile/screen-error';
import type { Me, UnitSystem } from '@/types/auth';
import type { Dashboard } from '@/types/dashboard';

import { BmiSection } from './BmiSection';
import { ExportReportButton } from './ExportReportButton';
import { HistorySection } from './HistorySection';
import { RecoverySection } from './RecoverySection';
import { TodaySection } from './TodaySection';
import { WeightSection } from './WeightSection';

// Ẩn/hiện chỉ theo `me.permissions`, không suy từ tên role (doc 04 §7 ý 7; spec §6 ý 3).
const BODY_METRIC_PERMISSION = 'body_metric:manage_own';
const WORKOUT_PERMISSION = 'workout:manage_own';
const REPORT_EXPORT_PERMISSION = 'report:export_own';

type Access = { canViewRecovery: boolean; canExport: boolean };
type ContentProps = { unitSystem: UnitSystem | null; access: Access };

function ReportSections({ dashboard, unitSystem, access }: ContentProps & { dashboard: Dashboard }) {
  return (
    <>
      <TodaySection today={dashboard.today} unitSystem={unitSystem} />
      <HistorySection week={dashboard.this_week} canOpenReports={access.canExport} />
      <WeightSection metrics={dashboard.latest_metrics} isPlateau={dashboard.is_plateau} unitSystem={unitSystem} />
      <BmiSection metrics={dashboard.latest_metrics} />
      {access.canViewRecovery && <RecoverySection />}
      {access.canExport && <ExportReportButton />}
    </>
  );
}

/** Đã có dữ liệu thì luôn hiện nội dung, kể cả khi lần tải lại sau đó lỗi. */
function DashboardContent({ unitSystem, access }: ContentProps) {
  const dashboard = useDashboard();
  if (dashboard.data) return <ReportSections dashboard={dashboard.data} unitSystem={unitSystem} access={access} />;
  if (dashboard.isError) {
    return <ErrorState message={screenErrorMessage(dashboard.error)} onRetry={() => dashboard.refetch()} />;
  }
  return <LoadingState />;
}

/** Thiếu `body_metric:manage_own` thì không mount phần gọi `/dashboard`, `/body`, `/recovery` (spec §2.2 "Quyền"). */
function ReportContent({ me }: { me: Me }) {
  const permissions = new Set(me.permissions);
  if (!permissions.has(BODY_METRIC_PERMISSION)) {
    return <EmptyState title="Bạn không có quyền xem báo cáo" icon="lock-closed-outline" />;
  }
  const access = { canViewRecovery: permissions.has(WORKOUT_PERMISSION), canExport: permissions.has(REPORT_EXPORT_PERMISSION) };
  return <DashboardContent unitSystem={me.unit_system} access={access} />;
}

export default function ReportScreen() {
  // Không truyền `streakDays`: `/dashboard` chưa trả chuỗi ngày tập (spec §2.2 ý 1, Q1).
  return (
    <Screen header={<ScreenHeader title="Báo cáo" />}>
      <MeStates>{(me) => <ReportContent me={me} />}</MeStates>
    </Screen>
  );
}
