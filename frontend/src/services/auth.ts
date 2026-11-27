/**
 * Service `/auth` (doc 04 §4; spec fe-auth §2.3). Mọi hàm trả thẳng `res.data`, không có
 * envelope (`Claude_api_respone.md` §1). Header và refresh token do `client.ts` lo.
 */
import type {
  ChangePasswordRequest,
  LoginRequest,
  LoginResponse,
  LogoutAllResponse,
  LogoutResponse,
  Me,
  RegisterRequest,
  RegisterResponse,
  UpdateMeRequest,
} from '@/types/auth';

import { api } from './api/client';

export async function login(body: LoginRequest): Promise<LoginResponse> {
  const res = await api.post<LoginResponse>('/auth/login', body);
  return res.data;
}

export async function register(body: RegisterRequest): Promise<RegisterResponse> {
  const res = await api.post<RegisterResponse>('/auth/register', body);
  return res.data;
}

export async function logout(refreshToken: string): Promise<LogoutResponse> {
  const res = await api.post<LogoutResponse>('/auth/logout', { refresh_token: refreshToken });
  return res.data;
}

/** Thu hồi mọi refresh token của user (doc 04 §4.5); endpoint không nhận body. */
export async function logoutAll(): Promise<LogoutAllResponse> {
  const res = await api.post<LogoutAllResponse>('/auth/logout-all');
  return res.data;
}

export async function getMe(): Promise<Me> {
  const res = await api.get<Me>('/auth/me');
  return res.data;
}

export async function updateMe(body: UpdateMeRequest): Promise<Me> {
  const res = await api.patch<Me>('/auth/me', body);
  return res.data;
}

/** Thành công thì server đã thu hồi mọi refresh token: client phải đăng nhập lại (doc 04 §4.7). */
export async function changePassword(body: ChangePasswordRequest): Promise<Me> {
  const res = await api.patch<Me>('/auth/change-password', body);
  return res.data;
}
