/**
 * Trạng thái phiên đăng nhập (frontend-standards §1). Token thật nằm trong SecureStore,
 * store chỉ giữ cờ đã đăng nhập và thông tin user để hiển thị.
 */
import { create } from 'zustand';

import { clearTokens, getAccessToken, saveTokens, type Tokens } from '@/services/api/session-storage';

export type SessionUser = { id: string; email: string; display_name: string | null; roles: string[] };
export type SessionStatus = 'loading' | 'signedIn' | 'signedOut';

type SessionState = {
  status: SessionStatus;
  user: SessionUser | null;
  hydrate: () => Promise<void>;
  signIn: (tokens: Tokens, user: SessionUser | null, deviceId?: string | null) => Promise<void>;
  setUser: (user: SessionUser | null) => void;
  signOut: () => Promise<void>;
  markExpired: () => void;
};

export const useSession = create<SessionState>((set) => ({
  status: 'loading',
  user: null,
  hydrate: async () => {
    const token = await getAccessToken();
    set({ status: token ? 'signedIn' : 'signedOut' });
  },
  signIn: async (tokens, user, deviceId) => {
    await saveTokens(tokens, deviceId);
    set({ status: 'signedIn', user });
  },
  setUser: (user) => set({ user }),
  signOut: async () => {
    await clearTokens();
    set({ status: 'signedOut', user: null });
  },
  markExpired: () => set({ status: 'signedOut', user: null }),
}));
