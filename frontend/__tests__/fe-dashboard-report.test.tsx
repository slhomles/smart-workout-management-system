import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';

import ReportScreen from '@/screens/dashboard/ReportScreen';
import { getMe } from '@/services/auth';
import { getBodyProfile, getDashboard, getWeightTrend, listMuscleRecovery } from '@/services/dashboard';
import { useSession } from '@/store/session';

import {
  cleanupClients,
  DASHBOARD_DEMO,
  DEMO_ME,
  networkError,
  neverResolves,
  OTHER_ME,
  PROFILE_DEMO,
  RECOVERY_DEMO,
  renderWithClient,
  SESSION_USER,
  TREND_DEMO,
  TREND_NO_WEIGHT,
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
const mockedGetDashboard = jest.mocked(getDashboard);
const mockedGetWeightTrend = jest.mocked(getWeightTrend);
const mockedGetBodyProfile = jest.mocked(getBodyProfile);
const mockedListMuscleRecovery = jest.mocked(listMuscleRecovery);

// Chuỗi kỳ vọng chép nguyên từ spec fe-dashboard §2.4, §5 (không dùng lại hằng của code để bắt lỗi chính tả).
const NETWORK_MESSAGE = 'Không kết nối được máy chủ';
const PLATEAU_MESSAGE = 'Cân nặng đang chững lại. Hãy xem lại chế độ ăn và cường độ tập.';
const WEEKDAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];
const TREND_POINT_LABELS = ['26/10: 71,5', '02/11: 71,1', '09/11: 70,6', '16/11: 70,3', '23/11: 70'];

function renderReport() {
  return renderWithClient(<ReportScreen />);
}

function button(name: string) {
  return screen.getByRole('button', { name });
}

function weightSection() {
  return within(screen.getByTestId('weight-section'));
}

/** Chờ các mục tự tải riêng (trend, hồ sơ, phục hồi) xong, để không có cập nhật state ngoài `act` khi test kết thúc. */
async function waitForSectionsLoaded() {
  await screen.findByLabelText('23/11: 70');
  await screen.findByText('172 cm');
  await screen.findByText('Ngực');
}

/** Giá trị của một dòng chỉ số trong mục Cân nặng ("Hiện tại", "Nặng nhất", "Nhẹ nhất"). */
function weightRow(testID: string) {
  return within(screen.getByTestId(testID));
}

beforeEach(() => {
  jest.clearAllMocks();
  // `useMe` tắt khi `signedOut` nên màn dùng `useMe` cần phiên `signedIn` (spec §5).
  useSession.setState({ status: 'signedIn', user: SESSION_USER });
  mockedGetMe.mockResolvedValue(DEMO_ME);
  mockedGetDashboard.mockResolvedValue(DASHBOARD_DEMO);
  mockedGetWeightTrend.mockResolvedValue(TREND_DEMO);
  mockedGetBodyProfile.mockResolvedValue(PROFILE_DEMO);
  mockedListMuscleRecovery.mockResolvedValue(RECOVERY_DEMO);
});

afterEach(async () => {
  await cleanupClients();
});

