/** Trạng thái và thao tác gửi của form đăng ký (spec fe-auth §2.2 "Đăng ký", §6 ý 4). */
import { router } from 'expo-router';
import { useRef, useState } from 'react';

import { register } from '@/services/auth';
import type { RegisterRequest } from '@/types/auth';

import { emptyFormErrors, hasFormErrors, type FormErrors } from './form-errors';
import { toRegisterErrors, validateRegister, type RegisterField, type RegisterInput } from './register-errors';
import { signInWithPassword } from './sign-in';

const EMPTY_INPUT: RegisterInput = { email: '', display_name: '', full_name: '', password: '', password_confirm: '' };
const REGISTERED_NOTICE_ROUTE = { pathname: '/login', params: { notice: 'registered' } } as const;

async function isAutoSignedIn(email: string, password: string): Promise<boolean> {
  try {
    await signInWithPassword(email, password);
    return true;
  } catch {
    // Tài khoản đã tạo xong; mọi lỗi tự đăng nhập (vd `email_not_verified` khi bật xác thực email) đều chuyển
    // sang màn đăng nhập với notice thay vì báo lỗi ở đây (spec fe-auth §2.2, §6 ý 4). Không log vì có email.
    return false;
  }
}

/** Trả lỗi để hiện trên form nếu `register` lỗi; thành công thì tự đăng nhập rồi điều hướng. */
async function registerAndSignIn(body: RegisterRequest): Promise<FormErrors<RegisterField> | null> {
  try {
    await register(body);
  } catch (err) {
    return toRegisterErrors(err);
  }
  if (await isAutoSignedIn(body.email, body.password)) router.replace('/');
  else router.replace(REGISTERED_NOTICE_ROUTE);
  return null;
}

export function useRegisterForm() {
  const [values, setValues] = useState<RegisterInput>(EMPTY_INPUT);
  const [errors, setErrors] = useState<FormErrors<RegisterField>>(emptyFormErrors);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // `loading` của nút chỉ có hiệu lực sau lần render kế tiếp; ref chặn ngay lần bấm thứ hai trong cùng khung hình.
  const isSubmittingRef = useRef(false);

  const setValue = (field: RegisterField) => (text: string) => setValues((prev) => ({ ...prev, [field]: text }));

  const submit = async () => {
    if (isSubmittingRef.current) return;
    const { errors: clientErrors, body } = validateRegister(values);
    setErrors(clientErrors);
    if (hasFormErrors(clientErrors)) return;

    isSubmittingRef.current = true;
    setIsSubmitting(true);
    try {
      const serverErrors = await registerAndSignIn(body);
      if (serverErrors) setErrors(serverErrors);
    } finally {
      isSubmittingRef.current = false;
      setIsSubmitting(false);
    }
  };

  return { values, setValue, errors, isSubmitting, submit };
}

export type RegisterForm = ReturnType<typeof useRegisterForm>;
