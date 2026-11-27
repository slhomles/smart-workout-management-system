/** Đóng mục tiêu `active` qua `PATCH /body/goals/{goal_id}` (spec fe-auth §2.2 "Mục tiêu", §2.4). */
import { useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';

import { useSingleFlight } from '@/hooks/auth/useSingleFlight';
import { GOALS_QUERY_KEY } from '@/hooks/profile/useGoals';
import { getErrorCode } from '@/services/api/errors';
import { updateGoal } from '@/services/profile';
import type { UpdateGoalRequest } from '@/types/profile';

import { screenErrorMessage } from './screen-error';

export type GoalCloseStatus = UpdateGoalRequest['status'];

type CloseRequest = { goalId: string; status: GoalCloseStatus };

const GOAL_NOT_FOUND = 'goal_not_found';
const CLOSE_GOAL_MESSAGES = { [GOAL_NOT_FOUND]: 'Mục tiêu không còn tồn tại' };

/** Trả `true` khi danh sách cần tải lại: đóng thành công, hoặc mục tiêu không còn trên server. */
async function submitClose(request: CloseRequest, onError: (message: string) => void): Promise<boolean> {
  try {
    await updateGoal(request.goalId, { status: request.status });
    return true;
  } catch (err) {
    onError(screenErrorMessage(err, CLOSE_GOAL_MESSAGES));
    return getErrorCode(err) === GOAL_NOT_FOUND;
  }
}

export function useCloseGoal() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  // `useSingleFlight` nhận tác vụ không tham số nên mục tiêu vừa bấm đi qua ref; tác vụ đọc ref trước lần
  // `await` đầu, nên lần bấm bị chặn khi đang gửi không làm đổi yêu cầu đã gửi.
  const requestRef = useRef<CloseRequest | null>(null);
  const { run, isPending } = useSingleFlight(async () => {
    const request = requestRef.current;
    if (!request) return;
    setError(null);
    const shouldReload = await submitClose(request, setError);
    // Chờ tải lại xong mới mở khoá nút, để không bấm đóng lần nữa trên dữ liệu cũ.
    if (shouldReload) await queryClient.invalidateQueries({ queryKey: GOALS_QUERY_KEY });
  });

  const close = async (goalId: string, status: GoalCloseStatus) => {
    requestRef.current = { goalId, status };
    await run();
  };

  return { close, isPending, error };
}
