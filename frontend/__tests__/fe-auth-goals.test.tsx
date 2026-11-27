import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react-native';
import { AxiosError, AxiosHeaders } from 'axios';
import { router } from 'expo-router';

import GoalsScreen from '@/screens/profile/GoalsScreen';
import { goalStatusLabel } from '@/screens/profile/labels';
import type { ApiErrorDetail } from '@/services/api/errors';
import { getMe } from '@/services/auth';
import { listGoals, updateGoal } from '@/services/profile';
import { useSession } from '@/store/session';
import type { Me } from '@/types/auth';
import type { Page } from '@/types/page';
import type { UserGoal } from '@/types/profile';

jest.mock('@/services/auth');
jest.mock('@/services/profile');
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
  useLocalSearchParams: jest.fn(() => ({})),
  Redirect: () => null,
}));

const mockedGetMe = jest.mocked(getMe);
const mockedListGoals = jest.mocked(listGoals);
const mockedUpdateGoal = jest.mocked(updateGoal);

// Dữ liệu giả theo persona seed "demo" và "other" (spec fe-auth §5), không phải người dùng thật.
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
const OTHER_ME: Me = {
  ...DEMO_ME,
  id: '5eed0000-0000-4000-8000-000000000010',
  email: 'other@smartworkout.local',
  display_name: 'Phương',
  full_name: 'Bùi Phương',
  locale: 'en-US',
  unit_system: 'imperial',
};
const SESSION_USER = {
  id: DEMO_ME.id,
  email: DEMO_ME.email,
  display_name: DEMO_ME.display_name,
  roles: DEMO_ME.roles,
};

// Mục tiêu giả theo FEAUTH-19; loại mục tiêu lấy `code`/`name` theo seeds/02_reference.sql.
const G1: UserGoal = {
  id: 'g-1',
  goal_type: { id: 1, code: 'lose_fat', name: 'Giảm mỡ' },
  target_weight_kg: 66,
  target_body_fat_pct: null,
  start_date: '2026-11-01',
  target_date: '2027-03-01',
  status: 'active',
  closed_at: null,
  created_at: '2026-11-01T02:00:00Z',
  updated_at: '2026-11-01T02:00:00Z',
};
const G2: UserGoal = {
  id: 'g-2',
  goal_type: { id: 2, code: 'gain_muscle', name: 'Tăng cơ' },
  target_weight_kg: 70.5,
  target_body_fat_pct: null,
  start_date: '2026-05-01',
  target_date: null,
  status: 'achieved',
  closed_at: '2026-10-15T09:30:00Z',
  created_at: '2026-05-01T01:00:00Z',
  updated_at: '2026-10-15T09:30:00Z',
};
const G3: UserGoal = {
  id: 'g-3',
  goal_type: { id: 5, code: 'maintain', name: 'Duy trì' },
  target_weight_kg: null,
  target_body_fat_pct: null,
  start_date: '2026-01-10',
  target_date: null,
  status: 'abandoned',
  closed_at: '2026-04-20T07:00:00Z',
  created_at: '2026-01-10T03:00:00Z',
  updated_at: '2026-04-20T07:00:00Z',
};
const G1_ACHIEVED: UserGoal = { ...G1, status: 'achieved', closed_at: '2026-11-28T04:00:00Z' };
const G1_ABANDONED: UserGoal = { ...G1, status: 'abandoned', closed_at: '2026-11-28T04:00:00Z' };

// Chuỗi kỳ vọng chép nguyên từ spec fe-auth §2.4 (không dùng lại hằng của code để bắt lỗi chính tả).
const NETWORK_MESSAGE = 'Không kết nối được máy chủ';
const PERMISSION_MESSAGE = 'Bạn không có quyền thực hiện thao tác này';
const GOAL_NOT_FOUND_MESSAGE = 'Mục tiêu không còn tồn tại';
const ACHIEVE = 'Đánh dấu đã đạt';
const ABANDON = 'Bỏ mục tiêu';
const NEW_GOAL = 'Đặt mục tiêu mới';
const LIST_TEST_ID = 'goals-list';

