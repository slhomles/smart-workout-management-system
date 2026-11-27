import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react-native';
import { AxiosError, AxiosHeaders } from 'axios';
import { router } from 'expo-router';

import { ME_QUERY_KEY } from '@/hooks/auth/useMe';
import ChangePasswordScreen from '@/screens/profile/ChangePasswordScreen';
import type { ApiErrorDetail } from '@/services/api/errors';
import { getAccessToken, getDeviceId, getRefreshToken, saveTokens } from '@/services/api/session-storage';
import { changePassword, getMe, logout } from '@/services/auth';
import { useSession } from '@/store/session';
import type { Me } from '@/types/auth';

jest.mock('@/services/auth');
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
  useLocalSearchParams: jest.fn(() => ({})),
  Redirect: () => null,
}));

const mockedChangePassword = jest.mocked(changePassword);
const mockedLogout = jest.mocked(logout);
const mockedGetMe = jest.mocked(getMe);

// Dữ liệu giả theo persona seed "demo" (spec fe-auth §5), không phải người dùng thật. Mật khẩu là mật khẩu seed.
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
const SESSION_USER = {
  id: DEMO_ME.id,
  email: DEMO_ME.email,
  display_name: DEMO_ME.display_name,
  roles: DEMO_ME.roles,
};
const CURRENT_PASSWORD = 'Demo@123';
const NEW_PASSWORD = 'Moi@12345';
const PASSWORD_CHANGED_ROUTE = { pathname: '/login', params: { notice: 'password_changed' } };

// Chuỗi kỳ vọng chép nguyên từ spec fe-auth §2.4 (không dùng lại hằng của code để bắt lỗi chính tả).
const PASSWORD_REQUIRED_MESSAGE = 'Vui lòng nhập mật khẩu';
const PASSWORD_POLICY_MESSAGE = 'Mật khẩu cần 8–72 byte, có ít nhất 1 chữ cái và 1 chữ số';
const PASSWORD_MISMATCH_MESSAGE = 'Mật khẩu nhập lại không khớp';

type PasswordValues = { current: string; next: string; confirm: string };
const VALID_VALUES: PasswordValues = { current: CURRENT_PASSWORD, next: NEW_PASSWORD, confirm: NEW_PASSWORD };

/** Lỗi API giả theo Claude_api_respone.md §3; `message` cố ý khác thông điệp màn hiện để chứng minh rẽ nhánh theo code. */
function apiError(status: number, code: string, details: ApiErrorDetail[] = []): AxiosError {
  const config = { headers: new AxiosHeaders() };
  const data = { error: { code, message: `Thông điệp server (${code})`, details, request_id: 'req-test' } };
  return new AxiosError('fail', 'ERR_BAD_RESPONSE', config, null, {
    status,
    statusText: '',
    headers: {},
    config,
    data,
  });
}

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

const queryClients: QueryClient[] = [];

async function renderChangePassword(): Promise<QueryClient> {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClients.push(client);
  client.setQueryData(ME_QUERY_KEY, DEMO_ME);
  await render(
    <QueryClientProvider client={client}>
      <ChangePasswordScreen />
    </QueryClientProvider>,
  );
  return client;
}

async function fillForm(values: PasswordValues) {
  await fireEvent.changeText(screen.getByLabelText('Mật khẩu hiện tại'), values.current);
  await fireEvent.changeText(screen.getByLabelText('Mật khẩu mới'), values.next);
  await fireEvent.changeText(screen.getByLabelText('Nhập lại mật khẩu mới'), values.confirm);
}

// Tiêu đề màn cũng là "Đổi mật khẩu" nhưng có role `header`, nên bấm nút qua role `button`.
function pressChange() {
  return fireEvent.press(screen.getByRole('button', { name: 'Đổi mật khẩu' }));
}

function fieldOf(label: string) {
  return within(screen.getByTestId(`field-${label}`));
}

async function expectSessionKept(client: QueryClient) {
  expect(await getAccessToken()).toBe('a');
  expect(await getRefreshToken()).toBe('r-1');
  expect(useSession.getState().status).toBe('signedIn');
  expect(useSession.getState().user).toStrictEqual(SESSION_USER);
  expect(client.getQueryData(ME_QUERY_KEY)).toEqual(DEMO_ME);
  expect(router.replace).not.toHaveBeenCalled();
}

