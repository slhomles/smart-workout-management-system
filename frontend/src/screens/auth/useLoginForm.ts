/** Trạng thái và thao tác gửi của form đăng nhập (spec fe-auth §2.2 "Đăng nhập"). */
import { router } from 'expo-router';
import { useRef, useState } from 'react';

import { emptyFormErrors, hasFormErrors, type FormErrors } from './form-errors';
import { toLoginErrors, validateLogin, type LoginField } from './login-errors';
import { signInWithPassword } from './sign-in';

export function useLoginForm() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<FormErrors<LoginField>>(emptyFormErrors);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // `loading` của nút chỉ có hiệu lực sau lần render kế tiếp; ref chặn ngay lần bấm thứ hai trong cùng khung hình.
  const isSubmittingRef = useRef(false);

  const submit = async () => {
    if (isSubmittingRef.current) return;
    const trimmedEmail = email.trim();
    const clientErrors = validateLogin(trimmedEmail, password);
    setErrors(clientErrors);
    if (hasFormErrors(clientErrors)) return;

    isSubmittingRef.current = true;
    setIsSubmitting(true);
    try {
      await signInWithPassword(trimmedEmail, password);
      router.replace('/');
    } catch (err) {
      // Lỗi đã được quy về thông điệp hiện trên form; không log vì có thể chứa email.
      setErrors(toLoginErrors(err));
    } finally {
      isSubmittingRef.current = false;
      setIsSubmitting(false);
    }
  };

  return { email, setEmail, password, setPassword, errors, isSubmitting, submit };
}
