import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { AxiosError, AxiosHeaders } from 'axios';
import { router } from 'expo-router';
import { Alert, type AlertButton } from 'react-native';

import { ME_QUERY_KEY } from '@/hooks/auth/useMe';
import DevicesScreen from '@/screens/profile/DevicesScreen';
import type { ApiErrorDetail } from '@/services/api/errors';
import { getAccessToken, getDeviceId, getRefreshToken, saveTokens } from '@/services/api/session-storage';
import { logout, logoutAll } from '@/services/auth';
import { useSession } from '@/store/session';
import type { Me } from '@/types/auth';

jest.mock('@/services/auth');
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
  useLocalSearchParams: jest.fn(() => ({})),
  Redirect: () => null,
}));

const mockedLogoutAll = jest.mocked(logoutAll);
const mockedLogout = jest.mocked(logout);

const LOGOUT_ALL_BUTTON = 'Đăng xuất khỏi mọi thiết bị';

// Dữ liệu giả theo persona seed "demo" (spec fe-auth §5), không phải người dùng thật.
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
  permissions: ['workout:manage_own', 'body_metric:manage_own', 'progress_photo:manage_own'],
};
const SESSION_USER = { id: DEMO_ME.id, email: DEMO_ME.email, display_name: DEMO_ME.display_name, roles: DEMO_ME.roles };

/** Lỗi API giả theo Claude_api_respone.md §3; `message` cố ý khác thông điệp màn hiện để chứng minh rẽ nhánh theo code. */
function apiError(status: number, code: string, details: ApiErrorDetail[] = []): AxiosError {
  const config = { headers: new AxiosHeaders() };
  const data = { error: { code, message: `Thông điệp server (${code})`, details, request_id: 'req-test' } };
  return new AxiosError('fail', 'ERR_BAD_RESPONSE', config, null, { status, statusText: '', headers: {}, config, data });
}

let alertSpy: jest.SpiedFunction<typeof Alert.alert>;
const queryClients: QueryClient[] = [];

async function renderDevices(): Promise<QueryClient> {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClients.push(client);
  client.setQueryData(ME_QUERY_KEY, DEMO_ME);
  await render(
    <QueryClientProvider client={client}>
      <DevicesScreen />
    </QueryClientProvider>,
  );
  return client;
}

/** Bấm nút chính, kiểm tiêu đề hộp thoại xác nhận rồi trả mảng nút của nó. */
async function openConfirm(): Promise<AlertButton[]> {
  await fireEvent.press(screen.getByRole('button', { name: LOGOUT_ALL_BUTTON }));
  expect(alertSpy).toHaveBeenCalledTimes(1);
  const call = alertSpy.mock.calls[0];
  if (!call) throw new Error('Alert.alert chưa được gọi');
  const [title, , buttons = []] = call;
  expect(title).toBe('Đăng xuất khỏi mọi thiết bị?');
  return buttons;
}

function buttonOf(buttons: AlertButton[], text: string): AlertButton {
  const button = buttons.find((item) => item.text === text);
  if (!button) throw new Error(`Hộp thoại không có nút "${text}"`);
  return button;
}

async function confirmLogoutAll() {
  const buttons = await openConfirm();
  await act(async () => {
    buttonOf(buttons, 'Đăng xuất tất cả').onPress?.();
  });
}

async function expectSessionKept() {
  expect(useSession.getState().status).toBe('signedIn');
  expect(await getAccessToken()).toBe('a');
  expect(await getRefreshToken()).toBe('r-1');
  expect(router.replace).not.toHaveBeenCalled();
}

beforeEach(async () => {
  jest.clearAllMocks();
  useSession.setState({ status: 'signedIn', user: SESSION_USER });
  await saveTokens({ access_token: 'a', refresh_token: 'r-1' }, 'dev-9');
  alertSpy = jest.spyOn(Alert, 'alert').mockImplementation(() => undefined);
});