beforeEach(async () => {
  jest.clearAllMocks();
  useSession.setState({ status: 'signedIn', user: SESSION_USER });
  await saveTokens({ access_token: 'a', refresh_token: 'r-1' }, 'dev-9');
});

// Gỡ màn rồi xoá cache: nếu không, timer `gcTime` (mặc định 5 phút) của React Query giữ tiến trình jest không thoát.
afterEach(async () => {
  await cleanup();
  for (const client of queryClients.splice(0)) client.clear();
});

describe('ChangePasswordScreen: đổi mật khẩu thành công', () => {
  it('FEAUTH-15 gửi đúng 2 field, không gọi logout, xoá phiên và cache rồi về /login với notice', async () => {
    mockedChangePassword.mockResolvedValue(DEMO_ME);
    const client = await renderChangePassword();

    await fillForm(VALID_VALUES);
    await pressChange();

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith(PASSWORD_CHANGED_ROUTE));
    expect(router.replace).toHaveBeenCalledTimes(1);
    expect(mockedChangePassword).toHaveBeenCalledTimes(1);
    expect(mockedChangePassword.mock.calls[0]?.[0]).toStrictEqual({
      current_password: CURRENT_PASSWORD,
      new_password: NEW_PASSWORD,
    });
    expect(mockedLogout).not.toHaveBeenCalled();
    expect(await getAccessToken()).toBeNull();
    expect(await getRefreshToken()).toBeNull();
    expect(await getDeviceId()).toBe('dev-9');
    expect(useSession.getState().status).toBe('signedOut');
    expect(useSession.getState().user).toBeNull();
    expect(client.getQueryData(ME_QUERY_KEY)).toBeUndefined();
    // Màn đổi mật khẩu không dùng `useMe`: không gọi `/auth/me`.
    expect(mockedGetMe).not.toHaveBeenCalled();
  });

  it('FEAUTH-15 mật khẩu gửi nguyên văn, không trim khoảng trắng', async () => {
    mockedChangePassword.mockResolvedValue(DEMO_ME);
    await renderChangePassword();

    await fillForm({
      current: ` ${CURRENT_PASSWORD} `,
      next: ` ${NEW_PASSWORD}`,
      confirm: ` ${NEW_PASSWORD}`,
    });
    await pressChange();

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith(PASSWORD_CHANGED_ROUTE));
    expect(mockedChangePassword.mock.calls[0]?.[0]).toStrictEqual({
      current_password: ` ${CURRENT_PASSWORD} `,
      new_password: ` ${NEW_PASSWORD}`,
    });
  });

  it('FEAUTH-15 bấm "Đổi mật khẩu" hai lần khi còn chờ thì chỉ gửi một lần', async () => {
    const pending = deferred<Me>();
    mockedChangePassword.mockReturnValue(pending.promise);
    await renderChangePassword();
    await fillForm(VALID_VALUES);

    // Lần bấm đầu treo tới khi `changePassword` resolve nên không await.
    const firstPress = pressChange();
    await waitFor(() => expect(mockedChangePassword).toHaveBeenCalledTimes(1));
    await pressChange();
    expect(mockedChangePassword).toHaveBeenCalledTimes(1);

    await act(async () => {
      pending.resolve(DEMO_ME);
      await firstPress;
    });

    expect(mockedChangePassword).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith(PASSWORD_CHANGED_ROUTE);
  });

  it('FEAUTH-15 có tiêu đề "Đổi mật khẩu" và nút "Quay lại" gọi router.back()', async () => {
    await renderChangePassword();

    expect(screen.getByRole('header', { name: 'Đổi mật khẩu' })).toBeTruthy();
    await fireEvent.press(screen.getByRole('button', { name: 'Quay lại' }));

    expect(router.back).toHaveBeenCalledTimes(1);
    expect(mockedChangePassword).not.toHaveBeenCalled();
  });
});

