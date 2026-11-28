/**
 * Báo cáo tuần đã xuất `GET /reports?report_type=weekly_summary`, phân trang cursor bằng `useInfiniteQuery`
 * (spec fe-dashboard §2.2 "Báo cáo đã xuất", §2.3; Claude_api_respone.md §5; frontend-standards §3).
 */
import { useInfiniteQuery } from '@tanstack/react-query';

import { listReports } from '@/services/dashboard';
import type { ListReportsParams, ReportExport } from '@/types/dashboard';
import type { Page } from '@/types/page';

// Nằm dưới tiền tố `['reports']`: xuất báo cáo xong invalidate `['reports']` là danh sách tải lại.
export const WEEKLY_REPORTS_QUERY_KEY = ['reports', 'weekly_summary'] as const;

const REPORTS_PAGE_SIZE = 20;

/** Trang đầu không gửi `cursor`; cursor là chuỗi mờ lấy nguyên từ `next_cursor`, client không tự tạo. */
function weeklyReportsParams(cursor: string | undefined): ListReportsParams {
  const params: ListReportsParams = { report_type: 'weekly_summary', limit: REPORTS_PAGE_SIZE };
  return cursor ? { ...params, cursor } : params;
}

function nextReportsCursor(page: Page<ReportExport>): string | undefined {
  return page.pagination.has_more ? (page.pagination.next_cursor ?? undefined) : undefined;
}

export function useWeeklyReports() {
  return useInfiniteQuery({
    queryKey: WEEKLY_REPORTS_QUERY_KEY,
    queryFn: ({ pageParam }) => listReports(weeklyReportsParams(pageParam)),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: nextReportsCursor,
  });
}

export type WeeklyReportsQuery = ReturnType<typeof useWeeklyReports>;
