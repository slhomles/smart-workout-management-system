/**
 * Danh sách mục tiêu `GET /body/goals`, phân trang cursor bằng `useInfiniteQuery`
 * (spec fe-auth §2.2 "Mục tiêu", §6 ý 13; Claude_api_respone.md §5; frontend-standards §3).
 */
import { useInfiniteQuery } from '@tanstack/react-query';

import { listGoals } from '@/services/profile';
import type { Page } from '@/types/page';
import type { ListGoalsParams, UserGoal } from '@/types/profile';

export const GOALS_QUERY_KEY = ['body', 'goals'] as const;

const GOALS_PAGE_SIZE = 20;

/** Trang đầu không gửi `cursor`; cursor là chuỗi mờ lấy nguyên từ `next_cursor`, client không tự tạo. */
function goalsParams(cursor: string | undefined): ListGoalsParams {
  return cursor ? { limit: GOALS_PAGE_SIZE, cursor } : { limit: GOALS_PAGE_SIZE };
}

function nextGoalsCursor(page: Page<UserGoal>): string | undefined {
  return page.pagination.has_more ? (page.pagination.next_cursor ?? undefined) : undefined;
}

export function useGoals() {
  return useInfiniteQuery({
    queryKey: GOALS_QUERY_KEY,
    queryFn: ({ pageParam }) => listGoals(goalsParams(pageParam)),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: nextGoalsCursor,
  });
}

export type GoalsQuery = ReturnType<typeof useGoals>;
