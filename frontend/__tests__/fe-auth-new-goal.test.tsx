import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react-native';
import { AxiosError, AxiosHeaders } from 'axios';
import { router } from 'expo-router';

import { toTargetWeightKg, validateNewGoal, type NewGoalInput } from '@/screens/profile/new-goal-form';
import NewGoalScreen from '@/screens/profile/NewGoalScreen';
import type { ApiErrorDetail } from '@/services/api/errors';
import { getMe } from '@/services/auth';
import { createGoal, listGoalTypes } from '@/services/profile';
import { useSession } from '@/store/session';
import type { Me } from '@/types/auth';
import type { Page } from '@/types/page';
import type { GoalType, UserGoal } from '@/types/profile';

jest.mock('@/services/auth');
jest.mock('@/services/profile');
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
  useLocalSearchParams: jest.fn(() => ({})),
  Redirect: () => null,
}));

const mockedGetMe = jest.mocked(getMe);
const mockedListGoalTypes = jest.mocked(listGoalTypes);
const mockedCreateGoal = jest.mocked(createGoal);

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

// 5 loại mục tiêu: `code`, `name`, `description` chép từ database/postgresql/seeds/02_reference.sql.
const GOAL_TYPES: GoalType[] = [
  { id: 1, code: 'lose_fat', name: 'Giảm mỡ', description: 'Giảm tỷ lệ mỡ, giữ khối cơ.' },
  { id: 2, code: 'gain_muscle', name: 'Tăng cơ', description: 'Tăng khối lượng cơ (bulking).' },
  { id: 3, code: 'recomposition', name: 'Tái cấu trúc cơ thể', description: 'Đồng thời giảm mỡ và tăng cơ.' },
  { id: 4, code: 'strength', name: 'Tăng sức mạnh', description: 'Tối đa hoá sức mạnh các bài chính.' },
  { id: 5, code: 'maintain', name: 'Duy trì', description: 'Giữ vóc dáng và sức khoẻ hiện tại.' },
];
const GOAL_TYPES_PAGE: Page<GoalType> = { data: GOAL_TYPES, pagination: { next_cursor: null, has_more: false } };
const CREATED_GOAL: UserGoal = {
  id: '0b6c2f0e-6a43-4f7e-9b1f-3d2a1c5e7f90',
  goal_type: { id: 2, code: 'gain_muscle', name: 'Tăng cơ' },
  target_weight_kg: 70.5,
  target_body_fat_pct: null,
  start_date: '2026-11-28',
  target_date: '2027-03-01',
  status: 'active',
  closed_at: null,
  created_at: '2026-11-28T04:00:00Z',
  updated_at: '2026-11-28T04:00:00Z',
};

// Chuỗi kỳ vọng chép nguyên từ spec fe-auth §2.4 (không dùng lại hằng của code để bắt lỗi chính tả).
const GOAL_TYPE_REQUIRED = 'Vui lòng chọn loại mục tiêu';
const WEIGHT_RANGE = 'Cân nặng mục tiêu phải từ 20 đến 400 kg';
const DATE_FORMAT = 'Ngày phải có dạng dd/mm/yyyy';
const ACTIVE_GOAL_EXISTS = 'Bạn đang có một mục tiêu chưa hoàn thành. Hãy đóng mục tiêu cũ trước.';
const NETWORK_MESSAGE = 'Không kết nối được máy chủ';
const PERMISSION_MESSAGE = 'Bạn không có quyền thực hiện thao tác này';
const WEIGHT = 'Cân nặng mục tiêu';
const TARGET_DATE = 'Ngày đạt mục tiêu';
const SAVE = 'Lưu mục tiêu';
// `testID` của nhóm Chip loại mục tiêu, cùng quy ước `field-<nhãn>` của `TextField`.
const GOAL_TYPE_GROUP = 'Loại mục tiêu';

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

const queryClients: QueryClient[] = [];

async function renderNewGoal(): Promise<QueryClient> {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClients.push(client);
  await render(
    <QueryClientProvider client={client}>
      <NewGoalScreen />
    </QueryClientProvider>,
  );
  await screen.findByRole('button', { name: 'Giảm mỡ' });
  return client;
}

function button(name: string) {
  return screen.getByRole('button', { name });
}

function fieldOf(label: string) {
  return within(screen.getByTestId(`field-${label}`));
}

type GoalFormInput = { goalType?: string; weight?: string; date?: string };

