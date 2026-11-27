import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react-native';
import { AxiosError, AxiosHeaders } from 'axios';
import { router, useLocalSearchParams } from 'expo-router';
import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import { TextField } from '@/components/common';
import { AUTH_REQUIRED } from '@/constants/features';
import { PERMISSION_DENIED_MESSAGE, toFormErrors } from '@/screens/auth/form-errors';
import LoginScreen from '@/screens/auth/LoginScreen';
import type { ApiErrorDetail } from '@/services/api/errors';
import { getAccessToken, getDeviceId, getRefreshToken } from '@/services/api/session-storage';
import { login } from '@/services/auth';
import { useSession } from '@/store/session';
import type { LoginResponse } from '@/types/auth';
import { toDevicePlatform } from '@/utils/device';

jest.mock('@/services/auth');
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
  useLocalSearchParams: jest.fn(() => ({})),
  Redirect: () => null,
}));

// Lần render đầu của suite nạp lười module React Native; khi cổng chạy cả suite song song với --coverage,
// test đầu có thể vượt timeout 5s mặc định. jest.config.js là file core nên nâng timeout tại đây.
jest.setTimeout(20_000);

const mockedLogin = jest.mocked(login);
const mockedSearchParams = jest.mocked(useLocalSearchParams);

// Dữ liệu giả theo persona seed "demo" (spec fe-auth §5), không phải dữ liệu người dùng thật.
const DEMO_EMAIL = 'demo@smartworkout.local';
const DEMO_PASSWORD = 'Demo@123';
const LOGIN_RESPONSE: LoginResponse = {
  access_token: 'acc-1',
  refresh_token: 'ref-1',
  token_type: 'bearer',
  expires_in: 1800,
  device_id: 'c1a7f1e0-2b53-4d57-9d2c-8d0d3a8f2a10',
  user: { id: '5eed0000-0000-4000-8000-000000000003', email: DEMO_EMAIL, display_name: 'An', roles: ['user'] },
};

/** Lỗi API giả theo Claude_api_respone.md §3; `message` cố ý khác thông điệp màn hiện để chứng minh rẽ nhánh theo code. */
function apiError(status: number, code: string, details: ApiErrorDetail[] = []): AxiosError {
  const config = { headers: new AxiosHeaders() };
  const data = { error: { code, message: `Thông điệp server (${code})`, details, request_id: 'req-test' } };
  return new AxiosError('fail', 'ERR_BAD_RESPONSE', config, null, { status, statusText: '', headers: {}, config, data });
}

function deferred<T>() {
  let resolve: (value: T) => void = () => undefined;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

async function renderLogin() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LoginScreen />
    </QueryClientProvider>,
  );
}

async function fillForm(email: string, password: string) {
  await fireEvent.changeText(screen.getByLabelText('Email'), email);
  await fireEvent.changeText(screen.getByLabelText('Mật khẩu'), password);
}

async function pressLogin() {
  await fireEvent.press(screen.getByRole('button', { name: 'Đăng nhập' }));
}

beforeEach(() => {
  jest.clearAllMocks();
  mockedSearchParams.mockReturnValue({});
  useSession.setState({ status: 'signedOut', user: null });
});