describe('ReportScreen: tải và lỗi', () => {
  it('FEDASH-04 (a) GET /auth/me đang tải: hiện "Đang tải...", chưa gọi GET /dashboard', async () => {
    mockedGetMe.mockReturnValue(neverResolves());
    await renderReport();

    await waitFor(() => expect(mockedGetMe).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText('Đang tải...')).toBeTruthy();
    expect(screen.getByRole('header', { name: 'Báo cáo' })).toBeTruthy();
    expect(mockedGetDashboard).not.toHaveBeenCalled();
  });

  it('FEDASH-04 (b) GET /dashboard đang tải: hiện "Đang tải...", chưa hiện mục "Hôm nay"', async () => {
    mockedGetDashboard.mockReturnValue(neverResolves());
    await renderReport();

    await waitFor(() => expect(mockedGetDashboard).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText('Đang tải...')).toBeTruthy();
    expect(screen.queryByText('Hôm nay')).toBeNull();
  });

  it('FEDASH-04 (c) GET /dashboard lỗi mạng: báo lỗi có "Thử lại"; bấm thì hiện "Hôm nay" và "Buổi tập"', async () => {
    mockedGetDashboard.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(DASHBOARD_DEMO);
    await renderReport();

    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(button('Thử lại')).toBeTruthy();
    expect(screen.queryByText('Hôm nay')).toBeNull();

    await fireEvent.press(button('Thử lại'));

    expect(await screen.findByText('Hôm nay')).toBeTruthy();
    expect(screen.getByText('Buổi tập')).toBeTruthy();
    expect(screen.queryByText(NETWORK_MESSAGE)).toBeNull();
    expect(mockedGetDashboard).toHaveBeenCalledTimes(2);
    await waitForSectionsLoaded();
  });

  it('FEDASH-04 (d) GET /auth/me lỗi mạng: báo lỗi, chưa gọi GET /dashboard; "Thử lại" thì tải tiếp', async () => {
    mockedGetMe.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(DEMO_ME);
    await renderReport();

    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(mockedGetDashboard).not.toHaveBeenCalled();

    await fireEvent.press(button('Thử lại'));

    expect(await screen.findByText('Hôm nay')).toBeTruthy();
    expect(mockedGetMe).toHaveBeenCalledTimes(2);
    expect(mockedGetDashboard).toHaveBeenCalled();
    await waitForSectionsLoaded();
  });
});

describe('ReportScreen: Hôm nay và Lịch sử', () => {
  it('FEDASH-05 StatCard hôm nay (metric) không có calo tiêu hao; Lịch sử có WeekStrip và tiến độ tuần', async () => {
    await renderReport();

    expect(await screen.findByText('Buổi tập')).toBeTruthy();
    await waitForSectionsLoaded();
    expect(screen.getByText('Khối lượng (kg)')).toBeTruthy();
    expect(screen.getByText('4.250')).toBeTruthy();
    expect(screen.getByText('Phút')).toBeTruthy();
    expect(screen.getByText('62')).toBeTruthy();
    expect(screen.queryByText(/320/)).toBeNull();
    // Chỉ BMR/TDEE mang đơn vị kcal (spec §6 ý 4).
    expect(screen.getAllByText(/kcal/)).toHaveLength(2);
    expect(screen.queryByText('Khối lượng (lb)')).toBeNull();

    expect(screen.getByText('Lịch sử')).toBeTruthy();
    for (const day of WEEKDAYS) {
      expect(screen.getByText(day)).toBeTruthy();
    }
    expect(screen.getByText('Tuần này: 3 buổi')).toBeTruthy();
    expect(screen.getByText('Theo lịch: 2/3 buổi')).toBeTruthy();
    expect(screen.getByText('Tuân thủ 67%')).toBeTruthy();
    expect(screen.queryByLabelText(/^Chuỗi .* ngày tập$/)).toBeNull();
  });
});

describe('ReportScreen: đơn vị imperial', () => {
  it('FEDASH-06 imperial: khối lượng và cân nặng hiển thị bằng lb, không còn "70 kg"', async () => {
    mockedGetMe.mockResolvedValue(OTHER_ME);
    await renderReport();

    expect(await screen.findByText('Khối lượng (lb)')).toBeTruthy();
    expect(screen.getByText('9.370')).toBeTruthy();
    expect(screen.queryByText('Khối lượng (kg)')).toBeNull();

    await waitFor(() => expect(weightRow('weight-heaviest').getByText('157,6 lb')).toBeTruthy());
    expect(weightRow('weight-current').getByText('Hiện tại')).toBeTruthy();
    expect(weightRow('weight-current').getByText('154,3 lb')).toBeTruthy();
    expect(weightRow('weight-heaviest').getByText('Nặng nhất')).toBeTruthy();
    expect(screen.queryByText('70 kg')).toBeNull();
    // Điểm biểu đồ cũng theo đơn vị hiển thị (kgToLb).
    expect(screen.getByLabelText('23/11: 154,3')).toBeTruthy();
  });
});