async function fillGoal({ goalType, weight, date }: GoalFormInput) {
  if (goalType) await fireEvent.press(button(goalType));
  if (weight !== undefined) await fireEvent.changeText(screen.getByLabelText(WEIGHT), weight);
  if (date !== undefined) await fireEvent.changeText(screen.getByLabelText(TARGET_DATE), date);
}

beforeEach(() => {
  jest.clearAllMocks();
  // `useMe` tắt khi `signedOut` nên màn dùng `useMe` cần phiên `signedIn` (spec fe-auth §5).
  useSession.setState({ status: 'signedIn', user: SESSION_USER });
  mockedGetMe.mockResolvedValue(DEMO_ME);
  mockedListGoalTypes.mockResolvedValue(GOAL_TYPES_PAGE);
});

// Gỡ màn rồi xoá cache: nếu không, timer `gcTime` (mặc định 5 phút) của React Query giữ tiến trình jest không thoát.
afterEach(async () => {
  await cleanup();
  for (const client of queryClients.splice(0)) client.clear();
});

describe('NewGoalScreen: đặt mục tiêu thành công', () => {
  it('FEAUTH-20 hiện đủ 5 Chip loại mục tiêu từ API, chưa chọn Chip nào; ô cân nặng có đơn vị kg', async () => {
    await renderNewGoal();

    expect(screen.getByRole('header', { name: 'Đặt mục tiêu' })).toBeTruthy();
    for (const type of GOAL_TYPES) expect(button(type.name)).not.toBeSelected();
    expect(within(screen.getByTestId(`field-${GOAL_TYPE_GROUP}`)).getAllByRole('button')).toHaveLength(5);
    expect(fieldOf(WEIGHT).getByText('kg')).toBeTruthy();
    expect(screen.getByLabelText(TARGET_DATE).props.placeholder).toBe('dd/mm/yyyy');
    expect(mockedListGoalTypes).toHaveBeenCalledTimes(1);
  });

  it.each([
    {
      name: '(a) metric: "Tăng cơ", "70,5", "01/03/2027"',
      me: DEMO_ME,
      input: { goalType: 'Tăng cơ', weight: '70,5', date: '01/03/2027' },
      body: { goal_type_id: 2, target_weight_kg: 70.5, target_date: '2027-03-01' },
    },
    {
      name: '(b) imperial: "Tăng cơ", "154" lb',
      me: OTHER_ME,
      input: { goalType: 'Tăng cơ', weight: '154' },
      body: { goal_type_id: 2, target_weight_kg: 69.85 },
    },
    {
      name: '(c) metric: chỉ chọn "Duy trì"',
      me: DEMO_ME,
      input: { goalType: 'Duy trì' },
      body: { goal_type_id: 5 },
    },
  ])('FEAUTH-20 $name: gửi đúng body, invalidate ["body","goals"] rồi quay lại', async ({ me, input, body }) => {
    mockedGetMe.mockResolvedValue(me);
    mockedCreateGoal.mockResolvedValue(CREATED_GOAL);
    const client = await renderNewGoal();
    const invalidateSpy = jest.spyOn(client, 'invalidateQueries');

    await fillGoal(input);
    await fireEvent.press(button(SAVE));

    await waitFor(() => expect(router.back).toHaveBeenCalledTimes(1));
    expect(mockedCreateGoal).toHaveBeenCalledTimes(1);
    expect(mockedCreateGoal.mock.calls[0]?.[0]).toStrictEqual(body);
    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ['body', 'goals'] }));
    expect(mockedCreateGoal.mock.invocationCallOrder[0]).toBeLessThan(
      invalidateSpy.mock.invocationCallOrder[0] ?? 0,
    );
  });

  it('FEAUTH-20 imperial: ô cân nặng có đơn vị lb', async () => {
    mockedGetMe.mockResolvedValue(OTHER_ME);
    await renderNewGoal();

    expect(fieldOf(WEIGHT).getByText('lb')).toBeTruthy();
    expect(fieldOf(WEIGHT).queryByText('kg')).toBeNull();
  });

  it('FEAUTH-20 bấm Chip khác thì đổi lựa chọn, chỉ một Chip được chọn', async () => {
    mockedCreateGoal.mockResolvedValue(CREATED_GOAL);
    await renderNewGoal();

    await fireEvent.press(button('Giảm mỡ'));
    expect(button('Giảm mỡ')).toBeSelected();
    await fireEvent.press(button('Tăng sức mạnh'));

    expect(button('Tăng sức mạnh')).toBeSelected();
    expect(button('Giảm mỡ')).not.toBeSelected();
    await fireEvent.press(button(SAVE));
    await waitFor(() => expect(router.back).toHaveBeenCalledTimes(1));
    expect(mockedCreateGoal.mock.calls[0]?.[0]).toStrictEqual({ goal_type_id: 4 });
  });

  it('FEAUTH-20 bấm "Lưu mục tiêu" hai lần khi createGoal còn chờ thì chỉ gửi một lần', async () => {
    const pending = deferred<UserGoal>();
    mockedCreateGoal.mockReturnValue(pending.promise);
    await renderNewGoal();
    await fillGoal({ goalType: 'Duy trì' });

    // Lần bấm đầu treo tới khi `createGoal` resolve nên không await.
    const firstPress = fireEvent.press(button(SAVE));
    await waitFor(() => expect(mockedCreateGoal).toHaveBeenCalledTimes(1));
    await fireEvent.press(button(SAVE));
    await act(async () => {
      pending.resolve(CREATED_GOAL);
      await firstPress;
    });

    expect(mockedCreateGoal).toHaveBeenCalledTimes(1);
    expect(router.back).toHaveBeenCalledTimes(1);
  });

  it('FEAUTH-20 nút "Quay lại" gọi router.back(), không gọi createGoal', async () => {
    await renderNewGoal();

    await fireEvent.press(button('Quay lại'));

    expect(router.back).toHaveBeenCalledTimes(1);
    expect(mockedCreateGoal).not.toHaveBeenCalled();
  });
});