describe('LoginScreen: đăng nhập thành công', () => {
  it.each([
    { name: 'đã có device_id', storedDeviceId: 'dev-9' },
    { name: 'chưa có device_id', storedDeviceId: null },
  ])('FEAUTH-04 $name: gọi login đúng 1 lần, lưu phiên rồi về trang chủ', async ({ storedDeviceId }) => {
    if (storedDeviceId) await SecureStore.setItemAsync('device_id', storedDeviceId);
    const pending = deferred<LoginResponse>();
    mockedLogin.mockReturnValue(pending.promise);
    await renderLogin();

    await fillForm(`  ${DEMO_EMAIL} `, DEMO_PASSWORD);
    // fireEvent của RNTL 14 trả về promise của handler: lần bấm đầu chỉ xong khi `login` resolve.
    const firstPress = pressLogin();
    await waitFor(() => expect(mockedLogin).toHaveBeenCalledTimes(1));
    await pressLogin();
    expect(mockedLogin).toHaveBeenCalledTimes(1);
    expect(mockedLogin).toHaveBeenCalledWith({
      email: DEMO_EMAIL,
      password: DEMO_PASSWORD,
      device: expect.objectContaining({ device_id: storedDeviceId, platform: toDevicePlatform(Platform.OS) }),
    });

    await act(async () => {
      pending.resolve(LOGIN_RESPONSE);
      await firstPress;
    });
    expect(router.replace).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith('/');
    expect(mockedLogin).toHaveBeenCalledTimes(1);
    expect(await getAccessToken()).toBe('acc-1');
    expect(await getRefreshToken()).toBe('ref-1');
    expect(await getDeviceId()).toBe('c1a7f1e0-2b53-4d57-9d2c-8d0d3a8f2a10');
    expect(useSession.getState().status).toBe('signedIn');
    expect(useSession.getState().user).toEqual(LOGIN_RESPONSE.user);
  });

  it('FEAUTH-04 không gửi push_token, gửi os_version dạng chuỗi', async () => {
    mockedLogin.mockResolvedValue(LOGIN_RESPONSE);
    await renderLogin();
    await fillForm(DEMO_EMAIL, DEMO_PASSWORD);
    await pressLogin();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith('/'));
    const device = mockedLogin.mock.calls[0]?.[0].device;
    expect(device).not.toHaveProperty('push_token');
    expect(device?.os_version).toBe(String(Platform.Version));
  });
});

describe('LoginScreen: kiểm tra phía client, điều hướng, thông báo', () => {
  it('FEAUTH-05 (a) hai ô rỗng: báo lỗi dưới từng ô và không gọi login', async () => {
    await renderLogin();
    await pressLogin();
    expect(within(screen.getByTestId('field-Email')).getByText('Email không hợp lệ')).toBeTruthy();
    expect(within(screen.getByTestId('field-Mật khẩu')).getByText('Vui lòng nhập mật khẩu')).toBeTruthy();
    expect(mockedLogin).not.toHaveBeenCalled();
  });

  it('FEAUTH-05 (b) email sai định dạng: báo lỗi dưới ô Email và không gọi login', async () => {
    await renderLogin();
    await fillForm('khong-phai-email', DEMO_PASSWORD);
    await pressLogin();
    expect(within(screen.getByTestId('field-Email')).getByText('Email không hợp lệ')).toBeTruthy();
    expect(screen.queryByText('Vui lòng nhập mật khẩu')).toBeNull();
    expect(mockedLogin).not.toHaveBeenCalled();
  });

  it('FEAUTH-05 (b) sửa lại email đúng thì lỗi client biến mất khi gửi lại', async () => {
    mockedLogin.mockResolvedValue(LOGIN_RESPONSE);
    await renderLogin();
    await fillForm('khong-phai-email', DEMO_PASSWORD);
    await pressLogin();
    expect(screen.getByText('Email không hợp lệ')).toBeTruthy();
    await fillForm(DEMO_EMAIL, DEMO_PASSWORD);
    await pressLogin();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith('/'));
    expect(screen.queryByText('Email không hợp lệ')).toBeNull();
  });

  it('FEAUTH-05 (c) bấm "Chưa có tài khoản? Đăng ký" thì mở /register', async () => {
    await renderLogin();
    await fireEvent.press(screen.getByRole('button', { name: 'Chưa có tài khoản? Đăng ký' }));
    expect(router.push).toHaveBeenCalledTimes(1);
    expect(router.push).toHaveBeenCalledWith('/register');
  });

  it.each([
    { notice: 'password_changed', message: 'Đã đổi mật khẩu. Vui lòng đăng nhập lại.' },
    { notice: 'registered', message: 'Đăng ký thành công. Vui lòng đăng nhập.' },
  ])('FEAUTH-05 (d, e) notice "$notice" hiện đúng thông báo', async ({ notice, message }) => {
    mockedSearchParams.mockReturnValue({ notice });
    await renderLogin();
    expect(screen.getByText(message)).toBeTruthy();
  });

  it('FEAUTH-05 notice lạ hoặc không có thì không hiện thông báo', async () => {
    mockedSearchParams.mockReturnValue({ notice: 'constructor' });
    await renderLogin();
    expect(screen.queryByText('Đã đổi mật khẩu. Vui lòng đăng nhập lại.')).toBeNull();
    expect(screen.queryByText('Đăng ký thành công. Vui lòng đăng nhập.')).toBeNull();
  });
});