describe('ReportScreen: mục Cân nặng', () => {
  it('FEDASH-07 hiện tại, nặng nhất, nhẹ nhất và 5 điểm biểu đồ của khoảng "Tháng"; không cảnh báo chững cân', async () => {
    await renderReport();

    expect(await screen.findByLabelText('23/11: 70')).toBeTruthy();
    expect(mockedGetWeightTrend).toHaveBeenCalledWith('month');
    expect(mockedGetWeightTrend).not.toHaveBeenCalledWith('3months');

    expect(screen.getByText('Cân nặng')).toBeTruthy();
    expect(screen.getByText('Hiện tại')).toBeTruthy();
    expect(screen.getAllByText('70 kg')).toHaveLength(2);
    expect(weightRow('weight-current').getByText('70 kg')).toBeTruthy();
    expect(weightRow('weight-lightest').getByText('Nhẹ nhất')).toBeTruthy();
    expect(weightRow('weight-lightest').getByText('70 kg')).toBeTruthy();
    expect(weightRow('weight-heaviest').getByText('Nặng nhất')).toBeTruthy();
    expect(weightRow('weight-heaviest').getByText('71,5 kg')).toBeTruthy();
    for (const label of TREND_POINT_LABELS) {
      expect(screen.getByLabelText(label)).toBeTruthy();
    }
    expect(screen.queryByText(PLATEAU_MESSAGE)).toBeNull();
  });

  it('FEDASH-07 dashboard.is_plateau = true: hiện cảnh báo chững cân', async () => {
    mockedGetDashboard.mockResolvedValue({ ...DASHBOARD_DEMO, is_plateau: true });
    await renderReport();

    expect(await screen.findByText(PLATEAU_MESSAGE)).toBeTruthy();
    expect(weightSection().getByText(PLATEAU_MESSAGE)).toBeTruthy();
    await waitForSectionsLoaded();
  });
});

describe('ReportScreen: khoảng thời gian, lỗi và rỗng của biểu đồ', () => {
  it('FEDASH-08 (a) mặc định chọn "Tháng"; bấm "3 Tháng" thì tải trend 3months và chọn chip đó', async () => {
    await renderReport();
    await screen.findByLabelText('23/11: 70');

    expect(button('Tháng').props.accessibilityState).toEqual(expect.objectContaining({ selected: true }));
    expect(button('3 Tháng').props.accessibilityState).toEqual(expect.objectContaining({ selected: false }));

    await fireEvent.press(button('3 Tháng'));

    await waitFor(() => expect(mockedGetWeightTrend).toHaveBeenCalledWith('3months'));
    expect(button('3 Tháng').props.accessibilityState).toEqual(expect.objectContaining({ selected: true }));
    expect(button('Tháng').props.accessibilityState).toEqual(expect.objectContaining({ selected: false }));
    expect(await screen.findByLabelText('23/11: 70')).toBeTruthy();
  });

  it('FEDASH-08 (b) trend lỗi mạng: báo lỗi trong thẻ, các mục khác vẫn hiện; "Thử lại" trong thẻ thì vẽ lại', async () => {
    mockedGetWeightTrend.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(TREND_DEMO);
    await renderReport();

    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(weightSection().getByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(screen.getByText('Buổi tập')).toBeTruthy();
    expect(screen.getByText('BMI')).toBeTruthy();
    expect(screen.queryByLabelText('23/11: 70')).toBeNull();

    await fireEvent.press(weightSection().getByRole('button', { name: 'Thử lại' }));

    expect(await screen.findByLabelText('23/11: 70')).toBeTruthy();
    expect(weightSection().queryByText(NETWORK_MESSAGE)).toBeNull();
    expect(mockedGetWeightTrend).toHaveBeenCalledTimes(2);
  });

  it('FEDASH-08 (c) mọi điểm không có cân nặng: biểu đồ rỗng, "Nặng nhất" và "Nhẹ nhất" là "—"', async () => {
    mockedGetWeightTrend.mockResolvedValue(TREND_NO_WEIGHT);
    await renderReport();

    expect(await screen.findByText('Chưa có dữ liệu cân nặng')).toBeTruthy();
    expect(weightRow('weight-heaviest').getByText('Nặng nhất')).toBeTruthy();
    expect(weightRow('weight-heaviest').getByText('—')).toBeTruthy();
    expect(weightRow('weight-lightest').getByText('—')).toBeTruthy();
    expect(weightRow('weight-current').getByText('70 kg')).toBeTruthy();
    expect(screen.queryByLabelText('23/11: 70')).toBeNull();
  });
});
