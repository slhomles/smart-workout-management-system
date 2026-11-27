/** Danh mục loại mục tiêu `GET /body/goal-types` (spec fe-auth §2.3, §6 ý 3, ý 13). */
import { useQuery } from '@tanstack/react-query';

import { listGoalTypes } from '@/services/profile';
import type { Page } from '@/types/page';
import type { GoalType } from '@/types/profile';

export const GOAL_TYPES_QUERY_KEY = ['body', 'goal-types'] as const;

// Cache giữ nguyên `Page` của API; backend trả danh mục nhỏ trong một trang duy nhất (`endpoints/body.py`).
function selectGoalTypes(page: Page<GoalType>): GoalType[] {
  return page.data;
}

export function useGoalTypes() {
  return useQuery({ queryKey: GOAL_TYPES_QUERY_KEY, queryFn: () => listGoalTypes(), select: selectGoalTypes });
}
