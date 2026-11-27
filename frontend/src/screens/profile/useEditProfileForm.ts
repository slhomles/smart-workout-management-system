/** Trạng thái và thao tác lưu của form Hồ sơ (spec fe-auth §2.2 "Sửa hồ sơ"). */
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';

import { ME_QUERY_KEY } from '@/hooks/auth/useMe';
import { useSingleFlight } from '@/hooks/auth/useSingleFlight';
import { emptyFormErrors, hasFormErrors, type FormErrors } from '@/screens/auth/form-errors';
import { updateMe } from '@/services/auth';
import { useSession } from '@/store/session';
import type { Me, UpdateMeRequest } from '@/types/auth';

import {
  hasChanges,
  initialProfileInput,
  toProfileErrors,
  validateProfile,
  type ProfileField,
  type ProfileInput,
} from './edit-profile-form';

/** Ghi response vào cache `['auth','me']` và thông tin hiển thị của session (spec fe-auth §2.2). */
function storeUpdatedMe(queryClient: QueryClient, updated: Me): void {
  queryClient.setQueryData(ME_QUERY_KEY, updated);
  const { id, email, display_name, roles } = updated;
  useSession.getState().setUser({ id, email, display_name, roles });
}

/** Trả lỗi để hiện trên form nếu `updateMe` lỗi; lỗi thì KHÔNG đụng tới cache. */
async function saveProfile(
  queryClient: QueryClient,
  changes: UpdateMeRequest,
): Promise<FormErrors<ProfileField> | null> {
  let updated: Me;
  try {
    updated = await updateMe(changes);
  } catch (err) {
    // Lỗi đã được quy về thông điệp trên form; không log vì body có họ tên.
    return toProfileErrors(err);
  }
  storeUpdatedMe(queryClient, updated);
  return null;
}

/** `me` chỉ dùng để khởi tạo ô nhập và tính field đã đổi; dữ liệu server tải lại không ghi đè chữ đang nhập. */
export function useEditProfileForm(me: Me) {
  const queryClient = useQueryClient();
  const [values, setValues] = useState<ProfileInput>(() => initialProfileInput(me));
  const [errors, setErrors] = useState<FormErrors<ProfileField>>(emptyFormErrors);

  const setValue = (field: ProfileField) => (text: string) =>
    setValues((prev) => ({ ...prev, [field]: text }));

  const { run, isPending } = useSingleFlight(async () => {
    const { errors: clientErrors, changes } = validateProfile(values, me);
    setErrors(clientErrors);
    if (hasFormErrors(clientErrors)) return;
    // Không đổi gì thì không gọi API, chỉ quay lại (spec fe-auth §2.2).
    const serverErrors = hasChanges(changes) ? await saveProfile(queryClient, changes) : null;
    if (serverErrors) setErrors(serverErrors);
    else router.back();
  });

  return { values, setValue, errors, isSubmitting: isPending, submit: run };
}
