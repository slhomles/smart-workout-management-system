/**
 * Axios client duy nhất của app (frontend-standards §3, doc 04 §7). File core.
 * - Gắn `Authorization: Bearer` bằng interceptor; module KHÔNG tự gắn header.
 * - `token_expired`: refresh single-flight, ghi cả hai token rồi retry đúng một lần.
 * - `token_invalid`, `token_reused`, `account_disabled` hoặc refresh thất bại: xoá token, báo phiên hết hạn.
 */
import axios, { AxiosError, create, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios';

import { getErrorCode } from './errors';
import { clearTokens, getAccessToken, getDeviceId, getRefreshToken, saveTokens } from './session-storage';

export const API_BASE_URL = `${process.env.EXPO_PUBLIC_API_URL ?? 'http://localhost:8000'}/api/v1`;
const SESSION_END_CODES = ['token_invalid', 'token_reused', 'account_disabled'];

type RetriableConfig = InternalAxiosRequestConfig & { _retried?: boolean };
type RefreshResponse = { access_token: string; refresh_token: string; device_id?: string };

let onSessionExpired: () => void = () => undefined;
let refreshing: Promise<string> | null = null;

/** Root layout đăng ký: xoá phiên trong store và điều hướng về đăng nhập. */
export function setSessionExpiredHandler(handler: () => void): void {
  onSessionExpired = handler;
}

async function refreshAccessToken(): Promise<string> {
  const refreshToken = await getRefreshToken();
  if (!refreshToken) throw new Error('missing_refresh_token');
  // axios trần (không qua interceptor) để không lặp vô hạn.
  const res = await axios.post<RefreshResponse>(`${API_BASE_URL}/auth/refresh`, { refresh_token: refreshToken });
  await saveTokens(res.data, res.data.device_id ?? (await getDeviceId()));
  return res.data.access_token;
}

async function endSession(): Promise<void> {
  await clearTokens();
  onSessionExpired();
}

async function retryWithFreshToken(api: AxiosInstance, original: RetriableConfig): Promise<unknown> {
  original._retried = true;
  refreshing ??= refreshAccessToken().finally(() => {
    refreshing = null;
  });
  const token = await refreshing;
  original.headers.Authorization = `Bearer ${token}`;
  return api(original);
}

export function createApiClient(baseURL = API_BASE_URL): AxiosInstance {
  const api = create({ baseURL, timeout: 20000 });
  api.interceptors.request.use(async (config) => {
    const token = await getAccessToken();
    if (token) config.headers.Authorization = `Bearer ${token}`;
    return config;
  });
  api.interceptors.response.use(
    (res) => res,
    async (error: AxiosError) => {
      const code = getErrorCode(error);
      const original = error.config as RetriableConfig | undefined;
      if (code === 'token_expired' && original && !original._retried) {
        try {
          return await retryWithFreshToken(api, original);
        } catch {
          await endSession();
        }
      } else if (code && SESSION_END_CODES.includes(code)) {
        await endSession();
      }
      return Promise.reject(error);
    },
  );
  return api;
}

export const api = createApiClient();
