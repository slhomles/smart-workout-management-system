import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';

import HeightScreen from '@/screens/dashboard/HeightScreen';
import { getBodyProfile, replaceBodyProfile } from '@/services/dashboard';
import { useSession } from '@/store/session';
import type { BodyProfile } from '@/types/dashboard';

import {
  apiError,
  cleanupClients,
  flushPromises,
  networkError,
  neverResolves,
  PROFILE_DEMO,
  PROFILE_NEWBIE,
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

const mockedGetBodyProfile = jest.mocked(getBodyProfile);
const mockedReplaceBodyProfile = jest.mocked(replaceBodyProfile);

// Chuỗi kỳ vọng chép nguyên từ spec fe-dashboard §2.4, §5 (không dùng lại hằng của code để bắt lỗi chính tả).
const HEIGHT = 'Chiều cao (cm)';
const SAVE = 'Lưu';
const HEIGHT_RANGE = 'Chiều cao phải từ 80 đến 250 cm';
const NETWORK_MESSAGE = 'Không kết nối được máy chủ';
const PERMISSION_MESSAGE = 'Bạn không có quyền thực hiện thao tác này';

async function renderHeight() {
  const client = await renderWithClient(<HeightScreen />);
  await screen.findByLabelText(HEIGHT);
  return client;
}

function button(name: string) {
  return screen.getByRole('button', { name });
}

function fieldOf(label: string) {
  return within(screen.getByTestId(`field-${label}`));
}

function heightInput() {
  return screen.getByLabelText(HEIGHT);
}

async function fillAndSave(height: string) {
  await fireEvent.changeText(heightInput(), height);
  await fireEvent.press(button(SAVE));
}

beforeEach(() => {
  jest.clearAllMocks();
  useSession.setState({ status: 'signedIn', user: SESSION_USER });
  mockedGetBodyProfile.mockResolvedValue(PROFILE_DEMO);
});

afterEach(cleanupClients);

describe('HeightScreen: sửa chiều cao thành công', () => {
  it.each([
    {
      name: '(a) profile demo, "172,5"',
      profile: PROFILE_DEMO,
      prefilled: '172',
      input: '172,5',
      body: { gender: 'male', date_of_birth: '2003-05-10', height_cm: 172.5, activity_level_id: 3, experience_level_id: 1 },
    },
    {
      name: '(b) profile newbie, "160"',
      profile: PROFILE_NEWBIE,
      prefilled: '',
      input: '160',
      body: { gender: 'unspecified', date_of_birth: null, height_cm: 160, activity_level_id: null, experience_level_id: null },
    },
  ])('FEDASH-21 $name: điền sẵn, gửi đủ 5 field, invalidate rồi quay lại', async ({ profile, prefilled, input, body }) => {
    mockedGetBodyProfile.mockResolvedValue(profile);
    const updated: BodyProfile = { ...profile, height_cm: body.height_cm, updated_at: '2026-11-29T02:00:00Z' };
    mockedReplaceBodyProfile.mockResolvedValue(updated);
    const client = await renderHeight();
    const invalidateSpy = jest.spyOn(client, 'invalidateQueries');

    expect(screen.getByRole('header', { name: 'Chiều cao' })).toBeTruthy();
    expect(heightInput().props.value).toBe(prefilled);
    await fillAndSave(input);

    await waitFor(() => expect(router.back).toHaveBeenCalledTimes(1));
    expect(mockedReplaceBodyProfile).toHaveBeenCalledTimes(1);
    expect(mockedReplaceBodyProfile).toHaveBeenCalledWith(body);
    const sentBody = mockedReplaceBodyProfile.mock.calls[0]?.[0];
    expect(sentBody).toStrictEqual(body);
    expect(sentBody).not.toHaveProperty('updated_at');
    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ['body', 'profile'] }));
    expect(invalidateSpy).toHaveBeenCalledWith(expect.objectContaining({ queryKey: ['dashboard'] }));
    expect(mockedReplaceBodyProfile.mock.invocationCallOrder[0]).toBeLessThan(
      invalidateSpy.mock.invocationCallOrder[0] ?? 0,
    );
  });

  it('FEDASH-21 nút "Quay lại" gọi router.back(), không gọi replaceBodyProfile', async () => {
    await renderHeight();

    await fireEvent.press(button('Quay lại'));

    expect(router.back).toHaveBeenCalledTimes(1);
    expect(mockedReplaceBodyProfile).not.toHaveBeenCalled();
  });
});

