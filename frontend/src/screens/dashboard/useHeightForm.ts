/** Trạng thái và thao tác lưu của form Chiều cao (spec fe-dashboard §2.2 "Chiều cao"). */
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';

import { useSingleFlight } from '@/hooks/auth/useSingleFlight';
import { BODY_PROFILE_QUERY_KEY } from '@/hooks/dashboard/useBodyProfile';
import { DASHBOARD_QUERY_KEY } from '@/hooks/dashboard/useDashboard';
import { emptyFormErrors, type FormErrors } from '@/screens/auth/form-errors';
import { replaceBodyProfile } from '@/services/dashboard';
import type { BodyProfile, ReplaceBodyProfileRequest } from '@/types/dashboard';

import { initialHeightText, toHeightErrors, validateHeight, type HeightField } from './height-form';

/** Trả lỗi để hiện trên form nếu `replaceBodyProfile` lỗi; thành công thì đánh dấu hồ sơ và tab Báo cáo cần tải lại. */
async function saveHeight(queryClient: QueryClient, body: ReplaceBodyProfileRequest): Promise<FormErrors<HeightField> | null> {
  try {
    await replaceBodyProfile(body);
  } catch (err) {
    return toHeightErrors(err);
  }
  // Chiều cao đổi thì BMI, BMR, TDEE của `/dashboard` cũng đổi (spec §2.2 "Chiều cao"). Không chờ tải lại.
  void queryClient.invalidateQueries({ queryKey: BODY_PROFILE_QUERY_KEY });
  void queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
  return null;
}

/** `profile` chỉ dùng để điền sẵn một lần và giữ nguyên các field khác khi gửi PUT (spec §6 ý 10). */
export function useHeightForm(profile: BodyProfile) {
  const queryClient = useQueryClient();
  const [height, setHeight] = useState(() => initialHeightText(profile));
  const [errors, setErrors] = useState<FormErrors<HeightField>>(emptyFormErrors);

  const { run, isPending } = useSingleFlight(async () => {
    const { errors: clientErrors, body } = validateHeight(height, profile);
    setErrors(clientErrors);
    if (!body) return;
    const serverErrors = await saveHeight(queryClient, body);
    if (serverErrors) setErrors(serverErrors);
    else router.back();
  });

  return { height, setHeight, errors, isSubmitting: isPending, submit: run };
}
