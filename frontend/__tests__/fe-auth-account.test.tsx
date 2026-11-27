import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react-native';
import { AxiosError, AxiosHeaders } from 'axios';
import { router } from 'expo-router';
import type { ReactElement } from 'react';

import { ME_QUERY_KEY } from '@/hooks/auth/useMe';
import EditProfileScreen from '@/screens/profile/EditProfileScreen';
import UnitSystemScreen from '@/screens/profile/UnitSystemScreen';
import type { ApiErrorDetail } from '@/services/api/errors';
import { getMe, updateMe } from '@/services/auth';
import { useSession } from '@/store/session';
import type { Me } from '@/types/auth';

jest.mock('@/services/auth');
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
  useLocalSearchParams: jest.fn(() => ({})),
  Redirect: () => null,
}));

const mockedGetMe = jest.mocked(getMe);
const mockedUpdateMe = jest.mocked(updateMe);

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
const SESSION_USER = {
  id: DEMO_ME.id,
  email: DEMO_ME.email,
  display_name: DEMO_ME.display_name,
  roles: DEMO_ME.roles,
};

// Chuỗi kỳ vọng chép nguyên từ spec fe-auth §2.4 (không dùng lại hằng của code để bắt lỗi chính tả).
const DISPLAY_NAME_MESSAGE = 'Tên hiển thị cần 1–50 ký tự';
const FULL_NAME_MESSAGE = 'Họ và tên tối đa 100 ký tự';
const NETWORK_MESSAGE = 'Không kết nối được máy chủ';
const METRIC = 'Mét (kg, cm)';
const IMPERIAL = 'Anh (lb, in)';

/**
 * Lỗi API giả theo Claude_api_respone.md §3. Mặc định `message` cố ý khác thông điệp màn hiện để chứng minh
 * rẽ nhánh theo code; FEAUTH-14 (c) truyền `message` riêng vì màn hiện đúng `message` của server.
 */
function apiError(
  status: number,
  code: string,
  details: ApiErrorDetail[] = [],
  message = `Thông điệp server (${code})`,
) {
  const config = { headers: new AxiosHeaders() };
  const data = { error: { code, message, details, request_id: 'req-test' } };
  return new AxiosError('fail', 'ERR_BAD_RESPONSE', config, null, {
    status,
    statusText: '',
    headers: {},
    config,
    data,
  });
}

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

async function renderScreen(ui: ReactElement): Promise<QueryClient> {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClients.push(client);
  await render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
  return client;
}

function fieldOf(label: string) {
  return within(screen.getByTestId(`field-${label}`));
}

function button(name: string) {
  return screen.getByRole('button', { name });
}

function cachedMe(client: QueryClient): Me | undefined {
  return client.getQueryData<Me>(ME_QUERY_KEY);
}

beforeEach(() => {
  jest.clearAllMocks();
  // `useMe` tắt khi `signedOut` nên các màn dùng `useMe` cần phiên `signedIn` (spec fe-auth §5).
  useSession.setState({ status: 'signedIn', user: SESSION_USER });
  mockedGetMe.mockResolvedValue(DEMO_ME);
});

// Gỡ màn rồi xoá cache: nếu không, timer `gcTime` (mặc định 5 phút) của React Query giữ tiến trình jest không thoát.
afterEach(async () => {
  await cleanup();
  for (const client of queryClients.splice(0)) client.clear();
});

