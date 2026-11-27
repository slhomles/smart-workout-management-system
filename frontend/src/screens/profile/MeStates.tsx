import type { ReactNode } from 'react';

import { ErrorState, LoadingState } from '@/components/common';
import { useMe } from '@/hooks/auth/useMe';
import { getErrorMessage } from '@/services/api/errors';
import type { Me } from '@/types/auth';

/**
 * Trạng thái của `GET /auth/me` cho các màn trong `account/` (frontend-standards §4): tải, lỗi có "Thử lại",
 * có dữ liệu. Không có trạng thái rỗng vì `/auth/me` luôn trả một resource (spec fe-auth §6 ý 14).
 * Đã có dữ liệu thì luôn hiện nội dung, kể cả khi lần tải lại sau đó lỗi, để không mất dữ liệu đang nhập.
 */
export function MeStates({ children }: { children: (me: Me) => ReactNode }) {
  const me = useMe();
  if (me.data) return children(me.data);
  if (me.isError) return <ErrorState message={getErrorMessage(me.error)} onRetry={() => me.refetch()} />;
  return <LoadingState />;
}
