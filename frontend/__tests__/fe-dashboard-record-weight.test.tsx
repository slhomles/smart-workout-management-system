import { act, fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';

import RecordWeightScreen from '@/screens/dashboard/RecordWeightScreen';
import { getMe } from '@/services/auth';
import { createMeasurement } from '@/services/dashboard';
import { useSession } from '@/store/session';
import type { BodyMeasurement } from '@/types/dashboard';

import {
  apiError,
  cleanupClients,
  deferred,
  DEMO_ME,
  flushPromises,
  networkError,
  OTHER_ME,
  renderWithClient,
  SESSION_USER,
} from '../test-utils/fe-dashboard-fixtures';

jest.mock('@/services/auth');
jest.mock('@/services/dashboard');
jest.mock('expo-router', () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn() },
  useLocalSearchParams: jest.fn(() => ({})),
  Redirect: () => null,
}));

// Lần render đầu của suite nạp lười module React Native; khi cổng chạy cả suite song song với --coverage,
// test đầu có thể vượt timeout 5s mặc định. jest.config.js là file core nên nâng timeout tại đây.
jest.setTimeout(20_000);

const mockedGetMe = jest.mocked(getMe);
const mockedCreateMeasurement = jest.mocked(createMeasurement);

// Chuỗi kỳ vọng chép nguyên từ spec fe-dashboard §2.4, §5 (không dùng lại hằng của code để bắt lỗi chính tả).
const WEIGHT = 'Cân nặng';
const BODY_FAT = 'Tỷ lệ mỡ (%)';
const SAVE = 'Lưu';
const WEIGHT_RANGE = 'Cân nặng phải từ 20 đến 400 kg';
const BODY_FAT_RANGE = 'Tỷ lệ mỡ phải từ 2 đến 70%';
const MEASUREMENT_EXISTS = 'Đã có lần đo tại thời điểm này';
const NETWORK_MESSAGE = 'Không kết nối được máy chủ';
const PERMISSION_MESSAGE = 'Bạn không có quyền thực hiện thao tác này';

// Lần đo vừa tạo của persona demo (giá trị chỉ số theo views/01_body.sql với chiều cao 172 cm).
const CREATED_MEASUREMENT: BodyMeasurement = {
  id: '6a1f3c2e-8b4d-4e5f-9a0b-1c2d3e4f5a6b',
  measured_at: '2026-11-29T02:00:00Z',
  weight_kg: 70.5,
  body_fat_pct: 18.2,
  muscle_mass_kg: null,
  source: 'manual',
  note: null,
  circumferences: [],
  metrics: {
    age_years: 23,
    bmi: 23.8,
    bmi_category: 'overweight',
    lean_body_mass_kg: 57.67,
    bmr_kcal: 1671,
    bmr_katch_mcardle_kcal: 1616,
    tdee_kcal: 2590,
    activity_level_code: 'moderate',
  },
  created_at: '2026-11-29T02:00:00Z',
  updated_at: '2026-11-29T02:00:00Z',
};

async function renderRecordWeight() {
  const client = await renderWithClient(<RecordWeightScreen />);
  await screen.findByLabelText(WEIGHT);
  return client;
}

function button(name: string) {
  return screen.getByRole('button', { name });
}

function fieldOf(label: string) {
  return within(screen.getByTestId(`field-${label}`));
}

async function fillAndSave(weight: string, bodyFat?: string) {
  await fireEvent.changeText(screen.getByLabelText(WEIGHT), weight);
  if (bodyFat !== undefined) await fireEvent.changeText(screen.getByLabelText(BODY_FAT), bodyFat);
  await fireEvent.press(button(SAVE));
}

beforeEach(() => {
  jest.clearAllMocks();
  // `useMe` tắt khi `signedOut` nên màn dùng `useMe` cần phiên `signedIn` (spec §5 "Quy ước chung").
  useSession.setState({ status: 'signedIn', user: SESSION_USER });
  mockedGetMe.mockResolvedValue(DEMO_ME);
  mockedCreateMeasurement.mockResolvedValue(CREATED_MEASUREMENT);
});