describe('ChangePasswordScreen: lỗi', () => {
  it('FEAUTH-16 client: báo mọi lỗi cùng lúc dưới đúng ô, không gọi changePassword', async () => {
    const client = await renderChangePassword();

    await fillForm({ current: '', next: 'abcdefgh', confirm: NEW_PASSWORD });
    await pressChange();

    expect(fieldOf('Mật khẩu hiện tại').getByText(PASSWORD_REQUIRED_MESSAGE)).toBeTruthy();
    expect(fieldOf('Mật khẩu mới').getByText(PASSWORD_POLICY_MESSAGE)).toBeTruthy();
    expect(fieldOf('Nhập lại mật khẩu mới').getByText(PASSWORD_MISMATCH_MESSAGE)).toBeTruthy();
    expect(mockedChangePassword).not.toHaveBeenCalled();
    await expectSessionKept(client);
  });

  const clientCases = [
    {
      name: 'Mật khẩu hiện tại rỗng',
      values: { ...VALID_VALUES, current: '' },
      label: 'Mật khẩu hiện tại',
      message: PASSWORD_REQUIRED_MESSAGE,
    },
    {
      name: 'Mật khẩu mới "abcdefgh"',
      values: { ...VALID_VALUES, next: 'abcdefgh', confirm: 'abcdefgh' },
      label: 'Mật khẩu mới',
      message: PASSWORD_POLICY_MESSAGE,
    },
    {
      name: 'Nhập lại khác Mật khẩu mới',
      values: { ...VALID_VALUES, confirm: 'Moi@12346' },
      label: 'Nhập lại mật khẩu mới',
      message: PASSWORD_MISMATCH_MESSAGE,
    },
  ];

  it.each(clientCases)(
    'FEAUTH-16 client $name: chỉ báo lỗi dưới ô đó, không gọi changePassword',
    async (item) => {
      const client = await renderChangePassword();

      await fillForm(item.values);
      await pressChange();

      expect(fieldOf(item.label).getByText(item.message)).toBeTruthy();
      for (const other of [PASSWORD_REQUIRED_MESSAGE, PASSWORD_POLICY_MESSAGE, PASSWORD_MISMATCH_MESSAGE]) {
        expect(screen.queryAllByText(other)).toHaveLength(other === item.message ? 1 : 0);
      }
      expect(mockedChangePassword).not.toHaveBeenCalled();
      await expectSessionKept(client);
    },
  );

  const serverCases = [
    {
      name: '401 invalid_credentials',
      error: apiError(401, 'invalid_credentials'),
      message: 'Mật khẩu hiện tại không đúng',
      fieldLabel: 'Mật khẩu hiện tại' as string | null,
    },
    {
      name: '422 validation_error theo field new_password',
      error: apiError(422, 'validation_error', [
        { field: 'new_password', message: 'Mật khẩu phải có ít nhất 1 chữ số', code: 'value_error' },
      ]),
      message: 'Mật khẩu phải có ít nhất 1 chữ số',
      fieldLabel: 'Mật khẩu mới',
    },
    {
      name: 'lỗi mạng',
      error: new AxiosError('Network Error'),
      message: 'Không kết nối được máy chủ',
      fieldLabel: null,
    },
    {
      name: '403 permission_denied',
      error: apiError(403, 'permission_denied'),
      message: 'Bạn không có quyền thực hiện thao tác này',
      fieldLabel: null,
    },
  ];

  it.each(serverCases)(
    'FEAUTH-16 server $name: hiện đúng thông điệp, giữ phiên, không điều hướng, bấm lại được',
    async ({ error, message, fieldLabel }) => {
      mockedChangePassword.mockRejectedValue(error);
      const client = await renderChangePassword();

      await fillForm(VALID_VALUES);
      await pressChange();

      expect(await screen.findByText(message)).toBeTruthy();
      if (fieldLabel) expect(fieldOf(fieldLabel).getByText(message)).toBeTruthy();
      else expect(fieldOf('Mật khẩu hiện tại').queryByText(message)).toBeNull();
      expect(screen.queryByText(/Thông điệp server/)).toBeNull();
      expect(mockedLogout).not.toHaveBeenCalled();
      await expectSessionKept(client);

      await pressChange();
      await waitFor(() => expect(mockedChangePassword).toHaveBeenCalledTimes(2));
      expect(router.replace).not.toHaveBeenCalled();
    },
  );
});
