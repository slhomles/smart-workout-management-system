/**
 * Kiểu dữ liệu mục tiêu `/body` (chức năng 3), khớp `backend/app/schemas/body.py`.
 * UUID là `string`, ID danh mục là `number` (frontend-standards §3); cân nặng luôn là kg.
 */

export type GoalStatus = 'active' | 'achieved' | 'abandoned';

export type GoalType = {
  id: number;
  code: string;
  name: string;
  description: string | null;
};

export type UserGoal = {
  id: string;
  goal_type: { id: number; code: string; name: string };
  target_weight_kg: number | null;
  target_body_fat_pct: number | null;
  /** Ngày dạng `yyyy-mm-dd`. */
  start_date: string;
  target_date: string | null;
  status: GoalStatus;
  closed_at: string | null;
  created_at: string;
  updated_at: string;
};

/** Field để trống thì không gửi key (spec fe-auth FEAUTH-20). */
export type CreateGoalRequest = {
  goal_type_id: number;
  target_weight_kg?: number;
  target_date?: string;
};

export type UpdateGoalRequest = { status: 'achieved' | 'abandoned' };

export type ListGoalsParams = {
  limit?: number;
  cursor?: string;
  status?: GoalStatus;
};
