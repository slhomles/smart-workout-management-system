/**
 * Service mục tiêu `/body` (spec fe-auth §2.3, §6 ý 3). Mọi hàm trả thẳng `res.data`;
 * danh sách có dạng `Page<T>` (`Claude_api_respone.md` §5).
 */
import type { Page } from '@/types/page';
import type { CreateGoalRequest, GoalType, ListGoalsParams, UpdateGoalRequest, UserGoal } from '@/types/profile';

import { api } from './api/client';

export async function listGoals(params: ListGoalsParams): Promise<Page<UserGoal>> {
  const res = await api.get<Page<UserGoal>>('/body/goals', { params });
  return res.data;
}

export async function listGoalTypes(): Promise<Page<GoalType>> {
  const res = await api.get<Page<GoalType>>('/body/goal-types');
  return res.data;
}

export async function createGoal(body: CreateGoalRequest): Promise<UserGoal> {
  const res = await api.post<UserGoal>('/body/goals', body);
  return res.data;
}

/** Đóng mục tiêu bằng `status` achieved/abandoned. */
export async function updateGoal(goalId: string, body: UpdateGoalRequest): Promise<UserGoal> {
  const res = await api.patch<UserGoal>(`/body/goals/${goalId}`, body);
  return res.data;
}