afterEach(cleanupClients);

describe('RecordWeightScreen: ghi cân nặng thành công', () => {
  it.each([
    {
      name: '(a) metric: "70,5" và "18,2"',
      me: DEMO_ME,
      weight: '70,5',
      bodyFat: '18,2',
      unit: 'kg',
      otherUnit: 'lb',
      body: { weight_kg: 70.5, body_fat_pct: 18.2 },
    },
    {
      name: '(b) imperial: "154" lb, % mỡ trống',
      me: OTHER_ME,
      weight: '154',
      bodyFat: undefined,
      unit: 'lb',
      otherUnit: 'kg',
      body: { weight_kg: 69.85 },
    },
    {
      name: '(c) metric: "70.456" làm tròn 2 chữ số',
      me: DEMO_ME,
      weight: '70.456',
      bodyFat: undefined,
      unit: 'kg',
      otherUnit: 'lb',
      body: { weight_kg: 70.46 },
    },
  ])('FEDASH-19 $name: gửi đúng body, invalidate ["dashboard"] rồi quay lại', async (testCase) => {
    mockedGetMe.mockResolvedValue(testCase.me);
    const client = await renderRecordWeight();
    const invalidateSpy = jest.spyOn(client, 'invalidateQueries');

    expect(screen.getByRole('header', { name: 'Ghi cân nặng' })).toBeTruthy();
    expect(fieldOf(WEIGHT).getByText(testCase.unit)).toBeTruthy();
    expect(fieldOf(WEIGHT).queryByText(testCase.otherUnit)).toBeNull();
    await fillAndSave(testCase.weight, testCase.bodyFat);

    await waitFor(() => expect(router.back).toHaveBeenCalledTimes(1));
    expect(mockedCreateMeasurement).toHaveBeenCalledTimes(1);
    expect(mockedCreateMeasurement).toHaveBeenCalledWith(testCase.body);
    const sentBody = mockedCreateMeasurement.mock.calls[0]?.[0];
    expect(sentBody).toStrictEqual(testCase.body);
    expect(sentBody).not.toHaveProperty('measured_at');
    if (testCase.bodyFat === undefined) expect(sentBody).not.toHaveProperty('body_fat_pct');
    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ['dashboard'] }));
    expect(mockedCreateMeasurement.mock.invocationCallOrder[0]).toBeLessThan(
      invalidateSpy.mock.invocationCallOrder[0] ?? 0,
    );
  });

  it('FEDASH-19 bấm "Lưu" hai lần khi createMeasurement còn chờ thì chỉ gửi một lần', async () => {
    const pending = deferred<BodyMeasurement>();
    mockedCreateMeasurement.mockReturnValue(pending.promise);
    await renderRecordWeight();

    await fireEvent.changeText(screen.getByLabelText(WEIGHT), '70,5');
    // Lần bấm đầu treo tới khi `createMeasurement` resolve nên không await.
    const firstPress = fireEvent.press(button(SAVE));
    await waitFor(() => expect(mockedCreateMeasurement).toHaveBeenCalledTimes(1));
    await fireEvent.press(button(SAVE));
    await act(async () => {
      pending.resolve(CREATED_MEASUREMENT);
      await firstPress;
    });

    expect(mockedCreateMeasurement).toHaveBeenCalledTimes(1);
    expect(router.back).toHaveBeenCalledTimes(1);
  });

  it('FEDASH-19 nút "Quay lại" gọi router.back(), không gọi createMeasurement', async () => {
    await renderRecordWeight();

    await fireEvent.press(button('Quay lại'));

    expect(router.back).toHaveBeenCalledTimes(1);
    expect(mockedCreateMeasurement).not.toHaveBeenCalled();
  });
});

