/**
 * Token và device_id: trên điện thoại CHỈ lưu trong SecureStore (doc 04 §7 ý 1). File core.
 * Ngoại lệ (doc 04 §7, frontend-standards §3): bản web chạy để phát triển/demo không có SecureStore
 * (expo-secure-store không hỗ trợ trình duyệt), nên dùng `localStorage` của trình duyệt.
 */
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

const KEYS = { access: 'access_token', refresh: 'refresh_token', device: 'device_id' } as const;

export type Tokens = { access_token: string; refresh_token: string };

type KeyValueStore = {
  get: (key: string) => Promise<string | null>;
  set: (key: string, value: string) => Promise<void>;
  remove: (key: string) => Promise<void>;
};

const secureStore: KeyValueStore = {
  get: (key) => SecureStore.getItemAsync(key),
  set: (key, value) => SecureStore.setItemAsync(key, value),
  remove: (key) => SecureStore.deleteItemAsync(key),
};

const browserStore: KeyValueStore = {
  get: async (key) => globalThis.localStorage?.getItem(key) ?? null,
  set: async (key, value) => globalThis.localStorage?.setItem(key, value),
  remove: async (key) => globalThis.localStorage?.removeItem(key),
};

/** Kho lưu theo nền tảng; tách thành hàm để test chọn được cả hai nhánh. */
export function tokenStore(platform: string = Platform.OS): KeyValueStore {
  return platform === 'web' ? browserStore : secureStore;
}

export async function getAccessToken(): Promise<string | null> {
  return tokenStore().get(KEYS.access);
}

export async function getRefreshToken(): Promise<string | null> {
  return tokenStore().get(KEYS.refresh);
}

export async function getDeviceId(): Promise<string | null> {
  return tokenStore().get(KEYS.device);
}

/** Ghi CẢ HAI token trước khi dùng (refresh token cũ đã vô hiệu, doc 04 §7 ý 4). */
export async function saveTokens(tokens: Tokens, deviceId?: string | null): Promise<void> {
  const store = tokenStore();
  await store.set(KEYS.access, tokens.access_token);
  await store.set(KEYS.refresh, tokens.refresh_token);
  if (deviceId) await store.set(KEYS.device, deviceId);
}

/** Xoá token khi đăng xuất hoặc phiên hết hiệu lực; giữ device_id để lần đăng nhập sau dùng lại. */
export async function clearTokens(): Promise<void> {
  const store = tokenStore();
  await store.remove(KEYS.access);
  await store.remove(KEYS.refresh);
}
