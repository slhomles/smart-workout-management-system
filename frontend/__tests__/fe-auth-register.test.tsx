import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react-native';
import { AxiosError, AxiosHeaders } from 'axios';
import { router } from 'expo-router';
import { Platform } from 'react-native';

import RegisterScreen from '@/screens/auth/RegisterScreen';
import type { ApiErrorDetail } from '@/services/api/errors';
import { getAccessToken } from '@/services/api/session-storage';
import { login, register } from '@/services/auth';
import { useSession } from '@/store/session';
import type { LoginResponse, RegisterResponse } from '@/types/auth';
import { toDevicePlatform } from '@/utils/device';
import { checkFullName } from '@/utils/validation';

jest.mock('@/services/auth');
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
  useLocalSearchParams: jest.fn(() => ({})),
  Redirect: () => null,
}));

// Lần render đầu của suite nạp lười module React Native; khi cổng chạy cả suite song song với --coverage,
// test đầu có thể vượt timeout 5s mặc định. jest.config.js là file core nên nâng timeout tại đây.
jest.setTimeout(20_000);

const mockedRegister = jest.mocked(register);
const mockedLogin = jest.mocked(login);

// Dữ liệu giả theo spec fe-auth §5 FEAUTH-07, không phải dữ liệu người dùng thật.
const NEW_EMAIL = 'moi.user@example.com';
const NEW_PASSWORD = 'Moi@12345';
const NEW_USER_ID = 'b7e2c4a0-0000-4000-8000-000000000007';
const REGISTER_RESPONSE: RegisterResponse = {
  id: NEW_USER_ID,
  email: NEW_EMAIL,
  display_name: 'Mới',
  full_name: 'Người Mới',
  roles: ['user'],
  status: 'active',
};
const LOGIN_RESPONSE: LoginResponse = {
  access_token: 'acc-1',
  refresh_token: 'ref-1',
  token_type: 'bearer',
  expires_in: 1800,
  device_id: 'c1a7f1e0-2b53-4d57-9d2c-8d0d3a8f2a10',
  user: { id: NEW_USER_ID, email: NEW_EMAIL, display_name: 'Mới', roles: ['user'] },
};
const REGISTERED_NOTICE_ROUTE = { pathname: '/login', params: { notice: 'registered' } };

type RegisterValues = {
  email: string;
  displayName: string;
  fullName: string;
  password: string;
  passwordConfirm: string;
};

const VALID_VALUES: RegisterValues = {
  email: NEW_EMAIL,
  displayName: ' Mới ',
  fullName: 'Người Mới',
  password: NEW_PASSWORD,
  passwordConfirm: NEW_PASSWORD,
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

async function renderRegister() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RegisterScreen />
    </QueryClientProvider>,
  );
}

async function fillForm(values: RegisterValues) {
  await fireEvent.changeText(screen.getByLabelText('Email'), values.email);
  await fireEvent.changeText(screen.getByLabelText('Tên hiển thị'), values.displayName);
  await fireEvent.changeText(screen.getByLabelText('Họ và tên'), values.fullName);
  await fireEvent.changeText(screen.getByLabelText('Mật khẩu'), values.password);
  await fireEvent.changeText(screen.getByLabelText('Nhập lại mật khẩu'), values.passwordConfirm);
}

function pressRegister() {
  return fireEvent.press(screen.getByRole('button', { name: 'Đăng ký' }));
}

function fieldOf(label: string) {
  return within(screen.getByTestId(`field-${label}`));
}

beforeEach(() => {
  jest.clearAllMocks();
  useSession.setState({ status: 'signedOut', user: null });
});

