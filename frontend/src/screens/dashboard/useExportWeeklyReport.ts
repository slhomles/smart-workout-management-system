/** "Xuất báo cáo tuần" qua `POST /reports` (spec §2.2 "Xuất báo cáo tuần", §2.4, §6 ý 5). */
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useRef, useState } from 'react';

import { screenErrorMessage } from '@/screens/profile/screen-error';
import { createReport } from '@/services/dashboard';

import { previousWeekStart } from './report-utils';

// Tiền tố của mọi danh sách báo cáo (`['reports','weekly_summary']`), để màn "Báo cáo đã xuất" tải lại.
const REPORTS_QUERY_KEY = ['reports'] as const;
const EXPORT_ERROR_MESSAGES = { report_already_exists: 'Báo cáo tuần trước đã được xuất' };

/** Kỳ xuất là tuần trước, tuần đã trọn vẹn, theo ngày giờ máy (spec §6 ý 5). */
function exportPreviousWeek() {
  return createReport({ report_type: 'weekly_summary', period_start: previousWeekStart(new Date()) });
}

export function useExportWeeklyReport() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  // `isPending` chỉ đổi sau lần render kế tiếp; ref chặn ngay lần bấm thứ hai trong cùng khung hình.
  const isSendingRef = useRef(false);
  const mutation = useMutation({
    mutationFn: exportPreviousWeek,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: REPORTS_QUERY_KEY });
      router.push('/stats/reports');
    },
    onError: (err) => setError(screenErrorMessage(err, EXPORT_ERROR_MESSAGES)),
    onSettled: () => {
      isSendingRef.current = false;
    },
  });

  const exportReport = () => {
    if (isSendingRef.current) return;
    isSendingRef.current = true;
    setError(null);
    mutation.mutate();
  };

  return { exportReport, isPending: mutation.isPending, error };
}