describe('NewGoalScreen: lỗi', () => {
  function expectNotSaved() {
    expect(mockedCreateGoal).not.toHaveBeenCalled();
    expect(router.back).not.toHaveBeenCalled();
  }

  it('FEAUTH-21 client: chưa chọn loại thì báo dưới nhóm Chip, không gọi createGoal', async () => {
    await renderNewGoal();

    await fireEvent.press(button(SAVE));

    expect(within(screen.getByTestId(`field-${GOAL_TYPE_GROUP}`)).getByText(GOAL_TYPE_REQUIRED)).toBeTruthy();
    expect(screen.getAllByText(GOAL_TYPE_REQUIRED)).toHaveLength(1);
    expectNotSaved();
  });

  it.each([
    { name: 'Cân nặng "15"', input: { weight: '15' }, label: WEIGHT, message: WEIGHT_RANGE },
    { name: 'Cân nặng "abc"', input: { weight: 'abc' }, label: WEIGHT, message: WEIGHT_RANGE },
    { name: 'Cân nặng "400,01"', input: { weight: '400,01' }, label: WEIGHT, message: WEIGHT_RANGE },
    { name: 'Ngày "30/02/2027"', input: { date: '30/02/2027' }, label: TARGET_DATE, message: DATE_FORMAT },
    { name: 'Ngày "1/3/27"', input: { date: '1/3/27' }, label: TARGET_DATE, message: DATE_FORMAT },
  ])('FEAUTH-21 client $name: báo dưới đúng ô, không gọi createGoal', async ({ input, label, message }) => {
    await renderNewGoal();

    await fillGoal({ goalType: 'Tăng cơ', ...input });
    await fireEvent.press(button(SAVE));

    expect(fieldOf(label).getByText(message)).toBeTruthy();
    expect(screen.getAllByText(message)).toHaveLength(1);
    expectNotSaved();
  });

  it('FEAUTH-21 client: báo mọi lỗi cùng lúc', async () => {
    await renderNewGoal();

    await fillGoal({ weight: '15', date: '30/02/2027' });
    await fireEvent.press(button(SAVE));

    expect(within(screen.getByTestId(`field-${GOAL_TYPE_GROUP}`)).getByText(GOAL_TYPE_REQUIRED)).toBeTruthy();
    expect(fieldOf(WEIGHT).getByText(WEIGHT_RANGE)).toBeTruthy();
    expect(fieldOf(TARGET_DATE).getByText(DATE_FORMAT)).toBeTruthy();
    expectNotSaved();
  });

  it('FEAUTH-21 server 409 active_goal_already_exists: hiện thông điệp chung, bấm lại được', async () => {
    mockedCreateGoal.mockRejectedValue(apiError(409, 'active_goal_already_exists'));
    await renderNewGoal();

    await fillGoal({ goalType: 'Duy trì' });
    await fireEvent.press(button(SAVE));

    expect(await screen.findByText(ACTIVE_GOAL_EXISTS)).toBeTruthy();
    expect(fieldOf(WEIGHT).queryByText(ACTIVE_GOAL_EXISTS)).toBeNull();
    expect(screen.queryByText(/Thông điệp server/)).toBeNull();
    expect(router.back).not.toHaveBeenCalled();

    await fireEvent.press(button(SAVE));
    await waitFor(() => expect(mockedCreateGoal).toHaveBeenCalledTimes(2));
    expect(router.back).not.toHaveBeenCalled();
  });

  it('FEAUTH-21 server 422 validation_error target_date: hiện dưới ô Ngày đạt mục tiêu', async () => {
    mockedCreateGoal.mockRejectedValue(
      apiError(422, 'validation_error', [
        { field: 'target_date', message: 'target_date phải sau start_date', code: 'invalid_reference' },
      ]),
    );
    await renderNewGoal();

    await fillGoal({ goalType: 'Giảm mỡ', weight: '66', date: '01/01/2020' });
    await fireEvent.press(button(SAVE));

    expect(await fieldOf(TARGET_DATE).findByText('target_date phải sau start_date')).toBeTruthy();
    expect(screen.getAllByText('target_date phải sau start_date')).toHaveLength(1);
    expect(screen.queryByText(/Thông điệp server/)).toBeNull();
    expect(mockedCreateGoal.mock.calls[0]?.[0]).toStrictEqual({
      goal_type_id: 1,
      target_weight_kg: 66,
      target_date: '2020-01-01',
    });
    expect(router.back).not.toHaveBeenCalled();
  });

  it('FEAUTH-21 server 422 validation_error target_weight_kg và goal_type_id: hiện dưới ô Cân nặng và nhóm Chip', async () => {
    mockedCreateGoal.mockRejectedValue(
      apiError(422, 'validation_error', [
        { field: 'target_weight_kg', message: 'Cân nặng sai', code: 'value_error' },
        { field: 'goal_type_id', message: 'Loại mục tiêu sai', code: 'invalid_reference' },
      ]),
    );
    await renderNewGoal();

    await fillGoal({ goalType: 'Giảm mỡ', weight: '66' });
    await fireEvent.press(button(SAVE));

    expect(await fieldOf(WEIGHT).findByText('Cân nặng sai')).toBeTruthy();
    expect(within(screen.getByTestId(`field-${GOAL_TYPE_GROUP}`)).getByText('Loại mục tiêu sai')).toBeTruthy();
    expect(router.back).not.toHaveBeenCalled();
  });

  it.each([
    { name: 'lỗi mạng', error: networkError(), message: NETWORK_MESSAGE },
    { name: '403 permission_denied', error: apiError(403, 'permission_denied'), message: PERMISSION_MESSAGE },
  ])('FEAUTH-21 server $name: hiện thông điệp, không quay lại', async ({ error, message }) => {
    mockedCreateGoal.mockRejectedValue(error);
    await renderNewGoal();

    await fillGoal({ goalType: 'Duy trì' });
    await fireEvent.press(button(SAVE));

    expect(await screen.findByText(message)).toBeTruthy();
    expect(screen.queryByText(/Thông điệp server/)).toBeNull();
    expect(router.back).not.toHaveBeenCalled();
  });

  it('FEAUTH-21 listGoalTypes lỗi mạng: báo lỗi có "Thử lại"; bấm thì hiện 5 Chip', async () => {
    mockedListGoalTypes.mockReset();
    mockedListGoalTypes.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(GOAL_TYPES_PAGE);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClients.push(client);
    await render(
      <QueryClientProvider client={client}>
        <NewGoalScreen />
      </QueryClientProvider>,
    );

    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(screen.queryByRole('button', { name: SAVE })).toBeNull();

    await fireEvent.press(button('Thử lại'));

    for (const type of GOAL_TYPES) expect(await screen.findByRole('button', { name: type.name })).toBeTruthy();
    expect(screen.queryByText(NETWORK_MESSAGE)).toBeNull();
    expect(mockedListGoalTypes).toHaveBeenCalledTimes(2);
    expectNotSaved();
  });

  it('FEAUTH-21 listGoalTypes đang tải: hiện "Đang tải...", chưa có form; danh mục rỗng: báo "Chưa có loại mục tiêu"', async () => {
    mockedListGoalTypes.mockReturnValue(new Promise<Page<GoalType>>(() => undefined));
    const loadingClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClients.push(loadingClient);
    await render(
      <QueryClientProvider client={loadingClient}>
        <NewGoalScreen />
      </QueryClientProvider>,
    );
    await waitFor(() => expect(mockedListGoalTypes).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText('Đang tải...')).toBeTruthy();
    expect(screen.queryByRole('button', { name: SAVE })).toBeNull();
    await cleanup();

    mockedListGoalTypes.mockResolvedValue({ data: [], pagination: { next_cursor: null, has_more: false } });
    const emptyClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClients.push(emptyClient);
    await render(
      <QueryClientProvider client={emptyClient}>
        <NewGoalScreen />
      </QueryClientProvider>,
    );
    expect(await screen.findByText('Chưa có loại mục tiêu')).toBeTruthy();
    expect(screen.queryByRole('button', { name: SAVE })).toBeNull();
  });
});

