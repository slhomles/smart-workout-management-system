import { getAccessToken, getDeviceId } from '@/services/api/session-storage';
import { useSession } from '@/store/session';

const user = { id: 'u-1', email: 'demo@smartworkout.local', display_name: 'Demo', roles: ['user'] };

describe('useSession', () => {
  beforeEach(() => useSession.setState({ status: 'loading', user: null }));

  it('hydrate: không có token thì signedOut', async () => {
    await useSession.getState().hydrate();
    expect(useSession.getState().status).toBe('signedOut');
  });

  it('signIn lưu token, device_id và user; hydrate sau đó là signedIn', async () => {
    await useSession.getState().signIn({ access_token: 'a', refresh_token: 'r' }, user, 'dev-9');
    expect(useSession.getState()).toMatchObject({ status: 'signedIn', user });
    expect(await getAccessToken()).toBe('a');
    expect(await getDeviceId()).toBe('dev-9');

    useSession.setState({ status: 'loading' });
    await useSession.getState().hydrate();
    expect(useSession.getState().status).toBe('signedIn');
  });

  it('signOut xoá token nhưng giữ device_id', async () => {
    await useSession.getState().signIn({ access_token: 'a', refresh_token: 'r' }, user, 'dev-9');
    await useSession.getState().signOut();
    expect(useSession.getState()).toMatchObject({ status: 'signedOut', user: null });
    expect(await getAccessToken()).toBeNull();
    expect(await getDeviceId()).toBe('dev-9');
  });
});