describe('EditProfileScreen: sửa hồ sơ thành công', () => {
  async function renderEditProfile(): Promise<QueryClient> {
    const client = await renderScreen(<EditProfileScreen />);
    await screen.findByLabelText('Tên hiển thị');
    return client;
  }

  async function fillProfile(displayName: string, fullName: string) {
    await fireEvent.changeText(screen.getByLabelText('Tên hiển thị'), displayName);
    await fireEvent.changeText(screen.getByLabelText('Họ và tên'), fullName);
  }

  function pressSave() {
    return fireEvent.press(button('Lưu'));
  }

  it('FEAUTH-12 điền sẵn Tên hiển thị "An" và Họ và tên "Nguyễn Văn An" từ GET /auth/me', async () => {
    await renderEditProfile();

    expect(screen.getByRole('header', { name: 'Hồ sơ' })).toBeTruthy();
    expect(screen.getByLabelText('Tên hiển thị')).toHaveDisplayValue('An');
    expect(screen.getByLabelText('Họ và tên')).toHaveDisplayValue('Nguyễn Văn An');
    expect(mockedGetMe).toHaveBeenCalledTimes(1);
  });

  it('FEAUTH-12 (a) gửi đúng field đã đổi, ghi cache và session rồi quay lại', async () => {
    mockedUpdateMe.mockResolvedValue({ ...DEMO_ME, display_name: 'An Nguyễn', full_name: null });
    const client = await renderEditProfile();

    await fillProfile('An Nguyễn', '');
    await pressSave();

    await waitFor(() => expect(router.back).toHaveBeenCalledTimes(1));
    expect(mockedUpdateMe).toHaveBeenCalledTimes(1);
    expect(mockedUpdateMe.mock.calls[0]?.[0]).toStrictEqual({ display_name: 'An Nguyễn', full_name: null });
    expect(cachedMe(client)?.display_name).toBe('An Nguyễn');
    expect(cachedMe(client)?.full_name).toBeNull();
    expect(useSession.getState().user).toStrictEqual({
      id: '5eed0000-0000-4000-8000-000000000003',
      email: 'demo@smartworkout.local',
      display_name: 'An Nguyễn',
      roles: ['user'],
    });
    expect(useSession.getState().status).toBe('signedIn');
    expect(mockedUpdateMe.mock.invocationCallOrder[0]).toBeLessThan(
      jest.mocked(router.back).mock.invocationCallOrder[0] ?? 0,
    );
  });

  it('FEAUTH-12 (b) không sửa gì: không gọi updateMe, chỉ quay lại', async () => {
    const client = await renderEditProfile();

    await pressSave();

    expect(mockedUpdateMe).not.toHaveBeenCalled();
    expect(router.back).toHaveBeenCalledTimes(1);
    expect(cachedMe(client)).toEqual(DEMO_ME);
    expect(useSession.getState().user).toStrictEqual(SESSION_USER);
  });

  it('FEAUTH-12 (b) chỉ thêm khoảng trắng hai đầu cũng coi như không đổi', async () => {
    await renderEditProfile();

    await fillProfile('  An ', ' Nguyễn Văn An  ');
    await pressSave();

    expect(mockedUpdateMe).not.toHaveBeenCalled();
    expect(router.back).toHaveBeenCalledTimes(1);
  });

  it('FEAUTH-12 chỉ đổi Họ và tên thì body chỉ có full_name đã trim', async () => {
    mockedUpdateMe.mockResolvedValue({ ...DEMO_ME, full_name: 'Nguyễn Văn Bình' });
    await renderEditProfile();

    await fillProfile(' An ', '  Nguyễn Văn Bình ');
    await pressSave();

    await waitFor(() => expect(router.back).toHaveBeenCalledTimes(1));
    expect(mockedUpdateMe.mock.calls[0]?.[0]).toStrictEqual({ full_name: 'Nguyễn Văn Bình' });
  });

  it('FEAUTH-12 bấm "Lưu" hai lần khi updateMe còn chờ thì chỉ gửi một lần', async () => {
    const pending = deferred<Me>();
    mockedUpdateMe.mockReturnValue(pending.promise);
    await renderEditProfile();
    await fillProfile('An Nguyễn', 'Nguyễn Văn An');

    // Lần bấm đầu treo tới khi `updateMe` resolve nên không await.
    const firstPress = pressSave();
    await waitFor(() => expect(mockedUpdateMe).toHaveBeenCalledTimes(1));
    await pressSave();
    await act(async () => {
      pending.resolve({ ...DEMO_ME, display_name: 'An Nguyễn' });
      await firstPress;
    });

    expect(mockedUpdateMe).toHaveBeenCalledTimes(1);
    expect(router.back).toHaveBeenCalledTimes(1);
  });

  it('FEAUTH-12 GET /auth/me đang tải: hiện "Đang tải...", chưa có form', async () => {
    mockedGetMe.mockReturnValue(new Promise<Me>(() => undefined));
    await renderScreen(<EditProfileScreen />);

    expect(screen.getByLabelText('Đang tải...')).toBeTruthy();
    expect(screen.queryByLabelText('Tên hiển thị')).toBeNull();
  });

  it('FEAUTH-12 GET /auth/me lỗi mạng: báo lỗi, bấm "Thử lại" thì hiện form', async () => {
    mockedGetMe.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(DEMO_ME);
    await renderScreen(<EditProfileScreen />);

    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(screen.queryByLabelText('Tên hiển thị')).toBeNull();

    await fireEvent.press(button('Thử lại'));

    expect(await screen.findByLabelText('Tên hiển thị')).toHaveDisplayValue('An');
    expect(mockedGetMe).toHaveBeenCalledTimes(2);
  });

  it('FEAUTH-12 nút "Quay lại" gọi router.back()', async () => {
    await renderEditProfile();

    await fireEvent.press(button('Quay lại'));

    expect(router.back).toHaveBeenCalledTimes(1);
    expect(mockedUpdateMe).not.toHaveBeenCalled();
  });
});