describe('new-goal-form: hàm thuần', () => {
  const EMPTY: NewGoalInput = { goal_type_id: null, target_weight: '', target_date: '' };

  it('FEAUTH-20 toTargetWeightKg: đổi lb sang kg, làm tròn 2 chữ số; chuỗi không phải số trả null', () => {
    expect(toTargetWeightKg('70,5', 'metric')).toBe(70.5);
    expect(toTargetWeightKg('70.555', 'metric')).toBe(70.56);
    expect(toTargetWeightKg('154', 'imperial')).toBe(69.85);
    expect(toTargetWeightKg('abc', 'metric')).toBeNull();
    expect(toTargetWeightKg('', 'imperial')).toBeNull();
  });

  it('FEAUTH-20 validateNewGoal: ô trống không gửi key, giá trị được trim', () => {
    expect(validateNewGoal({ ...EMPTY, goal_type_id: 5 }, 'metric')).toStrictEqual({
      errors: { fields: {}, form: null },
      body: { goal_type_id: 5 },
    });
    expect(
      validateNewGoal({ goal_type_id: 1, target_weight: ' 66 ', target_date: ' 01/03/2027 ' }, 'metric').body,
    ).toStrictEqual({ goal_type_id: 1, target_weight_kg: 66, target_date: '2027-03-01' });
    expect(validateNewGoal({ ...EMPTY, goal_type_id: 1, target_weight: '   ' }, 'metric').body).toStrictEqual({
      goal_type_id: 1,
    });
  });

  it.each([
    { weight: '20', unit: 'metric' as const, kg: 20 },
    { weight: '400', unit: 'metric' as const, kg: 400 },
    // 44,09 lb = 19,9989 kg, làm tròn 2 chữ số thành 20,00 kg (đúng giá trị sẽ gửi) nên hợp lệ.
    { weight: '44,09', unit: 'imperial' as const, kg: 20 },
  ])('FEAUTH-21 validateNewGoal biên hợp lệ: $weight ($unit) → $kg kg', ({ weight, unit, kg }) => {
    const result = validateNewGoal({ ...EMPTY, goal_type_id: 1, target_weight: weight }, unit);

    expect(result.errors.fields).toStrictEqual({});
    expect(result.body).toStrictEqual({ goal_type_id: 1, target_weight_kg: kg });
  });

  it.each([
    { weight: '19,99', unit: 'metric' as const },
    { weight: '400,01', unit: 'metric' as const },
    { weight: '-66', unit: 'metric' as const },
    { weight: '44', unit: 'imperial' as const },
    { weight: '1.234,5', unit: 'metric' as const },
  ])('FEAUTH-21 validateNewGoal biên lỗi: $weight ($unit) báo lỗi cân nặng', ({ weight, unit }) => {
    const result = validateNewGoal({ ...EMPTY, goal_type_id: 1, target_weight: weight }, unit);

    expect(result.errors.fields).toStrictEqual({ target_weight_kg: WEIGHT_RANGE });
    expect(result.body).toBeNull();
  });

  it('FEAUTH-21 validateNewGoal: thiếu loại và sai ngày báo cùng lúc, không có body', () => {
    const result = validateNewGoal({ goal_type_id: null, target_weight: '', target_date: '29/02/2027' }, 'metric');

    expect(result.errors).toStrictEqual({
      fields: { goal_type_id: GOAL_TYPE_REQUIRED, target_date: DATE_FORMAT },
      form: null,
    });
    expect(result.body).toBeNull();
  });
});