describe('LoginScreen: lỗi API theo error.code', () => {
  const cases = [
    { name: '401 invalid_credentials', error: apiError(401, 'invalid_credentials'), message: 'Email hoặc mật khẩu không đúng', fieldId: null },
    {
      name: '403 account_disabled',
      error: apiError(403, 'account_disabled'),
      message: 'Tài khoản đã bị vô hiệu hoá. Vui lòng liên hệ hỗ trợ.',
      fieldId: null,
    },
    {
      name: '403 email_not_verified',
      error: apiError(403, 'email_not_verified'),
      message: 'Email chưa được xác thực. Vui lòng kiểm tra hộp thư.',
      fieldId: null,
    },
    {
      name: '423 account_locked có retry_after_seconds',
      error: apiError(423, 'account_locked', [{ field: null, code: 'retry_after_seconds', message: '840' }]),
      message: 'Tài khoản tạm khoá. Thử lại sau 14 phút.',
      fieldId: null,
    },
    {
      name: '423 account_locked không có retry_after_seconds',
      error: apiError(423, 'account_locked', []),
      message: 'Tài khoản đã bị khoá. Vui lòng liên hệ quản trị viên.',
      fieldId: null,
    },
    {
      name: '422 validation_error theo field email',
      error: apiError(422, 'validation_error', [{ field: 'email', message: 'Email sai', code: 'value_error' }]),
      message: 'Email sai',
      fieldId: 'field-Email',
    },
    { name: 'lỗi mạng', error: new AxiosError('Network Error'), message: 'Không kết nối được máy chủ', fieldId: null },
  ];

  it.each(cases)('FEAUTH-06 $name: hiện đúng thông điệp, giữ signedOut, bấm lại được', async ({ error, message, fieldId }) => {
    mockedLogin.mockRejectedValue(error);
    await renderLogin();
    await fillForm(DEMO_EMAIL, DEMO_PASSWORD);
    await pressLogin();

    expect(await screen.findByText(message)).toBeTruthy();
    const emailField = within(screen.getByTestId('field-Email'));
    if (fieldId) expect(within(screen.getByTestId(fieldId)).getByText(message)).toBeTruthy();
    else expect(emailField.queryByText(message)).toBeNull();
    expect(screen.queryByText(/Thông điệp server/)).toBeNull();
    expect(useSession.getState().status).toBe('signedOut');
    expect(await getAccessToken()).toBeNull();
    expect(router.replace).not.toHaveBeenCalled();

    await pressLogin();
    await waitFor(() => expect(mockedLogin).toHaveBeenCalledTimes(2));
  });

  it('FEAUTH-06 account_locked với retry_after_seconds không phải số thì báo khoá liên hệ quản trị viên', async () => {
    mockedLogin.mockRejectedValue(apiError(423, 'account_locked', [{ field: null, code: 'retry_after_seconds', message: 'abc' }]));
    await renderLogin();
    await fillForm(DEMO_EMAIL, DEMO_PASSWORD);
    await pressLogin();
    expect(await screen.findByText('Tài khoản đã bị khoá. Vui lòng liên hệ quản trị viên.')).toBeTruthy();
  });

  it('FEAUTH-06 lỗi validation của mật khẩu hiện dưới ô Mật khẩu', async () => {
    const details = [{ field: 'password', message: 'Mật khẩu quá dài', code: 'string_too_long' }];
    mockedLogin.mockRejectedValue(apiError(422, 'validation_error', details));
    await renderLogin();
    await fillForm(DEMO_EMAIL, DEMO_PASSWORD);
    await pressLogin();
    expect(await within(screen.getByTestId('field-Mật khẩu')).findByText('Mật khẩu quá dài')).toBeTruthy();
  });
});

describe('Cờ tính năng', () => {
  it('FEAUTH-23 AUTH_REQUIRED bật: tab chỉ mở sau khi đăng nhập', () => {
    expect(AUTH_REQUIRED).toBe(true);
  });
});

