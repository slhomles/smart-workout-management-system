/** Đổi hệ đơn vị hiển thị qua `PATCH /auth/me` (spec fe-auth §2.2 "Đơn vị đo"). */
import { useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';

import { ME_QUERY_KEY } from '@/hooks/auth/useMe';
import { useSingleFlight } from '@/hooks/auth/useSingleFlight';
import { toFormErrors } from '@/screens/auth/form-errors';
import { getErrorMessage } from '@/services/api/errors';
import { updateMe } from '@/services/auth';
import type { UnitSystem } from '@/types/auth';

/**
 * Màn không có ô nhập: `validation_error` thành `message` của server, `permission_denied` có thông điệp riêng,
 * mã khác và lỗi mạng dùng `getErrorMessage` (spec fe-auth §2.4).
 */
function unitSystemError(err: unknown): string {
  return toFormErrors(err, { fields: [] }).form ?? getErrorMessage(err);
}

/** `current` là đơn vị theo dữ liệu server (cache), KHÔNG cập nhật lạc quan. */
export function useUnitSystem(current: UnitSystem) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  // `useSingleFlight` nhận tác vụ không tham số nên đơn vị vừa bấm đi qua ref; tác vụ đọc ref trước lần `await` đầu,
  // nên lần bấm bị chặn khi đang gửi không làm đổi giá trị đã gửi.
  const requestedRef = useRef<UnitSystem>(current);
  const { run, isPending } = useSingleFlight(async () => {
    setError(null);
    try {
      const updated = await updateMe({ unit_system: requestedRef.current });
      // Chip đổi theo cache sau khi server xác nhận.
      queryClient.setQueryData(ME_QUERY_KEY, updated);
    } catch (err) {
      setError(unitSystemError(err));
    }
  });

  const select = async (unit: UnitSystem) => {
    // Bấm Chip đang chọn thì không gọi API (spec fe-auth §2.2).
    if (unit === current) return;
    requestedRef.current = unit;
    await run();
  };

  return { select, isPending, error };
}
