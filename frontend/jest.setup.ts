// Thiết lập chung cho jest (frontend-standards §6). File core.
// SecureStore giả bằng Map trong bộ nhớ: test không chạm Keychain/Keystore thật.
const mockSecureStore = new Map<string, string>();

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn(async (key: string) => mockSecureStore.get(key) ?? null),
  setItemAsync: jest.fn(async (key: string, value: string) => {
    mockSecureStore.set(key, value);
  }),
  deleteItemAsync: jest.fn(async (key: string) => {
    mockSecureStore.delete(key);
  }),
}));

beforeEach(() => {
  mockSecureStore.clear();
});
