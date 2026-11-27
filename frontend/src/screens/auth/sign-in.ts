/**
 * Đăng nhập bằng email/mật khẩu rồi lưu phiên (doc 04 §4.3, §7 ý 1; spec fe-auth §2.2).
 * Dùng chung cho màn đăng nhập và tự đăng nhập sau khi đăng ký. Không điều hướng: màn hình tự quyết.
 */
import { Platform } from 'react-native';

import { getDeviceId } from '@/services/api/session-storage';
import { login } from '@/services/auth';
import { useSession } from '@/store/session';
import type { LoginRequest, LoginResponse } from '@/types/auth';
import { toDevicePlatform } from '@/utils/device';

/** `email` phải được trim trước khi gọi. Không gửi `push_token` (spec fe-auth §2.2). */
export async function signInWithPassword(email: string, password: string): Promise<LoginResponse> {
  const body: LoginRequest = {
    email,
    password,
    device: {
      // Gửi lại device_id đã lưu để server dùng lại thiết bị cũ; `null` thì server tạo thiết bị mới.
      device_id: await getDeviceId(),
      platform: toDevicePlatform(Platform.OS),
      os_version: String(Platform.Version),
    },
  };
  const res = await login(body);
  const tokens = { access_token: res.access_token, refresh_token: res.refresh_token };
  await useSession.getState().signIn(tokens, res.user, res.device_id);
  return res;
}