describe('toFormErrors', () => {
  const fields = ['email', 'password'] as const;

  it('validation_error: field thuộc form thì gắn vào ô, không có lỗi chung', () => {
    const err = apiError(422, 'validation_error', [{ field: 'email', message: 'Email sai', code: 'value_error' }]);
    expect(toFormErrors(err, { fields })).toEqual({ fields: { email: 'Email sai' }, form: null });
  });

  it('validation_error: có field không thuộc form thì thêm lỗi chung từ getErrorMessage', () => {
    const err = apiError(422, 'validation_error', [
      { field: 'email', message: 'Email sai', code: 'value_error' },
      { field: 'device.platform', message: 'Nền tảng sai', code: 'enum' },
    ]);
    expect(toFormErrors(err, { fields })).toEqual({ fields: { email: 'Email sai' }, form: 'Thông điệp server (validation_error)' });
  });

  it('validation_error: không có field nào thì báo lỗi chung', () => {
    const err = apiError(422, 'validation_error', [{ field: null, message: 'Chung', code: 'x' }]);
    expect(toFormErrors(err, { fields })).toEqual({ fields: {}, form: 'Thông điệp server (validation_error)' });
  });

  it('mã có trong messages và fieldOf thì gắn thông điệp vào đúng ô', () => {
    const err = apiError(409, 'email_already_exists');
    const result = toFormErrors(err, {
      fields,
      messages: { email_already_exists: 'Email đã được sử dụng' },
      fieldOf: { email_already_exists: 'email' },
    });
    expect(result).toEqual({ fields: { email: 'Email đã được sử dụng' }, form: null });
  });

  it('mã có trong messages nhưng không có fieldOf thì là lỗi chung', () => {
    const err = apiError(409, 'active_goal_already_exists');
    const messages = { active_goal_already_exists: 'Đã có mục tiêu' };
    expect(toFormErrors(err, { fields, messages })).toEqual({ fields: {}, form: 'Đã có mục tiêu' });
  });

  it('permission_denied dùng thông điệp chung không có quyền', () => {
    expect(toFormErrors(apiError(403, 'permission_denied'), { fields })).toEqual({ fields: {}, form: PERMISSION_DENIED_MESSAGE });
  });

  it('mã chưa map, lỗi mạng và lỗi không phải axios dùng getErrorMessage', () => {
    expect(toFormErrors(apiError(500, 'internal_error'), { fields }).form).toBe('Thông điệp server (internal_error)');
    expect(toFormErrors(new AxiosError('Network Error'), { fields }).form).toBe('Không kết nối được máy chủ');
    expect(toFormErrors(new Error('x'), { fields }).form).toBe('Đã có lỗi, vui lòng thử lại');
  });

  it('mã trùng tên thuộc tính có sẵn của object không bị coi là đã map', () => {
    const err = apiError(400, 'constructor');
    expect(toFormErrors(err, { fields, messages: {} })).toEqual({ fields: {}, form: 'Thông điệp server (constructor)' });
  });
});

describe('TextField', () => {
  it('nhãn là accessibilityLabel, hiện đơn vị cạnh ô và lỗi dưới ô', async () => {
    const onChangeText = jest.fn();
    await render(<TextField label="Cân nặng mục tiêu" value="70,5" onChangeText={onChangeText} suffix="kg" error="Sai" />);
    await fireEvent.changeText(screen.getByLabelText('Cân nặng mục tiêu'), '71');
    expect(onChangeText).toHaveBeenCalledWith('71');
    const field = within(screen.getByTestId('field-Cân nặng mục tiêu'));
    expect(field.getByText('kg')).toBeTruthy();
    expect(field.getByText('Sai')).toBeTruthy();
  });

  it('lỗi về null thì ẩn dòng lỗi; placeholder hiện trong ô', async () => {
    const label = 'Ngày đạt mục tiêu';
    const view = await render(<TextField label={label} value="" onChangeText={jest.fn()} placeholder="dd/mm/yyyy" error="Sai ngày" />);
    expect(screen.getByText('Sai ngày')).toBeTruthy();
    await view.rerender(<TextField label={label} value="" onChangeText={jest.fn()} placeholder="dd/mm/yyyy" error={null} />);
    expect(screen.queryByText('Sai ngày')).toBeNull();
    expect(screen.getByPlaceholderText('dd/mm/yyyy')).toBeTruthy();
  });
});
