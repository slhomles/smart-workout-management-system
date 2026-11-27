/** Trạng thái và thao tác gửi của form Đổi mật khẩu (doc 04 §4.7; spec fe-auth §2.2 "Đổi mật khẩu", §6 ý 5). */
import { useState } from 'react';

import { useEndSession } from '@/hooks/auth/useEndSession';
import { useSingleFlight } from '@/hooks/auth/useSingleFlight';
import { emptyFormErrors, hasFormErrors, type FormErrors } from '@/screens/auth/form-errors';
import { changePassword } from '@/services/auth';
import type { ChangePasswordRequest } from '@/types/auth';

import {
  toChangePasswordErrors,
  validateChangePassword,
  type ChangePasswordField,
  type ChangePasswordInput,
} from './change-password-errors';

const EMPTY_INPUT: ChangePasswordInput = { current_password: '', new_password: '', new_password_confirm: '' };
const PASSWORD_CHANGED_ROUTE = { pathname: '/login', params: { notice: 'password_changed' } } as const;

/** Trả lỗi để hiện trên form, hoặc `null` khi server đã đổi mật khẩu. */
async function submitChange(body: ChangePasswordRequest): Promise<FormErrors<ChangePasswordField> | null> {
  try {
    await changePassword(body);
    return null;
  } catch (err) {
    // Lỗi đã được quy về thông điệp trên form; không log vì request chứa mật khẩu (doc 04 §6.1, §7).
    return toChangePasswordErrors(err);
  }
}

export function useChangePasswordForm() {
  const endSession = useEndSession();
  const [values, setValues] = useState<ChangePasswordInput>(EMPTY_INPUT);
  const [errors, setErrors] = useState<FormErrors<ChangePasswordField>>(emptyFormErrors);

  const setValue = (field: ChangePasswordField) => (text: string) =>
    setValues((prev) => ({ ...prev, [field]: text }));

  const { run, isPending } = useSingleFlight(async () => {
    const { errors: clientErrors, body } = validateChangePassword(values);
    setErrors(clientErrors);
    if (hasFormErrors(clientErrors)) return;
    const serverErrors = await submitChange(body);
    if (serverErrors) setErrors(serverErrors);
    // Server đã thu hồi mọi refresh token nên chỉ xoá phiên ở máy, KHÔNG gọi `/auth/logout` (doc 04 §4.7).
    else await endSession(PASSWORD_CHANGED_ROUTE);
  });

  return { values, setValue, errors, isSubmitting: isPending, submit: run };
}
