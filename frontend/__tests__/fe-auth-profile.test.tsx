import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { AxiosError } from 'axios';
import { router } from 'expo-router';
import * as SecureStore from 'expo-secure-store';

import { ME_QUERY_KEY } from '@/hooks/auth/useMe';
import ProfileScreen from '@/screens/profile/ProfileScreen';
import { unitSystemLabel } from '@/screens/profile/labels';
import { getAccessToken, getDeviceId, getRefreshToken, saveTokens } from '@/services/api/session-storage';
import { getMe, logout } from '@/services/auth';
import { useSession } from '@/store/session';
import type { LogoutResponse, Me } from '@/types/auth';

jest.mock('@/services/auth');
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
  useLocalSearchParams: jest.fn(() => ({})),
  Redirect: () => null,
}));

// Lần render đầu của suite nạp lười module React Native; khi cổng chạy cả suite song song với --coverage,
// test đầu có thể vượt timeout 5s mặc định. jest.config.js là file core nên nâng timeout tại đây.
jest.setTimeout(20_000);

const mockedGetMe = jest.mocked(getMe);
const mockedLogout = jest.mocked(logout);

// Dữ liệu giả theo persona seed (spec fe-auth §5; seeds/01_rbac.sql, 90_test_users.sql), không phải người dùng thật.
const USER_PERMISSIONS = [
  'exercise:read',
  'equipment:read',
  'muscle_group:read',
  'plan_template:read',
  'media:upload',
  'workout:manage_own',
  'body_metric:manage_own',
  'progress_photo:manage_own',
  'report:export_own',
  'ai:use',
];
const EDITOR_PERMISSIONS = [
  'exercise:read',
  'exercise:create',
  'exercise:update',
  'exercise:delete',
  'exercise:publish',
  'equipment:read',
  'equipment:manage',
  'muscle_group:read',
  'muscle_group:manage',
  'plan_template:read',
  'plan_template:manage',
  'media:upload',
];
const DEMO_ME: Me = {
  id: '5eed0000-0000-4000-8000-000000000003',
  email: 'demo@smartworkout.local',
  status: 'active',
  email_verified_at: '2026-01-05T08:00:00Z',
  display_name: 'An',
  full_name: 'Nguyễn Văn An',
  avatar_media_id: null,
  locale: 'vi-VN',
  timezone: 'Asia/Ho_Chi_Minh',
  unit_system: 'metric',
  roles: ['user'],
  permissions: USER_PERMISSIONS,
};
const EDITOR_ME: Me = {
  ...DEMO_ME,
  id: '5eed0000-0000-4000-8000-000000000002',
  email: 'editor@smartworkout.local',
  display_name: 'Editor',
  full_name: 'Biên tập viên',
  roles: ['content_editor'],
  permissions: EDITOR_PERMISSIONS,
};
const OTHER_ME: Me = {
  ...DEMO_ME,
  id: '5eed0000-0000-4000-8000-000000000010',
  email: 'other@smartworkout.local',
  display_name: 'Phương',
  full_name: 'Bùi Phương',
  locale: 'en-US',
  unit_system: 'imperial',
};
const SESSION_USER = { id: DEMO_ME.id, email: DEMO_ME.email, display_name: DEMO_ME.display_name, roles: DEMO_ME.roles };

const ACCOUNT_ROWS = ['Hồ sơ', 'Mục tiêu', 'Đơn vị đo', 'Thiết bị đăng nhập', 'Đổi mật khẩu', 'Đăng xuất'];

function networkError(): AxiosError {
  return new AxiosError('Network Error');
}

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

const queryClients: QueryClient[] = [];

async function renderProfile(): Promise<QueryClient> {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClients.push(client);
  await render(
    <QueryClientProvider client={client}>
      <ProfileScreen />
    </QueryClientProvider>,
  );
  return client;
}

function row(label: string) {
  return screen.getByRole('button', { name: label });
}

