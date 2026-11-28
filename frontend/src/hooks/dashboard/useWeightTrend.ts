/** Xu hướng cân nặng theo tuần `GET /dashboard/weight-trend` (spec fe-dashboard §2.3). */
import { useQuery } from '@tanstack/react-query';

import { getWeightTrend } from '@/services/dashboard';
import type { TrendRange } from '@/types/dashboard';

import { DASHBOARD_QUERY_KEY } from './useDashboard';

export function weightTrendQueryKey(range: TrendRange) {
  return [...DASHBOARD_QUERY_KEY, 'weight-trend', range] as const;
}

export function useWeightTrend(range: TrendRange) {
  return useQuery({ queryKey: weightTrendQueryKey(range), queryFn: () => getWeightTrend(range) });
}

export type WeightTrendQuery = ReturnType<typeof useWeightTrend>;