describe('RecordWeightScreen: lỗi', () => {
  it.each([
    { name: 'Cân nặng "15"', weight: '15', bodyFat: undefined, label: WEIGHT, message: WEIGHT_RANGE },
    { name: 'Cân nặng "abc"', weight: 'abc', bodyFat: undefined, label: WEIGHT, message: WEIGHT_RANGE },
    { name: 'Cân nặng ""', weight: '', bodyFat: undefined, label: WEIGHT, message: WEIGHT_RANGE },
    { name: '"70" + Tỷ lệ mỡ "1"', weight: '70', bodyFat: '1', label: BODY_FAT, message: BODY_FAT_RANGE },
    { name: '"70" + Tỷ lệ mỡ "71"', weight: '70', bodyFat: '71', label: BODY_FAT, message: BODY_FAT_RANGE },
  ])('FEDASH-20 client $name: báo dưới đúng ô, không gọi createMeasurement', async ({ weight, bodyFat, label, message }) => {
    await renderRecordWeight();

    await fillAndSave(weight, bodyFat);

    expect(fieldOf(label).getByText(message)).toBeTruthy();
    expect(screen.getAllByText(message)).toHaveLength(1);
    await flushPromises();
    expect(mockedCreateMeasurement).not.toHaveBeenCalled();
    expect(router.back).not.toHaveBeenCalled();
  });

  it('FEDASH-20 server 409 measurement_already_exists: hiện thông điệp chung, bấm lại được', async () => {
    mockedCreateMeasurement.mockRejectedValue(apiError(409, 'measurement_already_exists'));
    await renderRecordWeight();

    await fillAndSave('70,5');

    expect(await screen.findByText(MEASUREMENT_EXISTS)).toBeTruthy();
    expect(fieldOf(WEIGHT).queryByText(MEASUREMENT_EXISTS)).toBeNull();
    expect(screen.queryByText(/Thông điệp server/)).toBeNull();
    expect(router.back).not.toHaveBeenCalled();

    await fireEvent.press(button(SAVE));
    await waitFor(() => expect(mockedCreateMeasurement).toHaveBeenCalledTimes(2));
    expect(router.back).not.toHaveBeenCalled();
  });

  it('FEDASH-20 server 422 validation_error weight_kg: hiện ngay dưới ô Cân nặng', async () => {
    const details = [{ field: 'weight_kg', message: 'Cân nặng không hợp lệ', code: 'value_error' }];
    mockedCreateMeasurement.mockRejectedValue(apiError(422, 'validation_error', details));
    await renderRecordWeight();

    await fillAndSave('70,5', '18,2');

    expect(await fieldOf(WEIGHT).findByText('Cân nặng không hợp lệ')).toBeTruthy();
    expect(screen.getAllByText('Cân nặng không hợp lệ')).toHaveLength(1);
    expect(fieldOf(BODY_FAT).queryByText('Cân nặng không hợp lệ')).toBeNull();
    expect(router.back).not.toHaveBeenCalled();
  });

  it('FEDASH-20 server 422 validation_error body_fat_pct: hiện ngay dưới ô Tỷ lệ mỡ', async () => {
    const details = [{ field: 'body_fat_pct', message: 'Tỷ lệ mỡ không hợp lệ', code: 'value_error' }];
    mockedCreateMeasurement.mockRejectedValue(apiError(422, 'validation_error', details));
    await renderRecordWeight();

    await fillAndSave('70,5', '18,2');

    expect(await fieldOf(BODY_FAT).findByText('Tỷ lệ mỡ không hợp lệ')).toBeTruthy();
    expect(router.back).not.toHaveBeenCalled();
  });

  it.each([
    { name: 'lỗi mạng', error: networkError(), message: NETWORK_MESSAGE },
    { name: '403 permission_denied', error: apiError(403, 'permission_denied'), message: PERMISSION_MESSAGE },
  ])('FEDASH-20 server $name: hiện thông điệp chung, không quay lại', async ({ error, message }) => {
    mockedCreateMeasurement.mockRejectedValue(error);
    await renderRecordWeight();

    await fillAndSave('70,5');

    expect(await screen.findByText(message)).toBeTruthy();
    expect(fieldOf(WEIGHT).queryByText(message)).toBeNull();
    expect(mockedCreateMeasurement).toHaveBeenCalledTimes(1);
    expect(router.back).not.toHaveBeenCalled();
  });
});