describe('EditProfileScreen: lỗi', () => {
  async function renderEditProfile(): Promise<QueryClient> {
    const client = await renderScreen(<EditProfileScreen />);
    await screen.findByLabelText('Tên hiển thị');
    return client;
  }

  function expectNothingSaved(client: QueryClient) {
    expect(router.back).not.toHaveBeenCalled();
    expect(cachedMe(client)?.display_name).toBe('An');
    expect(useSession.getState().user).toStrictEqual(SESSION_USER);
  }

  const clientCases = [
    {
      name: 'Tên hiển thị chỉ có khoảng trắng',
      label: 'Tên hiển thị',
      value: '   ',
      message: DISPLAY_NAME_MESSAGE,
    },
    {
      name: 'Tên hiển thị 51 ký tự',
      label: 'Tên hiển thị',
      value: 'a'.repeat(51),
      message: DISPLAY_NAME_MESSAGE,
    },
    { name: 'Họ và tên 101 ký tự', label: 'Họ và tên', value: 'a'.repeat(101), message: FULL_NAME_MESSAGE },
  ];

  it.each(clientCases)(
    'FEAUTH-13 client $name: hiện lỗi dưới đúng ô, không gọi updateMe',
    async ({ label, value, message }) => {
      const client = await renderEditProfile();

      await fireEvent.changeText(screen.getByLabelText(label), value);
      await fireEvent.press(button('Lưu'));

      expect(fieldOf(label).getByText(message)).toBeTruthy();
      expect(screen.getAllByText(message)).toHaveLength(1);
      expect(mockedUpdateMe).not.toHaveBeenCalled();
      expectNothingSaved(client);
    },
  );

  it('FEAUTH-13 client: Tên hiển thị đúng 50 ký tự vẫn hợp lệ', async () => {
    const name = 'a'.repeat(50);
    mockedUpdateMe.mockResolvedValue({ ...DEMO_ME, display_name: name });
    await renderEditProfile();

    await fireEvent.changeText(screen.getByLabelText('Tên hiển thị'), name);
    await fireEvent.press(button('Lưu'));

    await waitFor(() => expect(router.back).toHaveBeenCalledTimes(1));
    expect(screen.queryByText(DISPLAY_NAME_MESSAGE)).toBeNull();
    expect(mockedUpdateMe.mock.calls[0]?.[0]).toStrictEqual({ display_name: name });
  });

  const serverCases = [
    {
      name: '422 validation_error theo field display_name',
      error: apiError(422, 'validation_error', [
        { field: 'display_name', message: 'Tên không hợp lệ', code: 'value_error' },
      ]),
      message: 'Tên không hợp lệ',
      fieldLabel: 'Tên hiển thị' as string | null,
    },
    { name: 'lỗi mạng', error: networkError(), message: NETWORK_MESSAGE, fieldLabel: null },
    {
      name: '403 permission_denied',
      error: apiError(403, 'permission_denied'),
      message: 'Bạn không có quyền thực hiện thao tác này',
      fieldLabel: null,
    },
  ];

  it.each(serverCases)(
    'FEAUTH-13 server $name: hiện đúng thông điệp, không quay lại, cache giữ nguyên, bấm lại được',
    async ({ error, message, fieldLabel }) => {
      mockedUpdateMe.mockRejectedValue(error);
      const client = await renderEditProfile();

      await fireEvent.changeText(screen.getByLabelText('Tên hiển thị'), 'An Nguyễn');
      await fireEvent.press(button('Lưu'));

      expect(await screen.findByText(message)).toBeTruthy();
      if (fieldLabel) expect(fieldOf(fieldLabel).getByText(message)).toBeTruthy();
      else expect(fieldOf('Tên hiển thị').queryByText(message)).toBeNull();
      expect(screen.queryByText(/Thông điệp server/)).toBeNull();
      expect(mockedUpdateMe).toHaveBeenCalledTimes(1);
      expectNothingSaved(client);

      await fireEvent.press(button('Lưu'));
      await waitFor(() => expect(mockedUpdateMe).toHaveBeenCalledTimes(2));
      expect(router.back).not.toHaveBeenCalled();
    },
  );
});