beforeEach(() => {
  jest.clearAllMocks();
  useSession.setState({ status: 'signedIn', user: SESSION_USER });
});

// Gỡ màn rồi xoá cache: nếu không, timer `gcTime` (mặc định 5 phút) của React Query giữ tiến trình jest không thoát.
afterEach(async () => {
  await cleanup();
  for (const client of queryClients.splice(0)) client.clear();
});

describe('ProfileScreen: trạng thái và dữ liệu', () => {
  it('FEAUTH-09 (a) đang tải: hiện "Đang tải..." và vẫn có dòng Đăng xuất', async () => {
    mockedGetMe.mockReturnValue(new Promise<Me>(() => undefined));
    await renderProfile();

    expect(screen.getByLabelText('Đang tải...')).toBeTruthy();
    expect(row('Đăng xuất')).toBeTruthy();
    // Dòng phụ thuộc dữ liệu chỉ hiện khi `me` đã tải.
    expect(screen.queryByLabelText('Hồ sơ')).toBeNull();
    expect(screen.queryByLabelText('Mục tiêu')).toBeNull();
  });

  it('FEAUTH-09 (b) lỗi mạng: báo lỗi, giữ Đăng xuất; bấm "Thử lại" thì hiện tài khoản và đủ 6 dòng', async () => {
    mockedGetMe.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(DEMO_ME);
    await renderProfile();

    expect(await screen.findByText('Không kết nối được máy chủ')).toBeTruthy();
    expect(row('Thử lại')).toBeTruthy();
    expect(row('Đăng xuất')).toBeTruthy();
    expect(screen.queryByLabelText('Hồ sơ')).toBeNull();

    await fireEvent.press(row('Thử lại'));

    expect(await screen.findByText('An')).toBeTruthy();
    expect(screen.getByText('demo@smartworkout.local')).toBeTruthy();
    for (const label of ACCOUNT_ROWS) expect(row(label)).toBeTruthy();
    expect(screen.getByText('Mét (kg, cm)')).toBeTruthy();
    expect(screen.queryByText('Không kết nối được máy chủ')).toBeNull();
    expect(mockedGetMe).toHaveBeenCalledTimes(2);
  });

  it('FEAUTH-09 (c) persona other: hiện "Phương" và dòng phụ "Anh (lb, in)"', async () => {
    mockedGetMe.mockResolvedValue(OTHER_ME);
    await renderProfile();

    expect(await screen.findByText('Phương')).toBeTruthy();
    expect(screen.getByText('other@smartworkout.local')).toBeTruthy();
    expect(screen.getByText('Anh (lb, in)')).toBeTruthy();
    expect(screen.queryByText('Mét (kg, cm)')).toBeNull();
  });

  it('FEAUTH-09 thiếu display_name thì thẻ tài khoản hiện email làm tên', async () => {
    mockedGetMe.mockResolvedValue({ ...DEMO_ME, display_name: null });
    await renderProfile();

    expect(await screen.findAllByText('demo@smartworkout.local')).toHaveLength(2);
    expect(screen.queryByText('An')).toBeNull();
  });

  it('FEAUTH-09 nhãn hệ đơn vị: metric và null là "Mét (kg, cm)", imperial là "Anh (lb, in)"', () => {
    expect(unitSystemLabel('metric')).toBe('Mét (kg, cm)');
    expect(unitSystemLabel(null)).toBe('Mét (kg, cm)');
    expect(unitSystemLabel('imperial')).toBe('Anh (lb, in)');
  });
});

