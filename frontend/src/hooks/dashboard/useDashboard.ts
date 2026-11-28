/** Tổng quan tab Báo cáo `GET /dashboard` (spec fe-dashboard §2.3). */
import { useQuery } from '@tanstack/react-query';

import { getDashboard } from '@/services/dashboard';

// Tiền tố chung: invalidate `['dashboard']` tải lại cả tổng quan lẫn biểu đồ cân nặng (spec §6 ý 9).
export const DASHBOARD_QUERY_KEY = ['dashboard'] as const;

export function useDashboard() {
  return useQuery({ queryKey: DASHBOARD_QUERY_KEY, queryFn: getDashboard });
}