// Gỡ màn rồi xoá cache: nếu không, timer `gcTime` (mặc định 5 phút) của React Query giữ tiến trình jest không thoát.
afterEach(async () => {
  alertSpy.mockRestore();
  await cleanup();
  for (const client of queryClients.splice(0)) client.clear();
});

describe('DevicesScreen: đăng xuất khỏi mọi thiết bị', () => {
  it('FEAUTH-17 hỏi xác nhận với nút "Huỷ" (cancel) và "Đăng xuất tất cả" (destructive)', async () => {
    await renderDevices();
    const buttons = await openConfirm();

    expect(buttons.map((item) => item.text)).toEqual(['Huỷ', 'Đăng xuất tất cả']);
    expect(buttonOf(buttons, 'Huỷ').style).toBe('cancel');
    expect(buttonOf(buttons, 'Đăng xuất tất cả').style).toBe('destructive');
    expect(mockedLogoutAll).not.toHaveBeenCalled();
  });

  it('FEAUTH-17 (a) bấm "Huỷ": không gọi logoutAll, giữ phiên', async () => {
    const client = await renderDevices();
    const buttons = await openConfirm();

    await act(async () => {
      buttonOf(buttons, 'Huỷ').onPress?.();
    });

    expect(mockedLogoutAll).not.toHaveBeenCalled();
    expect(mockedLogout).not.toHaveBeenCalled();
    await expectSessionKept();
    expect(client.getQueryData(ME_QUERY_KEY)).toEqual(DEMO_ME);
  });

  it('FEAUTH-17 (b) xác nhận: gọi logoutAll, không gọi logout, xoá phiên và cache rồi về /login', async () => {
    mockedLogoutAll.mockResolvedValue({ revoked_count: 2 });
    const client = await renderDevices();

    await confirmLogoutAll();

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith('/login'));
    expect(router.replace).toHaveBeenCalledTimes(1);
    expect(mockedLogoutAll).toHaveBeenCalledTimes(1);
    expect(mockedLogout).not.toHaveBeenCalled();
    expect(await getAccessToken()).toBeNull();
    expect(await getRefreshToken()).toBeNull();
    expect(await getDeviceId()).toBe('dev-9');
    expect(useSession.getState().status).toBe('signedOut');
    expect(useSession.getState().user).toBeNull();
    expect(client.getQueryData(ME_QUERY_KEY)).toBeUndefined();
  });

  it('FEAUTH-17 (c) logoutAll lỗi mạng: hiện "Không kết nối được máy chủ" và giữ phiên', async () => {
    mockedLogoutAll.mockRejectedValue(new AxiosError('Network Error'));
    const client = await renderDevices();

    await confirmLogoutAll();

    expect(await screen.findByText('Không kết nối được máy chủ')).toBeTruthy();
    expect(mockedLogoutAll).toHaveBeenCalledTimes(1);
    expect(mockedLogout).not.toHaveBeenCalled();
    await expectSessionKept();
    expect(client.getQueryData(ME_QUERY_KEY)).toEqual(DEMO_ME);
    // Nút bấm lại được sau lỗi.
    expect(screen.getByRole('button', { name: LOGOUT_ALL_BUTTON })).toBeEnabled();
  });

  it('FEAUTH-17 logoutAll bị 403 permission_denied: hiện thông điệp theo error.code, giữ phiên', async () => {
    mockedLogoutAll.mockRejectedValue(apiError(403, 'permission_denied'));
    await renderDevices();

    await confirmLogoutAll();

    expect(await screen.findByText('Bạn không có quyền thực hiện thao tác này')).toBeTruthy();
    expect(screen.queryByText('Thông điệp server (permission_denied)')).toBeNull();
    await expectSessionKept();
  });

  it('FEAUTH-17 nút "Quay lại" gọi router.back()', async () => {
    await renderDevices();

    await fireEvent.press(screen.getByRole('button', { name: 'Quay lại' }));

    expect(router.back).toHaveBeenCalledTimes(1);
  });
});