/** Lỗi API giả theo Claude_api_respone.md §3; `message` cố ý khác thông điệp màn hiện để chứng minh rẽ nhánh theo code. */
function apiError(status: number, code: string, details: ApiErrorDetail[] = []) {
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

function page(data: UserGoal[], nextCursor: string | null = null): Page<UserGoal> {
  return { data, pagination: { next_cursor: nextCursor, has_more: nextCursor !== null } };
}

const queryClients: QueryClient[] = [];

async function renderGoals(): Promise<QueryClient> {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClients.push(client);
  await render(
    <QueryClientProvider client={client}>
      <GoalsScreen />
    </QueryClientProvider>,
  );
  return client;
}

function button(name: string) {
  return screen.getByRole('button', { name });
}

function goalCard(goalId: string) {
  return within(screen.getByTestId(`goal-${goalId}`));
}

/** Cho các promise đang chờ chạy xong, để khẳng định "không có lần gọi thêm". */
async function flushPromises() {
  await act(async () => {
    await new Promise((done) => setTimeout(done, 0));
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  // `useMe` tắt khi `signedOut` nên màn dùng `useMe` cần phiên `signedIn` (spec fe-auth §5).
  useSession.setState({ status: 'signedIn', user: SESSION_USER });
  mockedGetMe.mockResolvedValue(DEMO_ME);
});

// Gỡ màn rồi xoá cache: nếu không, timer `gcTime` (mặc định 5 phút) của React Query giữ tiến trình jest không thoát.
afterEach(async () => {
  await cleanup();
  for (const client of queryClients.splice(0)) client.clear();
});

describe('GoalsScreen: 4 trạng thái', () => {
  it('FEAUTH-18 (a) GET /body/goals đang tải: hiện "Đang tải...", chưa có nút "Đặt mục tiêu mới"', async () => {
    mockedListGoals.mockReturnValue(new Promise<Page<UserGoal>>(() => undefined));
    await renderGoals();

    await waitFor(() => expect(mockedListGoals).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText('Đang tải...')).toBeTruthy();
    expect(screen.getByRole('header', { name: 'Mục tiêu' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: NEW_GOAL })).toBeNull();
  });

  it('FEAUTH-18 (b) lỗi mạng: báo lỗi có "Thử lại"; bấm thì hiện mục tiêu và nút "Đặt mục tiêu mới"', async () => {
    mockedListGoals.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(page([G1]));
    await renderGoals();

    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(button('Thử lại')).toBeTruthy();
    expect(screen.queryByRole('button', { name: NEW_GOAL })).toBeNull();

    await fireEvent.press(button('Thử lại'));

    expect(await screen.findByText('Giảm mỡ')).toBeTruthy();
    expect(screen.queryByText(NETWORK_MESSAGE)).toBeNull();
    expect(mockedListGoals).toHaveBeenCalledTimes(2);

    await fireEvent.press(button(NEW_GOAL));
    expect(router.push).toHaveBeenCalledTimes(1);
    expect(router.push).toHaveBeenCalledWith('/account/new-goal');
  });

  it('FEAUTH-18 (c) 403 permission_denied: hiện thông điệp riêng, không hiện message của server', async () => {
    mockedListGoals.mockRejectedValue(apiError(403, 'permission_denied'));
    await renderGoals();

    expect(await screen.findByText(PERMISSION_MESSAGE)).toBeTruthy();
    expect(screen.queryByText(/Thông điệp server/)).toBeNull();
    expect(button('Thử lại')).toBeTruthy();
  });

  it('FEAUTH-18 (d) danh sách rỗng: hiện "Chưa có mục tiêu" và nút "Đặt mục tiêu mới"', async () => {
    mockedListGoals.mockResolvedValue({ data: [], pagination: { next_cursor: null, has_more: false } });
    await renderGoals();

    expect(await screen.findByText('Chưa có mục tiêu')).toBeTruthy();
    expect(screen.queryByLabelText('Đang tải...')).toBeNull();

    await fireEvent.press(button(NEW_GOAL));
    expect(router.push).toHaveBeenCalledWith('/account/new-goal');
  });

  it('FEAUTH-18 GET /auth/me lỗi: báo lỗi, chưa gọi listGoals; "Thử lại" thì tải tiếp danh sách', async () => {
    mockedGetMe.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(DEMO_ME);
    mockedListGoals.mockResolvedValue(page([G1]));
    await renderGoals();

    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(mockedListGoals).not.toHaveBeenCalled();

    await fireEvent.press(button('Thử lại'));

    expect(await screen.findByText('Giảm mỡ')).toBeTruthy();
    expect(mockedGetMe).toHaveBeenCalledTimes(2);
  });

  it('FEAUTH-18 nút "Quay lại" gọi router.back()', async () => {
    mockedListGoals.mockResolvedValue(page([]));
    await renderGoals();
    await screen.findByText('Chưa có mục tiêu');

    await fireEvent.press(button('Quay lại'));

    expect(router.back).toHaveBeenCalledTimes(1);
  });
});

describe('GoalsScreen: dữ liệu, đơn vị, phân trang', () => {
  function mockTwoPages() {
    mockedListGoals.mockResolvedValueOnce(page([G1, G2], 'c-2')).mockResolvedValueOnce(page([G3]));
  }

  function reachEnd() {
    return fireEvent(screen.getByTestId(LIST_TEST_ID), 'endReached');
  }

  function expectCloseButtonsOnlyOnG1() {
    expect(screen.getAllByRole('button', { name: ACHIEVE })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: ABANDON })).toHaveLength(1);
    expect(goalCard('g-1').getByRole('button', { name: ACHIEVE })).toBeTruthy();
    expect(goalCard('g-1').getByRole('button', { name: ABANDON })).toBeTruthy();
    expect(goalCard('g-2').queryByRole('button', { name: ACHIEVE })).toBeNull();
    expect(goalCard('g-2').queryByRole('button', { name: ABANDON })).toBeNull();
  }

  it('FEAUTH-19 metric: hiện loại, cân nặng, ngày, trạng thái; tải trang 2 theo cursor, không gọi lần 3', async () => {
    mockTwoPages();
    await renderGoals();
    await screen.findByText('Giảm mỡ');

    // Dòng meta "66 kg • 01/03/2027" (spec fe-auth §4): khẳng định đúng cả chuỗi, tức đúng từng giá trị.
    expect(goalCard('g-1').getByText('66 kg • 01/03/2027')).toBeTruthy();
    expect(goalCard('g-1').getByText('Đang thực hiện')).toBeTruthy();
    expect(goalCard('g-2').getByText('Tăng cơ')).toBeTruthy();
    expect(goalCard('g-2').getByText('70,5 kg')).toBeTruthy();
    expect(goalCard('g-2').getByText('Đã đạt')).toBeTruthy();
    expectCloseButtonsOnlyOnG1();
    // Chưa cuộn tới cuối thì chưa tải trang 2.
    expect(screen.queryByText('Duy trì')).toBeNull();
    expect(mockedListGoals).toHaveBeenCalledTimes(1);
    expect(mockedListGoals.mock.calls[0]?.[0]).toStrictEqual({ limit: 20 });

    await reachEnd();
    expect(await screen.findByText('Duy trì')).toBeTruthy();
    expect(goalCard('g-3').getByText('Đã bỏ')).toBeTruthy();
    expect(mockedListGoals.mock.calls[1]?.[0]).toStrictEqual({ limit: 20, cursor: 'c-2' });

    await reachEnd();
    await flushPromises();
    expect(mockedListGoals).toHaveBeenCalledTimes(2);
    expectCloseButtonsOnlyOnG1();
    expect(goalCard('g-1').getByText('Giảm mỡ')).toBeTruthy();
  });

  it('FEAUTH-19 imperial (persona other): cân nặng hiện theo lb, không còn "66 kg"', async () => {
    mockedGetMe.mockResolvedValue(OTHER_ME);
    mockTwoPages();
    await renderGoals();
    await screen.findByText('Giảm mỡ');

    expect(goalCard('g-1').getByText('145,5 lb • 01/03/2027')).toBeTruthy();
    expect(goalCard('g-2').getByText('155,4 lb')).toBeTruthy();
    expect(screen.queryByText(/66 kg/)).toBeNull();
    expect(screen.queryByText(/ kg/)).toBeNull();
    expectCloseButtonsOnlyOnG1();

    await reachEnd();
    expect(await screen.findByText('Duy trì')).toBeTruthy();
    expect(mockedListGoals).toHaveBeenCalledTimes(2);
  });

  it('FEAUTH-19 unit_system null coi như metric', async () => {
    mockedGetMe.mockResolvedValue({ ...DEMO_ME, unit_system: null });
    mockedListGoals.mockResolvedValue(page([G1]));
    await renderGoals();

    expect(await screen.findByText('66 kg • 01/03/2027')).toBeTruthy();
  });

  it('FEAUTH-19 gọi endReached liên tiếp khi trang 2 còn đang tải thì chỉ gửi một request trang 2', async () => {
    const secondPage = deferred<Page<UserGoal>>();
    mockedListGoals.mockResolvedValueOnce(page([G1, G2], 'c-2')).mockReturnValueOnce(secondPage.promise);
    await renderGoals();
    await screen.findByText('Giảm mỡ');

    await reachEnd();
    await reachEnd();
    await flushPromises();
    expect(mockedListGoals).toHaveBeenCalledTimes(2);

    await act(async () => {
      secondPage.resolve(page([G3]));
    });
    expect(await screen.findByText('Duy trì')).toBeTruthy();
    expect(mockedListGoals).toHaveBeenCalledTimes(2);
  });

  it('FEAUTH-19 trang 2 lỗi mạng: giữ trang 1, báo lỗi; bấm "Thử lại" thì tải lại trang 2', async () => {
    mockedListGoals
      .mockResolvedValueOnce(page([G1, G2], 'c-2'))
      .mockRejectedValueOnce(networkError())
      .mockResolvedValueOnce(page([G3]));
    await renderGoals();
    await screen.findByText('Giảm mỡ');

    await reachEnd();

    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(screen.getByText('Giảm mỡ')).toBeTruthy();
    await fireEvent.press(button('Thử lại'));

    expect(await screen.findByText('Duy trì')).toBeTruthy();
    expect(screen.queryByText(NETWORK_MESSAGE)).toBeNull();
    expect(mockedListGoals).toHaveBeenCalledTimes(3);
    expect(mockedListGoals.mock.calls[2]?.[0]).toStrictEqual({ limit: 20, cursor: 'c-2' });
  });

  it('FEAUTH-19 nhãn trạng thái: active, achieved, abandoned', () => {
    expect(goalStatusLabel('active')).toBe('Đang thực hiện');
    expect(goalStatusLabel('achieved')).toBe('Đã đạt');
    expect(goalStatusLabel('abandoned')).toBe('Đã bỏ');
  });
});

