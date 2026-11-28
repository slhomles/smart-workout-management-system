import * as SecureStore from 'expo-secure-store';

import { tokenStore } from '@/services/api/session-storage';

describe('tokenStore theo nền tảng', () => {
  const memory = new Map<string, string>();
  const fakeLocalStorage = {
    getItem: (k: string) => memory.get(k) ?? null,
    setItem: (k: string, v: string) => void memory.set(k, v),
    removeItem: (k: string) => void memory.delete(k),
  };

  beforeEach(() => {
    memory.clear();
    (globalThis as { localStorage?: unknown }).localStorage = fakeLocalStorage;
  });

  afterAll(() => {
    delete (globalThis as { localStorage?: unknown }).localStorage;
  });

  it('web dùng localStorage, không gọi SecureStore', async () => {
    const store = tokenStore('web');
    await store.set('access_token', 'web-token');
    expect(await store.get('access_token')).toBe('web-token');
    await store.remove('access_token');
    expect(await store.get('access_token')).toBeNull();
    expect(SecureStore.setItemAsync).not.toHaveBeenCalledWith('access_token', 'web-token');
  });

  it('điện thoại dùng SecureStore, không ghi localStorage', async () => {
    const store = tokenStore('android');
    await store.set('access_token', 'native-token');
    expect(await store.get('access_token')).toBe('native-token');
    expect(memory.size).toBe(0);
  });
});