describe('UnitSystemScreen: đơn vị đo', () => {
  async function renderUnits(): Promise<QueryClient> {
    const client = await renderScreen(<UnitSystemScreen />);
    await screen.findByRole('button', { name: METRIC });
    return client;
  }

  function chip(label: string) {
    return button(label);
  }

  function expectSelected(selected: string, other: string) {
    expect(chip(selected)).toBeSelected();
    expect(chip(other)).not.toBeSelected();
  }

  it('FEAUTH-14 ban đầu Chip "Mét (kg, cm)" được chọn theo unit_system của server', async () => {
    await renderUnits();

    expect(screen.getByRole('header', { name: 'Đơn vị đo' })).toBeTruthy();
    expect(chip(METRIC).props.accessibilityState).toEqual(expect.objectContaining({ selected: true }));
    expectSelected(METRIC, IMPERIAL);
  });

  it('FEAUTH-14 unit_system null coi như metric', async () => {
    mockedGetMe.mockResolvedValue({ ...DEMO_ME, unit_system: null });
    await renderUnits();

    expectSelected(METRIC, IMPERIAL);
  });

  it('FEAUTH-14 (a) bấm "Anh (lb, in)": gửi đúng unit_system, Chip đổi theo dữ liệu server và cache', async () => {
    mockedUpdateMe.mockResolvedValue({ ...DEMO_ME, unit_system: 'imperial' });
    const client = await renderUnits();

    await fireEvent.press(chip(IMPERIAL));

    await waitFor(() => expect(chip(IMPERIAL)).toBeSelected());
    expect(chip(METRIC)).not.toBeSelected();
    expect(mockedUpdateMe).toHaveBeenCalledTimes(1);
    expect(mockedUpdateMe.mock.calls[0]?.[0]).toStrictEqual({ unit_system: 'imperial' });
    expect(cachedMe(client)?.unit_system).toBe('imperial');
  });

  it('FEAUTH-14 (a) không cập nhật lạc quan và chặn bấm khi đang gửi', async () => {
    const pending = deferred<Me>();
    mockedUpdateMe.mockReturnValue(pending.promise);
    const client = await renderUnits();

    // Lần bấm đầu treo tới khi `updateMe` resolve nên không await.
    const firstPress = fireEvent.press(chip(IMPERIAL));
    await waitFor(() => expect(mockedUpdateMe).toHaveBeenCalledTimes(1));
    expectSelected(METRIC, IMPERIAL);
    expect(cachedMe(client)?.unit_system).toBe('metric');
    await fireEvent.press(chip(IMPERIAL));
    expect(mockedUpdateMe).toHaveBeenCalledTimes(1);

    await act(async () => {
      pending.resolve({ ...DEMO_ME, unit_system: 'imperial' });
      await firstPress;
    });

    expectSelected(IMPERIAL, METRIC);
    expect(mockedUpdateMe).toHaveBeenCalledTimes(1);
  });

  it('FEAUTH-14 (b) bấm Chip đang chọn "Mét (kg, cm)": không gọi updateMe', async () => {
    const client = await renderUnits();

    await fireEvent.press(chip(METRIC));

    expect(mockedUpdateMe).not.toHaveBeenCalled();
    expectSelected(METRIC, IMPERIAL);
    expect(cachedMe(client)?.unit_system).toBe('metric');
  });

  it('FEAUTH-14 (c) updateMe lỗi 422 validation_error: hiện message của server, giữ Chip và cache', async () => {
    mockedUpdateMe.mockRejectedValue(
      apiError(
        422,
        'validation_error',
        [{ field: 'unit_system', message: 'Chi tiết không có ô (unit_system)', code: 'enum' }],
        'Dữ liệu gửi lên không hợp lệ',
      ),
    );
    const client = await renderUnits();

    await fireEvent.press(chip(IMPERIAL));

    expect(await screen.findByText('Dữ liệu gửi lên không hợp lệ')).toBeTruthy();
    expect(screen.queryByText('Chi tiết không có ô (unit_system)')).toBeNull();
    expectSelected(METRIC, IMPERIAL);
    expect(cachedMe(client)?.unit_system).toBe('metric');
    expect(mockedUpdateMe).toHaveBeenCalledTimes(1);
  });

  it('FEAUTH-14 (c) lỗi mạng hiện "Không kết nối được máy chủ"; lần sau thành công thì xoá lỗi', async () => {
    mockedUpdateMe
      .mockRejectedValueOnce(networkError())
      .mockResolvedValueOnce({ ...DEMO_ME, unit_system: 'imperial' });
    await renderUnits();

    await fireEvent.press(chip(IMPERIAL));
    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    expectSelected(METRIC, IMPERIAL);

    await fireEvent.press(chip(IMPERIAL));
    await waitFor(() => expect(chip(IMPERIAL)).toBeSelected());
    expect(screen.queryByText(NETWORK_MESSAGE)).toBeNull();
    expect(mockedUpdateMe).toHaveBeenCalledTimes(2);
  });

  it('FEAUTH-14 GET /auth/me đang tải rồi lỗi: hiện "Đang tải...", lỗi có "Thử lại"', async () => {
    mockedGetMe.mockReturnValue(new Promise<Me>(() => undefined));
    await renderScreen(<UnitSystemScreen />);
    expect(screen.getByLabelText('Đang tải...')).toBeTruthy();
    expect(screen.queryByRole('button', { name: METRIC })).toBeNull();
    await cleanup();

    mockedGetMe.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(DEMO_ME);
    await renderScreen(<UnitSystemScreen />);
    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    await fireEvent.press(button('Thử lại'));
    expect(await screen.findByRole('button', { name: METRIC })).toBeSelected();
  });

  it('FEAUTH-14 nút "Quay lại" gọi router.back()', async () => {
    await renderUnits();

    await fireEvent.press(button('Quay lại'));

    expect(router.back).toHaveBeenCalledTimes(1);
  });
});
