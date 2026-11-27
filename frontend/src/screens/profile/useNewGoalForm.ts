/** Trạng thái và thao tác lưu của form Đặt mục tiêu (spec fe-auth §2.2 "Đặt mục tiêu"). */
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';

import { useSingleFlight } from '@/hooks/auth/useSingleFlight';
import { GOALS_QUERY_KEY } from '@/hooks/profile/useGoals';
import { emptyFormErrors, type FormErrors } from '@/screens/auth/form-errors';
import { createGoal } from '@/services/profile';
import type { UnitSystem } from '@/types/auth';
import type { CreateGoalRequest } from '@/types/profile';

import {
  EMPTY_NEW_GOAL_INPUT,
  toNewGoalErrors,
  validateNewGoal,
  type NewGoalField,
  type NewGoalInput,
} from './new-goal-form';

export type NewGoalTextField = 'target_weight' | 'target_date';

/** Trả lỗi để hiện trên form nếu `createGoal` lỗi; thành công thì đánh dấu danh sách mục tiêu cần tải lại. */
async function saveGoal(queryClient: QueryClient, body: CreateGoalRequest): Promise<FormErrors<NewGoalField> | null> {
  try {
    await createGoal(body);
  } catch (err) {
    return toNewGoalErrors(err);
  }
  // Không chờ tải lại: màn Mục tiêu bên dưới tự cập nhật sau khi quay lại.
  void queryClient.invalidateQueries({ queryKey: GOALS_QUERY_KEY });
  return null;
}

/** `unitSystem` quyết định cân nặng nhập theo kg hay lb (spec fe-auth §6 ý 10). */
export function useNewGoalForm(unitSystem: UnitSystem) {
  const queryClient = useQueryClient();
  const [values, setValues] = useState<NewGoalInput>(EMPTY_NEW_GOAL_INPUT);
  const [errors, setErrors] = useState<FormErrors<NewGoalField>>(emptyFormErrors);

  const setText = (field: NewGoalTextField) => (text: string) => setValues((prev) => ({ ...prev, [field]: text }));
  const selectGoalType = (goalTypeId: number) => setValues((prev) => ({ ...prev, goal_type_id: goalTypeId }));

  const { run, isPending } = useSingleFlight(async () => {
    const { errors: clientErrors, body } = validateNewGoal(values, unitSystem);
    setErrors(clientErrors);
    if (!body) return;
    const serverErrors = await saveGoal(queryClient, body);
    if (serverErrors) setErrors(serverErrors);
    else router.back();
  });

  return { values, setText, selectGoalType, errors, isSubmitting: isPending, submit: run };
}
