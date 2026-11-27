/** Đọc lỗi API theo Claude_api_respone.md §3: `error.response.data.error.code` (chữ thường). File core. */
import { isAxiosError } from 'axios';

export type ApiErrorDetail = { field: string | null; message: string; code: string };
export type ApiErrorBody = { error: { code: string; message: string; details: ApiErrorDetail[]; request_id?: string } };

export const NETWORK_ERROR = 'network_error';

function errorBody(err: unknown): ApiErrorBody['error'] | null {
  if (!isAxiosError(err)) return null;
  const data = err.response?.data as Partial<ApiErrorBody> | undefined;
  return data?.error && typeof data.error.code === 'string' ? data.error : null;
}

/** Mã lỗi ổn định để rẽ nhánh; lỗi mạng (không có response) trả `network_error`. */
export function getErrorCode(err: unknown): string | null {
  if (isAxiosError(err) && !err.response) return NETWORK_ERROR;
  return errorBody(err)?.code ?? null;
}

/** Lỗi theo field của `validation_error`, dạng { field: message } để hiện ngay dưới ô nhập. */
export function getFieldErrors(err: unknown): Record<string, string> {
  const details = errorBody(err)?.details ?? [];
  return Object.fromEntries(details.filter((d) => d.field).map((d) => [d.field as string, d.message]));
}

/** Thông báo để hiển thị (chỉ để hiện, KHÔNG so sánh theo message). */
export function getErrorMessage(err: unknown, fallback = 'Đã có lỗi, vui lòng thử lại'): string {
  if (getErrorCode(err) === NETWORK_ERROR) return 'Không kết nối được máy chủ';
  return errorBody(err)?.message ?? fallback;
}
