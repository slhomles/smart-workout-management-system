/** Trạng thái phục hồi nhóm cơ `GET /recovery/muscle-groups` (spec fe-dashboard §2.3, §6 ý 11). */
import { useQuery } from '@tanstack/react-query';

import { listMuscleRecovery } from '@/services/dashboard';

export const MUSCLE_RECOVERY_QUERY_KEY = ['recovery', 'muscle-groups'] as const;

// Giới hạn tối đa của API; số nhóm cơ ít hơn 100 nên một trang là đủ, không cần phân trang (spec §6 ý 11).
const RECOVERY_PAGE_SIZE = 100;

export function useMuscleRecovery() {
  return useQuery({
    queryKey: MUSCLE_RECOVERY_QUERY_KEY,
    queryFn: () => listMuscleRecovery({ limit: RECOVERY_PAGE_SIZE }),
  });
}
