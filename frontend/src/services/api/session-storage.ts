/** Token và device_id chỉ lưu trong SecureStore (doc 04 §7 ý 1). File core. */
import * as SecureStore from 'expo-secure-store';

const KEYS = { access: 'access_token', refresh: 'refresh_token', device: 'device_id' } as const;

export type Tokens = { access_token: string; refresh_token: string };

export async function getAccessToken(): Promise<string | null> {
  return SecureStore.getItemAsync(KEYS.access);
}

export async function getRefreshToken(): Promise<string | null> {
  return SecureStore.getItemAsync(KEYS.refresh);
}

export async function getDeviceId(): Promise<string | null> {
  return SecureStore.getItemAsync(KEYS.device);
}

/** Ghi CẢ HAI token trước khi dùng (refresh token cũ đã vô hiệu, doc 04 §7 ý 4). */
export async function saveTokens(tokens: Tokens, deviceId?: string | null): Promise<void> {
  await SecureStore.setItemAsync(KEYS.access, tokens.access_token);
  await SecureStore.setItemAsync(KEYS.refresh, tokens.refresh_token);
  if (deviceId) await SecureStore.setItemAsync(KEYS.device, deviceId);
}

/** Xoá token khi đăng xuất hoặc phiên hết hiệu lực; giữ device_id để lần đăng nhập sau dùng lại. */
export async function clearTokens(): Promise<void> {
  await SecureStore.deleteItemAsync(KEYS.access);
  await SecureStore.deleteItemAsync(KEYS.refresh);
}
