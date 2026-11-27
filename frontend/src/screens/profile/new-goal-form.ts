/**
 * Logic thuần của form Đặt mục tiêu (spec fe-auth §2.2 "Đặt mục tiêu", §2.4, §6 ý 10, 11): kiểm tra phía client,
 * dựng body `POST /body/goals` và quy lỗi server về thông điệp. Giới hạn theo `CreateUserGoalRequest` của backend.
 */
import { hasFormErrors, toFormErrors, type FormErrors } from '@/screens/auth/form-errors';
import type { UnitSystem } from '@/types/auth';
import type { CreateGoalRequest } from '@/types/profile';
import { parseDateVi, parseDecimalVi } from '@/utils/format';
import { lbToKg } from '@/utils/units';

/** Field của API có chỗ hiện lỗi trên form; `goal_type_id` hiện dưới nhóm Chip. */
export type NewGoalField = 'goal_type_id' | 'target_weight_kg' | 'target_date';
/** Giá trị đang nhập: cân nặng theo `unit_system` (kg hoặc lb), ngày `dd/mm/yyyy`. */
export type NewGoalInput = { goal_type_id: number | null; target_weight: string; target_date: string };
export type NewGoalValidation = { errors: FormErrors<NewGoalField>; body: CreateGoalRequest | null };

const GOAL_TYPE_REQUIRED_MESSAGE = 'Vui lòng chọn loại mục tiêu';
const TARGET_WEIGHT_RANGE_MESSAGE = 'Cân nặng mục tiêu phải từ 20 đến 400 kg';
const DATE_FORMAT_MESSAGE = 'Ngày phải có dạng dd/mm/yyyy';
const ACTIVE_GOAL_ALREADY_EXISTS = 'active_goal_already_exists';
const ACTIVE_GOAL_ALREADY_EXISTS_MESSAGE = 'Bạn đang có một mục tiêu chưa hoàn thành. Hãy đóng mục tiêu cũ trước.';

export const EMPTY_NEW_GOAL_INPUT: NewGoalInput = { goal_type_id: null, target_weight: '', target_date: '' };

const NEW_GOAL_FIELDS: readonly NewGoalField[] = ['goal_type_id', 'target_weight_kg', 'target_date'];
// `ck_user_goals_target_weight` (05_body.sql) và `CreateUserGoalRequest.target_weight_kg` (ge=20, le=400).
const MIN_TARGET_WEIGHT_KG = 20;
const MAX_TARGET_WEIGHT_KG = 400;

/** Kết quả kiểm một ô tuỳ chọn: ô trống thì không có cả `value` lẫn `error` (không gửi key). */
type OptionalCheck<T> = { value?: T; error?: string };

/** Đổi sang kg rồi làm tròn 2 chữ số theo cột `numeric(5,2)`; không phải số thì `null`. */
export function toTargetWeightKg(text: string, unitSystem: UnitSystem): number | null {
  const value = parseDecimalVi(text);
  if (value === null) return null;
  const kg = unitSystem === 'imperial' ? lbToKg(value) : value;
  return Math.round(kg * 100) / 100;
}

// Kiểm khoảng trên giá trị đã làm tròn, vì đó là giá trị sẽ gửi lên server.
function checkTargetWeight(text: string, unitSystem: UnitSystem): OptionalCheck<number> {
  const trimmed = text.trim();
  if (trimmed === '') return {};
  const kg = toTargetWeightKg(trimmed, unitSystem);
  if (kg === null || kg < MIN_TARGET_WEIGHT_KG || kg > MAX_TARGET_WEIGHT_KG) return { error: TARGET_WEIGHT_RANGE_MESSAGE };
  return { value: kg };
}

// Điều kiện `target_date > start_date` do server kiểm (spec fe-auth §6 ý 11).
function checkTargetDate(text: string): OptionalCheck<string> {
  const trimmed = text.trim();
  if (trimmed === '') return {};
  const isoDate = parseDateVi(trimmed);
  return isoDate ? { value: isoDate } : { error: DATE_FORMAT_MESSAGE };
}

function buildBody(goalTypeId: number, weight: OptionalCheck<number>, date: OptionalCheck<string>): CreateGoalRequest {
  const body: CreateGoalRequest = { goal_type_id: goalTypeId };
  if (weight.value !== undefined) body.target_weight_kg = weight.value;
  if (date.value !== undefined) body.target_date = date.value;
  return body;
}

/** Trả mọi lỗi client cùng lúc; `body` chỉ có khi không còn lỗi. */
export function validateNewGoal(input: NewGoalInput, unitSystem: UnitSystem): NewGoalValidation {
  const weight = checkTargetWeight(input.target_weight, unitSystem);
  const date = checkTargetDate(input.target_date);
  const fields: Partial<Record<NewGoalField, string>> = {};
  if (input.goal_type_id === null) fields.goal_type_id = GOAL_TYPE_REQUIRED_MESSAGE;
  if (weight.error) fields.target_weight_kg = weight.error;
  if (date.error) fields.target_date = date.error;
  const errors: FormErrors<NewGoalField> = { fields, form: null };
  if (input.goal_type_id === null || hasFormErrors(errors)) return { errors, body: null };
  return { errors, body: buildBody(input.goal_type_id, weight, date) };
}

/** 409 hiện thông điệp chung; 422 hiện dưới ô theo `details[].field` (spec fe-auth §2.4). */
export function toNewGoalErrors(err: unknown): FormErrors<NewGoalField> {
  return toFormErrors<NewGoalField>(err, {
    fields: NEW_GOAL_FIELDS,
    messages: { [ACTIVE_GOAL_ALREADY_EXISTS]: ACTIVE_GOAL_ALREADY_EXISTS_MESSAGE },
  });
}
