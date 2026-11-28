import { fireEvent, screen, waitFor } from '@testing-library/react-native';
import { router } from 'expo-router';

import ReportScreen from '@/screens/dashboard/ReportScreen';
import { getMe } from '@/services/auth';
import { createReport, getBodyProfile, getDashboard, getWeightTrend, listMuscleRecovery } from '@/services/dashboard';
import { useSession } from '@/store/session';
import type { ReportExport } from '@/types/dashboard';

import {
  apiError,
  cleanupClients,
  DASHBOARD_DEMO,
  deferred,
  DEMO_ME,
  flushPromises,
  networkError,
  PROFILE_DEMO,
  RECOVERY_DEMO,
  renderWithClient,
  REPORT_R1,
  SESSION_USER,
  TREND_DEMO,
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
const mockedCreateReport = jest.mocked(createReport);

// Chuỗi kỳ vọng chép nguyên từ spec fe-dashboard §2.4, §5 (không dùng lại hằng của code để bắt lỗi chính tả).
const EXPORT = 'Xuất báo cáo tuần';
const EXPORT_BODY = { report_type: 'weekly_summary', period_start: '2026-11-16' };

// Chỉ giả `Date` (spec §5 FEDASH-15): timer thật để React Query và testing-library vẫn chạy như thường.
const REAL_TIMER_APIS = [
  'hrtime',
  'nextTick',
  'performance',
  'queueMicrotask',
  'requestAnimationFrame',
  'cancelAnimationFrame',
  'requestIdleCallback',
  'cancelIdleCallback',
  'setImmediate',
  'clearImmediate',
  'setInterval',
  'clearInterval',
  'setTimeout',
  'clearTimeout',
] as const;
// Chủ nhật 29/11/2026 09:00 giờ máy: tuần trước bắt đầu Thứ Hai 16/11/2026.
const NOW = new Date(2026, 10, 29, 9, 0);

function exportButton() {
  return screen.getByRole('button', { name: EXPORT });
}

/** Render tab Báo cáo với dữ liệu như FEDASH-05 và chờ mọi mục tải xong, trả QueryClient để spy. */
async function renderLoadedReport() {
  const client = await renderWithClient(<ReportScreen />);
  await screen.findByLabelText('23/11: 70');
  await screen.findByText('172 cm');
  await screen.findByText('Ngực');
  return client;
}

beforeEach(() => {
  jest.clearAllMocks();
  jest.useFakeTimers({ doNotFake: [...REAL_TIMER_APIS] });
  jest.setSystemTime(NOW);
  useSession.setState({ status: 'signedIn', user: SESSION_USER });
  mockedGetMe.mockResolvedValue(DEMO_ME);
  mockedGetDashboard.mockResolvedValue(DASHBOARD_DEMO);
  mockedGetWeightTrend.mockResolvedValue(TREND_DEMO);
  mockedGetBodyProfile.mockResolvedValue(PROFILE_DEMO);
  mockedListMuscleRecovery.mockResolvedValue(RECOVERY_DEMO);
});

afterEach(async () => {
  await cleanupClients();
  jest.useRealTimers();
});

describe('ReportScreen: Xuất báo cáo tuần', () => {
  it('FEDASH-15 bấm 2 lần khi đang chờ chỉ gửi 1 lần tuần trước; thành công thì invalidate ["reports"] rồi mở /stats/reports', async () => {
    const pending = deferred<ReportExport>();
    mockedCreateReport.mockReturnValue(pending.promise);
    const client = await renderLoadedReport();
    const invalidateSpy = jest.spyOn(client, 'invalidateQueries');

    await fireEvent.press(exportButton());
    await fireEvent.press(exportButton());
    await flushPromises();

    expect(mockedCreateReport).toHaveBeenCalledTimes(1);
    expect(mockedCreateReport).toHaveBeenCalledWith(EXPORT_BODY);
    expect(router.push).not.toHaveBeenCalled();

    pending.resolve(REPORT_R1);

    await waitFor(() => expect(router.push).toHaveBeenCalledTimes(1));
    expect(router.push).toHaveBeenCalledWith('/stats/reports');
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['reports'] });
    expect(mockedCreateReport).toHaveBeenCalledTimes(1);
  });

  it('FEDASH-16 lỗi 409, 422, 403, mạng: hiện đúng thông điệp, không điều hướng, bấm lại thì gọi lại API', async () => {
    const periodStartDetail = { field: 'period_start', message: 'Kỳ báo cáo chưa bắt đầu', code: 'value_error' };
    const cases: [Error, string][] = [
      [apiError(409, 'report_already_exists'), 'Báo cáo tuần trước đã được xuất'],
      [apiError(422, 'validation_error', [periodStartDetail], 'Dữ liệu gửi lên không hợp lệ'), 'Dữ liệu gửi lên không hợp lệ'],
      [apiError(403, 'permission_denied'), 'Bạn không có quyền thực hiện thao tác này'],
      [networkError(), 'Không kết nối được máy chủ'],
    ];
    for (const [err] of cases) mockedCreateReport.mockRejectedValueOnce(err);
    await renderLoadedReport();

    for (const [index, [, message]] of cases.entries()) {
      await fireEvent.press(exportButton());

      expect(await screen.findByText(message)).toBeTruthy();
      expect(mockedCreateReport).toHaveBeenCalledTimes(index + 1);
      expect(mockedCreateReport).toHaveBeenLastCalledWith(EXPORT_BODY);
      expect(router.push).not.toHaveBeenCalled();
    }
    // Thông điệp của lần trước được xoá khi bấm lại; ô `period_start` không có trên màn nên không hiện riêng.
    expect(screen.queryByText('Báo cáo tuần trước đã được xuất')).toBeNull();
    expect(screen.queryByText('Kỳ báo cáo chưa bắt đầu')).toBeNull();
  });
});
