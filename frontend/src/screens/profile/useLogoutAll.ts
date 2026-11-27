/** Đăng xuất khỏi mọi thiết bị (doc 04 §4.5; spec fe-auth §2.2 "Đăng xuất mọi thiết bị", §6 ý 5). */
import { useState } from 'react';
import { Alert } from 'react-native';

import { useEndSession } from '@/hooks/auth/useEndSession';
import { useSingleFlight } from '@/hooks/auth/useSingleFlight';
import { toFormErrors } from '@/screens/auth/form-errors';
import { getErrorMessage } from '@/services/api/errors';
import { logoutAll } from '@/services/auth';

const CONFIRM_TITLE = 'Đăng xuất khỏi mọi thiết bị?';
const CONFIRM_MESSAGE = 'Mọi thiết bị đang đăng nhập tài khoản này, kể cả máy này, sẽ phải đăng nhập lại.';

/** Trả thông điệp lỗi để hiện, hoặc `null` khi server đã thu hồi xong. */
async function revokeAllSessions(): Promise<string | null> {
  try {
    await logoutAll();
    return null;
  } catch (err) {
    // Rẽ nhánh theo `error.code`: `permission_denied` có thông điệp riêng, mã khác và lỗi mạng dùng
    // `getErrorMessage` (spec fe-auth §2.4). Phiên vẫn giữ nguyên.
    return toFormErrors(err, { fields: [] }).form ?? getErrorMessage(err);
  }
}

export function useLogoutAll() {
  const endSession = useEndSession();
  const [error, setError] = useState<string | null>(null);
  const { run, isPending } = useSingleFlight(async () => {
    setError(null);
    const failure = await revokeAllSessions();
    // Server đã thu hồi mọi refresh token nên chỉ xoá phiên ở máy, KHÔNG gọi `/auth/logout`.
    if (failure === null) await endSession('/login');
    else setError(failure);
  });

  const confirm = () =>
    Alert.alert(CONFIRM_TITLE, CONFIRM_MESSAGE, [
      { text: 'Huỷ', style: 'cancel' },
      { text: 'Đăng xuất tất cả', style: 'destructive', onPress: run },
    ]);

  return { confirm, isPending, error };
}