describe('RegisterScreen: đăng ký thành công rồi tự đăng nhập', () => {
  it('FEAUTH-07 (a) gửi đúng 4 field, rồi đăng nhập bằng cùng email/mật khẩu và về trang chủ', async () => {
    mockedRegister.mockResolvedValue(REGISTER_RESPONSE);
    mockedLogin.mockResolvedValue(LOGIN_RESPONSE);
    await renderRegister();

    await fillForm(VALID_VALUES);
    await pressRegister();

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith('/'));
    expect(mockedRegister).toHaveBeenCalledTimes(1);
    expect(mockedRegister.mock.calls[0]?.[0]).toStrictEqual({
      email: NEW_EMAIL,
      password: NEW_PASSWORD,
      display_name: 'Mới',
      full_name: 'Người Mới',
    });
    expect(mockedLogin).toHaveBeenCalledTimes(1);
    expect(mockedLogin).toHaveBeenCalledWith(
      expect.objectContaining({
        email: NEW_EMAIL,
        password: NEW_PASSWORD,
        device: expect.objectContaining({ platform: toDevicePlatform(Platform.OS) }),
      }),
    );
    expect(mockedRegister.mock.invocationCallOrder[0]).toBeLessThan(mockedLogin.mock.invocationCallOrder[0] ?? 0);
    expect(useSession.getState().status).toBe('signedIn');
    expect(useSession.getState().user).toEqual(LOGIN_RESPONSE.user);
    expect(await getAccessToken()).toBe('acc-1');
    expect(router.replace).toHaveBeenCalledTimes(1);
  });

  it('FEAUTH-07 (b) Họ và tên trống thì gửi full_name null', async () => {
    mockedRegister.mockResolvedValue({ ...REGISTER_RESPONSE, full_name: null });
    mockedLogin.mockResolvedValue(LOGIN_RESPONSE);
    await renderRegister();

    await fillForm({ ...VALID_VALUES, fullName: '' });
    await pressRegister();

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith('/'));
    expect(mockedRegister).toHaveBeenCalledTimes(1);
    expect(mockedRegister.mock.calls[0]?.[0]).toStrictEqual({
      email: NEW_EMAIL,
      password: NEW_PASSWORD,
      display_name: 'Mới',
      full_name: null,
    });
  });

  it('FEAUTH-07 (b) Họ và tên chỉ có khoảng trắng cũng gửi full_name null; email được trim', async () => {
    mockedRegister.mockResolvedValue({ ...REGISTER_RESPONSE, full_name: null });
    mockedLogin.mockResolvedValue(LOGIN_RESPONSE);
    await renderRegister();

    await fillForm({ ...VALID_VALUES, email: `  ${NEW_EMAIL} `, fullName: '   ' });
    await pressRegister();

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith('/'));
    expect(mockedRegister.mock.calls[0]?.[0]).toStrictEqual({
      email: NEW_EMAIL,
      password: NEW_PASSWORD,
      display_name: 'Mới',
      full_name: null,
    });
    expect(mockedLogin).toHaveBeenCalledWith(expect.objectContaining({ email: NEW_EMAIL, password: NEW_PASSWORD }));
  });

  it('FEAUTH-07 (c) tự đăng nhập lỗi email_not_verified thì về màn đăng nhập với notice registered', async () => {
    mockedRegister.mockResolvedValue(REGISTER_RESPONSE);
    mockedLogin.mockRejectedValue(apiError(403, 'email_not_verified'));
    await renderRegister();

    await fillForm(VALID_VALUES);
    await pressRegister();

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith(REGISTERED_NOTICE_ROUTE));
    expect(router.replace).toHaveBeenCalledTimes(1);
    expect(mockedRegister).toHaveBeenCalledTimes(1);
    expect(mockedLogin).toHaveBeenCalledTimes(1);
    expect(useSession.getState().status).toBe('signedOut');
    expect(await getAccessToken()).toBeNull();
    // Lỗi đăng nhập không hiện trên màn đăng ký: màn đăng nhập sẽ báo "Đăng ký thành công".
    expect(screen.queryByText(/Thông điệp server/)).toBeNull();
    expect(screen.queryByText('Email chưa được xác thực. Vui lòng kiểm tra hộp thư.')).toBeNull();
  });

  it('FEAUTH-07 (c) tự đăng nhập lỗi mạng cũng về màn đăng nhập với notice registered', async () => {
    mockedRegister.mockResolvedValue(REGISTER_RESPONSE);
    mockedLogin.mockRejectedValue(new AxiosError('Network Error'));
    await renderRegister();

    await fillForm(VALID_VALUES);
    await pressRegister();

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith(REGISTERED_NOTICE_ROUTE));
    expect(useSession.getState().status).toBe('signedOut');
    expect(screen.queryByText('Không kết nối được máy chủ')).toBeNull();
  });

  it('FEAUTH-07 bấm "Đăng ký" 2 lần khi register còn chờ thì chỉ gửi 1 lần', async () => {
    const pending = deferred<RegisterResponse>();
    mockedRegister.mockReturnValue(pending.promise);
    mockedLogin.mockResolvedValue(LOGIN_RESPONSE);
    await renderRegister();

    await fillForm(VALID_VALUES);
    // fireEvent của RNTL 14 trả về promise của handler: lần bấm đầu chỉ xong khi `register` resolve.
    const firstPress = pressRegister();
    await waitFor(() => expect(mockedRegister).toHaveBeenCalledTimes(1));
    await pressRegister();
    expect(mockedRegister).toHaveBeenCalledTimes(1);
    expect(mockedLogin).not.toHaveBeenCalled();

    await act(async () => {
      pending.resolve(REGISTER_RESPONSE);
      await firstPress;
    });
    expect(mockedRegister).toHaveBeenCalledTimes(1);
    expect(mockedLogin).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith('/');
  });

  it('bấm "Đã có tài khoản? Đăng nhập" thì về màn đăng nhập', async () => {
    await renderRegister();
    await fireEvent.press(screen.getByRole('button', { name: 'Đã có tài khoản? Đăng nhập' }));
    expect(router.replace).toHaveBeenCalledTimes(1);
    expect(router.replace).toHaveBeenCalledWith('/login');
    expect(mockedRegister).not.toHaveBeenCalled();
  });
});