describe('ProfileScreen: permission và điều hướng', () => {
  it('FEAUTH-10 bấm từng dòng thì chuyển tới đúng màn trong /account', async () => {
    mockedGetMe.mockResolvedValue(DEMO_ME);
    await renderProfile();
    await screen.findByText('An');

    for (const label of ['Hồ sơ', 'Mục tiêu', 'Đơn vị đo', 'Thiết bị đăng nhập', 'Đổi mật khẩu']) {
      await fireEvent.press(row(label));
    }

    expect(jest.mocked(router.push).mock.calls).toEqual([
      ['/account/edit-profile'],
      ['/account/goals'],
      ['/account/units'],
      ['/account/devices'],
      ['/account/change-password'],
    ]);
  });

  it('FEAUTH-10 editor không có body_metric:manage_own thì ẩn dòng "Mục tiêu", 5 dòng còn lại vẫn hiện', async () => {
    mockedGetMe.mockResolvedValue(EDITOR_ME);
    await renderProfile();
    await screen.findByText('Editor');

    expect(screen.queryByText('Mục tiêu')).toBeNull();
    expect(screen.queryByLabelText('Mục tiêu')).toBeNull();
    for (const label of ACCOUNT_ROWS.filter((item) => item !== 'Mục tiêu')) expect(row(label)).toBeTruthy();
  });
});

describe('ProfileScreen: đăng xuất', () => {
  async function renderSignedInProfile(): Promise<QueryClient> {
    mockedGetMe.mockResolvedValue(DEMO_ME);
    const client = await renderProfile();
    await screen.findByText('An');
    expect(client.getQueryData(ME_QUERY_KEY)).toEqual(DEMO_ME);
    return client;
  }

  async function expectSignedOut(client: QueryClient) {
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith('/login'));
    expect(router.replace).toHaveBeenCalledTimes(1);
    expect(await getAccessToken()).toBeNull();
    expect(await getRefreshToken()).toBeNull();
    expect(await getDeviceId()).toBe('dev-9');
    expect(useSession.getState().status).toBe('signedOut');
    expect(useSession.getState().user).toBeNull();
    expect(client.getQueryData(ME_QUERY_KEY)).toBeUndefined();
    // `useMe` bị tắt khi đã đăng xuất: không gọi lại `/auth/me` sau khi xoá cache.
    expect(mockedGetMe).toHaveBeenCalledTimes(1);
  }

  it.each([
    { name: '(a) logout thành công', setup: () => mockedLogout.mockResolvedValue({ is_revoked: true }) },
    { name: '(b) logout lỗi mạng', setup: () => mockedLogout.mockRejectedValue(networkError()) },
  ])('FEAUTH-11 $name: gọi logout với refresh token rồi luôn xoá phiên', async ({ setup }) => {
    await saveTokens({ access_token: 'a', refresh_token: 'r-1' }, 'dev-9');
    setup();
    const client = await renderSignedInProfile();

    await fireEvent.press(row('Đăng xuất'));

    await expectSignedOut(client);
    expect(mockedLogout).toHaveBeenCalledTimes(1);
    expect(mockedLogout).toHaveBeenCalledWith('r-1');
  });

  it('FEAUTH-11 (c) không có refresh token: không gọi logout, vẫn xoá phiên', async () => {
    await SecureStore.setItemAsync('device_id', 'dev-9');
    const client = await renderSignedInProfile();

    await fireEvent.press(row('Đăng xuất'));

    await expectSignedOut(client);
    expect(mockedLogout).not.toHaveBeenCalled();
  });

  it('FEAUTH-11 bấm "Đăng xuất" hai lần khi đang chờ thì chỉ gọi logout một lần', async () => {
    await saveTokens({ access_token: 'a', refresh_token: 'r-1' }, 'dev-9');
    const pending = deferred<LogoutResponse>();
    mockedLogout.mockReturnValue(pending.promise);
    const client = await renderSignedInProfile();

    // Lần bấm đầu treo tới khi `logout` resolve nên không await.
    const firstPress = fireEvent.press(row('Đăng xuất'));
    await waitFor(() => expect(mockedLogout).toHaveBeenCalledTimes(1));
    await fireEvent.press(row('Đăng xuất'));
    await act(async () => {
      pending.resolve({ is_revoked: true });
      await firstPress;
    });

    await expectSignedOut(client);
    expect(mockedLogout).toHaveBeenCalledTimes(1);
  });
});