describe('GoalsScreen: đóng mục tiêu', () => {
  async function renderWithActiveGoal() {
    await renderGoals();
    await screen.findByText('Giảm mỡ');
  }

  it('FEAUTH-22 (a) "Đánh dấu đã đạt": gửi status achieved, tải lại danh sách, hết nút đóng', async () => {
    mockedListGoals.mockResolvedValueOnce(page([G1, G2])).mockResolvedValueOnce(page([G1_ACHIEVED, G2]));
    mockedUpdateGoal.mockResolvedValue(G1_ACHIEVED);
    await renderWithActiveGoal();

    await fireEvent.press(button(ACHIEVE));

    await waitFor(() => expect(screen.queryByRole('button', { name: ACHIEVE })).toBeNull());
    expect(mockedUpdateGoal).toHaveBeenCalledTimes(1);
    expect(mockedUpdateGoal).toHaveBeenCalledWith('g-1', { status: 'achieved' });
    expect(mockedListGoals).toHaveBeenCalledTimes(2);
    expect(mockedListGoals.mock.calls[1]?.[0]).toStrictEqual({ limit: 20 });
    expect(screen.queryByRole('button', { name: ABANDON })).toBeNull();
    expect(goalCard('g-1').getByText('Đã đạt')).toBeTruthy();
  });

  it('FEAUTH-22 (b) "Bỏ mục tiêu": gửi status abandoned rồi tải lại danh sách', async () => {
    mockedListGoals.mockResolvedValueOnce(page([G1, G2])).mockResolvedValueOnce(page([G1_ABANDONED, G2]));
    mockedUpdateGoal.mockResolvedValue(G1_ABANDONED);
    await renderWithActiveGoal();

    await fireEvent.press(button(ABANDON));

    await waitFor(() => expect(goalCard('g-1').getByText('Đã bỏ')).toBeTruthy());
    expect(mockedUpdateGoal).toHaveBeenCalledTimes(1);
    expect(mockedUpdateGoal).toHaveBeenCalledWith('g-1', { status: 'abandoned' });
    expect(mockedListGoals).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('button', { name: ACHIEVE })).toBeNull();
  });

  it('FEAUTH-22 (c) 404 goal_not_found: hiện "Mục tiêu không còn tồn tại" và tải lại danh sách', async () => {
    mockedListGoals.mockResolvedValueOnce(page([G1, G2])).mockResolvedValueOnce(page([G2]));
    mockedUpdateGoal.mockRejectedValue(apiError(404, 'goal_not_found'));
    await renderWithActiveGoal();

    await fireEvent.press(button(ACHIEVE));

    expect(await screen.findByText(GOAL_NOT_FOUND_MESSAGE)).toBeTruthy();
    await waitFor(() => expect(mockedListGoals).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText('Giảm mỡ')).toBeNull());
    expect(screen.queryByText(/Thông điệp server/)).toBeNull();
    expect(mockedUpdateGoal).toHaveBeenCalledWith('g-1', { status: 'achieved' });
  });

  it.each([
    { name: 'lỗi mạng', error: networkError(), message: NETWORK_MESSAGE },
    { name: '403 permission_denied', error: apiError(403, 'permission_denied'), message: PERMISSION_MESSAGE },
  ])('FEAUTH-22 $name: hiện thông điệp, không tải lại danh sách, vẫn bấm lại được', async ({ error, message }) => {
    mockedListGoals.mockResolvedValue(page([G1, G2]));
    mockedUpdateGoal.mockRejectedValueOnce(error).mockResolvedValueOnce(G1_ABANDONED);
    await renderWithActiveGoal();

    await fireEvent.press(button(ABANDON));

    expect(await screen.findByText(message)).toBeTruthy();
    expect(screen.queryByText(/Thông điệp server/)).toBeNull();
    await flushPromises();
    expect(mockedListGoals).toHaveBeenCalledTimes(1);
    expect(goalCard('g-1').getByText('Đang thực hiện')).toBeTruthy();

    await fireEvent.press(button(ABANDON));
    await waitFor(() => expect(mockedUpdateGoal).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText(message)).toBeNull());
  });

  it('FEAUTH-22 bấm hai lần khi updateGoal còn chờ thì chỉ gửi một lần', async () => {
    const pending = deferred<UserGoal>();
    mockedListGoals.mockResolvedValueOnce(page([G1, G2])).mockResolvedValueOnce(page([G1_ACHIEVED, G2]));
    mockedUpdateGoal.mockReturnValue(pending.promise);
    await renderWithActiveGoal();

    // Lần bấm đầu treo tới khi `updateGoal` resolve nên không await.
    const firstPress = fireEvent.press(button(ACHIEVE));
    await waitFor(() => expect(mockedUpdateGoal).toHaveBeenCalledTimes(1));
    await fireEvent.press(button(ACHIEVE));
    await fireEvent.press(button(ABANDON));
    await act(async () => {
      pending.resolve(G1_ACHIEVED);
      await firstPress;
    });

    await waitFor(() => expect(screen.queryByRole('button', { name: ACHIEVE })).toBeNull());
    expect(mockedUpdateGoal).toHaveBeenCalledTimes(1);
    expect(mockedUpdateGoal).toHaveBeenCalledWith('g-1', { status: 'achieved' });
  });
});