describe('RegisterScreen: lỗi', () => {
  it('FEAUTH-08 client: hiện mọi lỗi dưới đúng ô và không gọi register', async () => {
    await renderRegister();
    await fillForm({
      email: 'khong-phai-email',
      displayName: '   ',
      fullName: '',
      password: 'abcdefgh',
      passwordConfirm: 'Moi@12346',
    });
    await pressRegister();

    expect(fieldOf('Email').getByText('Email không hợp lệ')).toBeTruthy();
    expect(fieldOf('Tên hiển thị').getByText('Tên hiển thị cần 1–50 ký tự')).toBeTruthy();
    expect(fieldOf('Mật khẩu').getByText('Mật khẩu cần 8–72 byte, có ít nhất 1 chữ cái và 1 chữ số')).toBeTruthy();
    expect(fieldOf('Nhập lại mật khẩu').getByText('Mật khẩu nhập lại không khớp')).toBeTruthy();
    expect(fieldOf('Mật khẩu').queryByText('Mật khẩu nhập lại không khớp')).toBeNull();
    expect(screen.queryByText('Họ và tên tối đa 100 ký tự')).toBeNull();
    expect(mockedRegister).not.toHaveBeenCalled();
    expect(mockedLogin).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it('FEAUTH-08 client: Họ và tên 101 ký tự báo lỗi dưới ô Họ và tên và không gọi register', async () => {
    await renderRegister();
    await fillForm({ ...VALID_VALUES, fullName: 'a'.repeat(101) });
    await pressRegister();

    expect(fieldOf('Họ và tên').getByText('Họ và tên tối đa 100 ký tự')).toBeTruthy();
    expect(mockedRegister).not.toHaveBeenCalled();
    expect(mockedLogin).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it('FEAUTH-08 client: sửa lại cho hợp lệ thì lỗi client biến mất và register được gọi', async () => {
    mockedRegister.mockResolvedValue(REGISTER_RESPONSE);
    mockedLogin.mockResolvedValue(LOGIN_RESPONSE);
    await renderRegister();
    await fillForm({ ...VALID_VALUES, passwordConfirm: 'Moi@12346' });
    await pressRegister();
    expect(screen.getByText('Mật khẩu nhập lại không khớp')).toBeTruthy();
    expect(mockedRegister).not.toHaveBeenCalled();

    await fireEvent.changeText(screen.getByLabelText('Nhập lại mật khẩu'), NEW_PASSWORD);
    await pressRegister();
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith('/'));
    expect(screen.queryByText('Mật khẩu nhập lại không khớp')).toBeNull();
    expect(mockedRegister).toHaveBeenCalledTimes(1);
  });

  const serverCases = [
    {
      name: '409 email_already_exists',
      error: apiError(409, 'email_already_exists'),
      message: 'Email đã được sử dụng',
      fieldLabel: 'Email',
    },
    {
      name: '422 validation_error theo field password',
      error: apiError(422, 'validation_error', [
        { field: 'password', message: 'Mật khẩu phải có ít nhất 1 chữ số', code: 'value_error' },
      ]),
      message: 'Mật khẩu phải có ít nhất 1 chữ số',
      fieldLabel: 'Mật khẩu',
    },
    { name: 'lỗi mạng', error: new AxiosError('Network Error'), message: 'Không kết nối được máy chủ', fieldLabel: null },
  ];

  it.each(serverCases)(
    'FEAUTH-08 server $name: hiện đúng thông điệp, không đăng nhập, không điều hướng, bấm lại được',
    async ({ error, message, fieldLabel }) => {
      mockedRegister.mockRejectedValue(error);
      await renderRegister();
      await fillForm(VALID_VALUES);
      await pressRegister();

      expect(await screen.findByText(message)).toBeTruthy();
      if (fieldLabel) expect(fieldOf(fieldLabel).getByText(message)).toBeTruthy();
      else expect(fieldOf('Email').queryByText(message)).toBeNull();
      expect(screen.queryByText(/Thông điệp server/)).toBeNull();
      expect(mockedLogin).not.toHaveBeenCalled();
      expect(router.replace).not.toHaveBeenCalled();
      expect(useSession.getState().status).toBe('signedOut');

      await pressRegister();
      await waitFor(() => expect(mockedRegister).toHaveBeenCalledTimes(2));
    },
  );

  it('FEAUTH-08 server validation_error theo display_name và full_name hiện dưới đúng ô', async () => {
    mockedRegister.mockRejectedValue(
      apiError(422, 'validation_error', [
        { field: 'display_name', message: 'Tên sai', code: 'value_error' },
        { field: 'full_name', message: 'Họ tên sai', code: 'string_too_long' },
      ]),
    );
    await renderRegister();
    await fillForm(VALID_VALUES);
    await pressRegister();

    expect(await fieldOf('Tên hiển thị').findByText('Tên sai')).toBeTruthy();
    expect(fieldOf('Họ và tên').getByText('Họ tên sai')).toBeTruthy();
    expect(screen.queryByText(/Thông điệp server/)).toBeNull();
    expect(mockedLogin).not.toHaveBeenCalled();
  });

  it('FEAUTH-08 server validation_error có field không có ô thì hiện thông điệp chung', async () => {
    mockedRegister.mockRejectedValue(
      apiError(422, 'validation_error', [{ field: 'status', message: 'Field lạ', code: 'extra_forbidden' }]),
    );
    await renderRegister();
    await fillForm(VALID_VALUES);
    await pressRegister();

    expect(await screen.findByText('Thông điệp server (validation_error)')).toBeTruthy();
    expect(mockedLogin).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
  });

  it('FEAUTH-08 server permission_denied hiện thông điệp không có quyền', async () => {
    mockedRegister.mockRejectedValue(apiError(403, 'permission_denied'));
    await renderRegister();
    await fillForm(VALID_VALUES);
    await pressRegister();

    expect(await screen.findByText('Bạn không có quyền thực hiện thao tác này')).toBeTruthy();
    expect(mockedLogin).not.toHaveBeenCalled();
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe('checkFullName (spec fe-auth §2.4)', () => {
  // Chuỗi kỳ vọng chép nguyên từ spec fe-auth §2.4 (không dùng lại hằng của code để bắt lỗi chính tả).
  const FULL_NAME_MESSAGE = 'Họ và tên tối đa 100 ký tự';
  // "é" dạng dựng sẵn U+00E9: 1 ký tự (viết escape để không phụ thuộc chuẩn hoá Unicode của editor).
  const E_ACUTE = 'é';

  it('FEAUTH-08 checkFullName trống hoặc chỉ có khoảng trắng trả value null, không lỗi', () => {
    expect(checkFullName('')).toEqual({ value: null, error: null });
    expect(checkFullName('   ')).toEqual({ value: null, error: null });
  });

  it('FEAUTH-08 checkFullName bỏ khoảng trắng hai đầu', () => {
    expect(checkFullName(' Người Mới ')).toEqual({ value: 'Người Mới', error: null });
  });

  it('FEAUTH-08 checkFullName chấp nhận đúng 100 ký tự, 101 ký tự thì báo lỗi', () => {
    expect(checkFullName('a'.repeat(100))).toEqual({ value: 'a'.repeat(100), error: null });
    expect(checkFullName('a'.repeat(101)).error).toBe(FULL_NAME_MESSAGE);
  });

  it('FEAUTH-08 checkFullName đếm ký tự có dấu là 1 ký tự và không tính khoảng trắng hai đầu', () => {
    expect(checkFullName(E_ACUTE.repeat(100)).error).toBeNull();
    expect(checkFullName(E_ACUTE.repeat(101)).error).toBe(FULL_NAME_MESSAGE);
    expect(checkFullName(` ${'a'.repeat(100)} `).error).toBeNull();
  });
});