describe('HeightScreen: lỗi và trạng thái', () => {
  it('FEDASH-22 (a) getBodyProfile chưa trả: hiện trạng thái tải', async () => {
    mockedGetBodyProfile.mockReturnValue(neverResolves<BodyProfile>());
    await renderWithClient(<HeightScreen />);

    expect(screen.getByLabelText('Đang tải...')).toBeTruthy();
    expect(screen.queryByLabelText(HEIGHT)).toBeNull();
    expect(router.back).not.toHaveBeenCalled();
  });

  it('FEDASH-22 (b) getBodyProfile lỗi mạng: hiện lỗi và "Thử lại", bấm thì điền sẵn "172"', async () => {
    mockedGetBodyProfile.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(PROFILE_DEMO);
    await renderWithClient(<HeightScreen />);

    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    await fireEvent.press(button('Thử lại'));

    expect((await screen.findByLabelText(HEIGHT)).props.value).toBe('172');
    expect(mockedGetBodyProfile).toHaveBeenCalledTimes(2);
    expect(router.back).not.toHaveBeenCalled();
  });

  it('FEDASH-22 getBodyProfile 403 permission_denied: hiện thông điệp quyền', async () => {
    mockedGetBodyProfile.mockRejectedValue(apiError(403, 'permission_denied'));
    await renderWithClient(<HeightScreen />);

    expect(await screen.findByText(PERMISSION_MESSAGE)).toBeTruthy();
    expect(screen.queryByLabelText(HEIGHT)).toBeNull();
  });

  it.each(['70', 'abc', '251', ''])('FEDASH-22 (c) client chiều cao "%s": báo dưới ô, không gọi replaceBodyProfile', async (height) => {
    await renderHeight();

    await fillAndSave(height);

    expect(fieldOf(HEIGHT).getByText(HEIGHT_RANGE)).toBeTruthy();
    expect(screen.getAllByText(HEIGHT_RANGE)).toHaveLength(1);
    await flushPromises();
    expect(mockedReplaceBodyProfile).not.toHaveBeenCalled();
    expect(router.back).not.toHaveBeenCalled();
  });

  it('FEDASH-22 (d) server 422 validation_error height_cm: hiện ngay dưới ô Chiều cao', async () => {
    const details = [{ field: 'height_cm', message: 'Chiều cao không hợp lệ', code: 'value_error' }];
    mockedReplaceBodyProfile.mockRejectedValue(apiError(422, 'validation_error', details));
    await renderHeight();

    await fillAndSave('172,5');

    expect(await fieldOf(HEIGHT).findByText('Chiều cao không hợp lệ')).toBeTruthy();
    expect(screen.getAllByText('Chiều cao không hợp lệ')).toHaveLength(1);
    expect(router.back).not.toHaveBeenCalled();
  });

  it.each([
    { name: '(e) 403 permission_denied', error: apiError(403, 'permission_denied'), message: PERMISSION_MESSAGE },
    { name: 'lỗi mạng', error: networkError(), message: NETWORK_MESSAGE },
  ])('FEDASH-22 server $name: hiện thông điệp chung, bấm lại được, không quay lại', async ({ error, message }) => {
    mockedReplaceBodyProfile.mockRejectedValue(error);
    await renderHeight();

    await fillAndSave('172,5');

    expect(await screen.findByText(message)).toBeTruthy();
    expect(fieldOf(HEIGHT).queryByText(message)).toBeNull();
    expect(screen.queryByText(/Thông điệp server/)).toBeNull();
    await fireEvent.press(button(SAVE));
    await waitFor(() => expect(mockedReplaceBodyProfile).toHaveBeenCalledTimes(2));
    expect(router.back).not.toHaveBeenCalled();
  });
});
