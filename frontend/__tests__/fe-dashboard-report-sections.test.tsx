import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';

import ReportScreen from '@/screens/dashboard/ReportScreen';
import { getMe } from '@/services/auth';
import { getBodyProfile, getDashboard, getWeightTrend, listMuscleRecovery } from '@/services/dashboard';
import { useSession } from '@/store/session';
import type { Dashboard } from '@/types/dashboard';

import {
  apiError,
  cleanupClients,
  DASHBOARD_DEMO,
  DASHBOARD_NEWBIE,
  DEMO_ME,
  EDITOR_ME,
  flushPromises,
  networkError,
  page,
  PROFILE_DEMO,
  PROFILE_NEWBIE,
  RECOVERY_DEMO,
  recoveryItem,
  renderWithClient,
  SESSION_USER,
  TREND_DEMO,
  TREND_EMPTY,
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
const mockedPush = jest.mocked(router.push);

// Chuỗi kỳ vọng chép nguyên từ spec fe-dashboard §2.4, §5 (không dùng lại hằng của code để bắt lỗi chính tả).
const NETWORK_MESSAGE = 'Không kết nối được máy chủ';
const BMI_MISSING_MESSAGE = 'Cần cân nặng và chiều cao để tính BMI';
const EXPORT_LABEL = 'Xuất báo cáo tuần';
const REPORTS_LINK_LABEL = 'Báo cáo đã xuất';

/** Persona unspecified (spec §5 FEDASH-10 b): có cân nặng nhưng chưa có chiều cao nên server không tính chỉ số. */
const DASHBOARD_UNSPECIFIED: Dashboard = {
  ...DASHBOARD_DEMO,
  latest_metrics: {
    measurement_id: 'm-1',
    measured_at: '2026-11-29T00:00:00Z',
    weight_kg: 65,
    body_fat_pct: null,
    bmi: null,
    bmi_category: null,
    bmr_kcal: null,
    tdee_kcal: null,
  },
};

const RECOVERY_ALL_READY = page([
  recoveryItem({ muscle_group_id: 1, muscle_code: 'chest', muscle_name: 'Ngực', recovery_status: 'ready', recovery_pct: 100 }),
  recoveryItem({ muscle_group_id: 4, muscle_code: 'biceps', muscle_name: 'Tay trước', recovery_status: 'ready', recovery_pct: 100 }),
]);

function renderReport() {
  return renderWithClient(<ReportScreen />);
}

/** Truy vấn trong một mục hoặc một dòng chỉ số có `testID` (vd "bmi-section", "bmi-bmr"). */
function section(testID: string) {
  return within(screen.getByTestId(testID));
}

/** Chờ các mục tự tải riêng (trend, hồ sơ, phục hồi) xong, để không có cập nhật state ngoài `act` khi test kết thúc. */
async function waitForSectionsLoaded() {
  await screen.findByLabelText('23/11: 70');
  await screen.findByText('172 cm');
  await screen.findByText('Ngực');
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

describe('ReportScreen: trạng thái rỗng (newbie)', () => {
  it('FEDASH-09 newbie: Cân nặng rỗng, tuần 0 buổi, không có tuân thủ, BMI và Phục hồi chưa có dữ liệu', async () => {
    mockedGetDashboard.mockResolvedValue(DASHBOARD_NEWBIE);
    mockedGetBodyProfile.mockResolvedValue(PROFILE_NEWBIE);
    mockedGetWeightTrend.mockResolvedValue(TREND_EMPTY);
    mockedListMuscleRecovery.mockResolvedValue({ data: [], pagination: { next_cursor: null, has_more: false } });
    await renderReport();

    expect(await screen.findByText('Chưa có số đo cơ thể')).toBeTruthy();
    expect(section('weight-section').getByText('Chưa có số đo cơ thể')).toBeTruthy();
    expect(screen.getByText('Tuần này: 0 buổi')).toBeTruthy();
    expect(screen.getByText('Theo lịch: 0/0 buổi')).toBeTruthy();
    expect(screen.queryByText(/Tuân thủ/)).toBeNull();

    expect(screen.getByText(BMI_MISSING_MESSAGE)).toBeTruthy();
    await waitFor(() => expect(section('bmi-height').getByText('Chưa có')).toBeTruthy());
    expect(section('bmi-height').getByText('Chiều cao')).toBeTruthy();
    expect(screen.queryByLabelText(/Thang BMI/)).toBeNull();

    expect(await screen.findByText('Chưa có dữ liệu phục hồi')).toBeTruthy();
    expect(section('recovery-section').getByText('Chưa có dữ liệu phục hồi')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Ghi lại' })).toBeTruthy();
  });
});

describe('ReportScreen: mục BMI', () => {
  it('FEDASH-10 (a) có số đo: BMI 23,7 "Thừa cân", thang BMI, BMR, TDEE, % mỡ và chiều cao 172 cm', async () => {
    await renderReport();

    expect(await screen.findByText('23,7')).toBeTruthy();
    await waitForSectionsLoaded();
    const bmi = section('bmi-section');
    expect(bmi.getByText('BMI')).toBeTruthy();
    expect(bmi.getByText('23,7')).toBeTruthy();
    expect(bmi.getByText('Thừa cân')).toBeTruthy();
    expect(bmi.getByLabelText('Thang BMI, giá trị 23,7')).toBeTruthy();
    expect(section('bmi-bmr').getByText('BMR')).toBeTruthy();
    expect(section('bmi-bmr').getByText('1.665 kcal')).toBeTruthy();
    expect(section('bmi-tdee').getByText('TDEE')).toBeTruthy();
    expect(section('bmi-tdee').getByText('2.581 kcal')).toBeTruthy();
    expect(section('bmi-body-fat').getByText('% mỡ')).toBeTruthy();
    expect(section('bmi-body-fat').getByText('18,4%')).toBeTruthy();
    expect(section('bmi-height').getByText('172 cm')).toBeTruthy();
    expect(screen.queryByText(BMI_MISSING_MESSAGE)).toBeNull();
  });

  it('FEDASH-10 (b) persona unspecified: không có BMI, BMR/TDEE/% mỡ là "—", chiều cao "Chưa có"', async () => {
    mockedGetDashboard.mockResolvedValue(DASHBOARD_UNSPECIFIED);
    mockedGetBodyProfile.mockResolvedValue(PROFILE_NEWBIE);
    await renderReport();

    expect(await screen.findByText(BMI_MISSING_MESSAGE)).toBeTruthy();
    await waitFor(() => expect(section('bmi-height').getByText('Chưa có')).toBeTruthy());
    await screen.findByLabelText('23/11: 70');
    await screen.findByText('Ngực');

    const bmi = section('bmi-section');
    expect(bmi.getByText(BMI_MISSING_MESSAGE)).toBeTruthy();
    expect(bmi.getAllByText('—')).toHaveLength(3);
    expect(screen.getAllByText('—')).toHaveLength(3);
    expect(section('bmi-bmr').getByText('BMR')).toBeTruthy();
    expect(section('bmi-bmr').getByText('—')).toBeTruthy();
    expect(section('bmi-tdee').getByText('TDEE')).toBeTruthy();
    expect(section('bmi-tdee').getByText('—')).toBeTruthy();
    expect(section('bmi-body-fat').getByText('% mỡ')).toBeTruthy();
    expect(section('bmi-body-fat').getByText('—')).toBeTruthy();
    expect(section('bmi-height').getByText('Chiều cao')).toBeTruthy();
    expect(screen.queryByLabelText(/Thang BMI/)).toBeNull();
    expect(screen.queryByText(/kcal/)).toBeNull();
  });
});

describe('ReportScreen: mục Phục hồi', () => {
  it('FEDASH-12 (a) chỉ liệt kê nhóm cơ chưa sẵn sàng; gọi listMuscleRecovery({ limit: 100 })', async () => {
    await renderReport();

    expect(await screen.findByText('Ngực')).toBeTruthy();
    await waitForSectionsLoaded();
    expect(mockedListMuscleRecovery).toHaveBeenCalledWith({ limit: 100 });
    const recovery = section('recovery-section');
    expect(recovery.getByText('Phục hồi')).toBeTruthy();
    expect(recovery.getByText('Ngực')).toBeTruthy();
    expect(recovery.getByText('Mệt mỏi')).toBeTruthy();
    expect(recovery.getByText('2%')).toBeTruthy();
    expect(recovery.getByText('Tay sau')).toBeTruthy();
    expect(recovery.getByText('Đang hồi phục')).toBeTruthy();
    expect(recovery.getByText('60%')).toBeTruthy();
    expect(screen.queryByText('Tay trước')).toBeNull();
    expect(screen.queryByText('Sẵn sàng')).toBeNull();
  });

  it('FEDASH-12 (b) mọi nhóm cơ đều ready: hiện "Mọi nhóm cơ đã sẵn sàng tập"', async () => {
    mockedListMuscleRecovery.mockResolvedValue(RECOVERY_ALL_READY);
    await renderReport();

    expect(await screen.findByText('Mọi nhóm cơ đã sẵn sàng tập')).toBeTruthy();
    expect(section('recovery-section').getByText('Mọi nhóm cơ đã sẵn sàng tập')).toBeTruthy();
    expect(mockedListMuscleRecovery).toHaveBeenCalledWith({ limit: 100 });
    expect(screen.queryByText('Ngực')).toBeNull();
    expect(screen.queryByText('Tay trước')).toBeNull();
    await screen.findByLabelText('23/11: 70');
    await screen.findByText('172 cm');
  });

  it('FEDASH-12 (c) lỗi mạng: báo lỗi trong mục, "Buổi tập" vẫn hiện; "Thử lại" trong mục thì hiện "Ngực"', async () => {
    mockedListMuscleRecovery.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(RECOVERY_DEMO);
    await renderReport();

    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(section('recovery-section').getByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(screen.getByText('Buổi tập')).toBeTruthy();
    expect(screen.queryByText('Ngực')).toBeNull();
    await screen.findByLabelText('23/11: 70');
    await screen.findByText('172 cm');

    await fireEvent.press(section('recovery-section').getByRole('button', { name: 'Thử lại' }));

    expect(await screen.findByText('Ngực')).toBeTruthy();
    expect(section('recovery-section').getByText('Ngực')).toBeTruthy();
    expect(screen.queryByText(NETWORK_MESSAGE)).toBeNull();
    expect(mockedListMuscleRecovery).toHaveBeenCalledTimes(2);
    expect(mockedListMuscleRecovery).toHaveBeenNthCalledWith(2, { limit: 100 });
  });
});

describe('ReportScreen: permission', () => {
  it('FEDASH-13 (a) editor thiếu body_metric:manage_own: báo không có quyền, không gọi API báo cáo nào', async () => {
    mockedGetMe.mockResolvedValue(EDITOR_ME);
    await renderReport();

    expect(await screen.findByText('Bạn không có quyền xem báo cáo')).toBeTruthy();
    await flushPromises();
    expect(mockedGetMe).toHaveBeenCalled();
    expect(mockedGetDashboard).not.toHaveBeenCalled();
    expect(mockedGetWeightTrend).not.toHaveBeenCalled();
    expect(mockedGetBodyProfile).not.toHaveBeenCalled();
    expect(mockedListMuscleRecovery).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: EXPORT_LABEL })).toBeNull();
    expect(screen.queryByText(EXPORT_LABEL)).toBeNull();
    expect(screen.queryByText('Hôm nay')).toBeNull();
  });

  it('FEDASH-13 (b) chỉ có body_metric:manage_own: không có Phục hồi, nút xuất và link "Báo cáo đã xuất"', async () => {
    mockedGetMe.mockResolvedValue({ ...DEMO_ME, permissions: ['body_metric:manage_own'] });
    await renderReport();

    expect(await screen.findByText('Hôm nay')).toBeTruthy();
    await screen.findByLabelText('23/11: 70');
    await screen.findByText('172 cm');
    await flushPromises();
    expect(screen.queryByText('Phục hồi')).toBeNull();
    expect(screen.queryByTestId('recovery-section')).toBeNull();
    expect(mockedListMuscleRecovery).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: EXPORT_LABEL })).toBeNull();
    expect(screen.queryByText(EXPORT_LABEL)).toBeNull();
    expect(screen.queryByLabelText(REPORTS_LINK_LABEL)).toBeNull();
    expect(screen.queryByText(REPORTS_LINK_LABEL)).toBeNull();
    // Các mục cần body_metric:manage_own vẫn hiện.
    expect(screen.getByText('Lịch sử')).toBeTruthy();
    expect(screen.getByText('BMI')).toBeTruthy();
  });

  it('FEDASH-13 (c) GET /dashboard trả 403 permission_denied: hiện "Bạn không có quyền thực hiện thao tác này"', async () => {
    mockedGetDashboard.mockRejectedValue(apiError(403, 'permission_denied'));
    await renderReport();

    expect(await screen.findByText('Bạn không có quyền thực hiện thao tác này')).toBeTruthy();
    expect(screen.queryByText('Thông điệp server (permission_denied)')).toBeNull();
    expect(screen.queryByText('Hôm nay')).toBeNull();
  });
});

describe('ReportScreen: điều hướng', () => {
  it('FEDASH-14 "Ghi lại", "Sửa chiều cao", "Báo cáo đã xuất" mở đúng màn trong stats/', async () => {
    await renderReport();
    await screen.findByText('Hôm nay');
    await waitForSectionsLoaded();

    await fireEvent.press(screen.getByRole('button', { name: 'Ghi lại' }));
    await fireEvent.press(screen.getByRole('button', { name: 'Sửa chiều cao' }));
    await fireEvent.press(screen.getByLabelText(REPORTS_LINK_LABEL));

    expect(mockedPush.mock.calls).toEqual([['/stats/record-weight'], ['/stats/height'], ['/stats/reports']]);
  });
});
