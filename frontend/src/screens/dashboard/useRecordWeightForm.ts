/** Trạng thái và thao tác lưu của form Ghi cân nặng (spec fe-dashboard §2.2 "Ghi cân nặng"). */
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { router } from 'expo-router';
import { useState } from 'react';

import { useSingleFlight } from '@/hooks/auth/useSingleFlight';
import { DASHBOARD_QUERY_KEY } from '@/hooks/dashboard/useDashboard';
import { emptyFormErrors, type FormErrors } from '@/screens/auth/form-errors';
import { createMeasurement } from '@/services/dashboard';
import type { UnitSystem } from '@/types/auth';
import type { CreateMeasurementRequest } from '@/types/dashboard';

import {
  EMPTY_RECORD_WEIGHT_INPUT,
  toRecordWeightErrors,
  validateRecordWeight,
  type RecordWeightField,
  type RecordWeightInput,
} from './record-weight-form';

/** Trả lỗi để hiện trên form nếu `createMeasurement` lỗi; thành công thì đánh dấu tab Báo cáo cần tải lại. */
async function saveMeasurement(
  queryClient: QueryClient,
  body: CreateMeasurementRequest,
): Promise<FormErrors<RecordWeightField> | null> {
  try {
    await createMeasurement(body);
  } catch (err) {
    return toRecordWeightErrors(err);
  }
  // `['dashboard']` là tiền tố của key biểu đồ nên điểm cân nặng mới cũng được vẽ lại (spec §6 ý 9).
  // Không chờ tải lại: tab Báo cáo bên dưới tự cập nhật sau khi quay lại.
  void queryClient.invalidateQueries({ queryKey: DASHBOARD_QUERY_KEY });
  return null;
}

/** `unitSystem` quyết định cân nặng nhập theo kg hay lb (spec §6 ý 8). */
export function useRecordWeightForm(unitSystem: UnitSystem) {
  const queryClient = useQueryClient();
  const [values, setValues] = useState<RecordWeightInput>(EMPTY_RECORD_WEIGHT_INPUT);
  const [errors, setErrors] = useState<FormErrors<RecordWeightField>>(emptyFormErrors);

  const setText = (field: keyof RecordWeightInput) => (text: string) => setValues((prev) => ({ ...prev, [field]: text }));

  const { run, isPending } = useSingleFlight(async () => {
    const { errors: clientErrors, body } = validateRecordWeight(values, unitSystem);
    setErrors(clientErrors);
    if (!body) return;
    const serverErrors = await saveMeasurement(queryClient, body);
    if (serverErrors) setErrors(serverErrors);
    else router.back();
  });

  return { values, setText, errors, isSubmitting: isPending, submit: run };
}
