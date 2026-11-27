/**
 * Kiểu dữ liệu `/auth` (doc 04 §4), khớp `backend/app/schemas/auth.py`.
 * Giữ snake_case như JSON; UUID là `string` (frontend-standards §3).
 */

export type DevicePlatform = 'ios' | 'android' | 'web';
export type UnitSystem = 'metric' | 'imperial';
export type UserStatus = 'pending_verification' | 'active' | 'locked' | 'disabled';

export type DeviceInfo = {
  device_id: string | null;
  platform: DevicePlatform;
  device_name?: string;
  os_version?: string;
  app_version?: string;
};

export type LoginRequest = {
  email: string;
  password: string;
  device: DeviceInfo;
};

export type AuthUser = {
  id: string;
  email: string;
  display_name: string | null;
  roles: string[];
};

export type LoginResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  device_id: string;
  user: AuthUser;
};

export type RegisterRequest = {
  email: string;
  password: string;
  display_name: string;
  full_name: string | null;
};

/** Register KHÔNG trả token (doc 04 §4.2). */
export type RegisterResponse = {
  id: string;
  email: string;
  display_name: string;
  full_name: string | null;
  roles: string[];
  status: UserStatus;
};

export type Me = {
  id: string;
  email: string;
  status: UserStatus;
  email_verified_at: string | null;
  display_name: string | null;
  full_name: string | null;
  avatar_media_id: string | null;
  locale: string | null;
  timezone: string | null;
  /** `null` coi như `metric` (spec fe-auth §6 ý 10). */
  unit_system: UnitSystem | null;
  roles: string[];
  permissions: string[];
};

/** Chỉ field có mặt mới được cập nhật; `full_name: null` để xoá họ tên. */
export type UpdateMeRequest = {
  display_name?: string;
  full_name?: string | null;
  unit_system?: UnitSystem;
};

export type ChangePasswordRequest = {
  current_password: string;
  new_password: string;
};

export type LogoutResponse = { is_revoked: boolean };
export type LogoutAllResponse = { revoked_count: number };
