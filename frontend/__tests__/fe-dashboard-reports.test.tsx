import { fireEvent, screen, waitFor, within } from '@testing-library/react-native';
import { router } from 'expo-router';

import ReportsScreen from '@/screens/dashboard/ReportsScreen';
import { getMe } from '@/services/auth';
import { listReports } from '@/services/dashboard';
import { useSession } from '@/store/session';

import {
  apiError,
  cleanupClients,
  DEMO_ME,
  flushPromises,
  networkError,
  neverResolves,
  OTHER_ME,
  page,
  renderWithClient,
  REPORT_R1,
  REPORT_R2,
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
const mockedListReports = jest.mocked(listReports);

// Chuỗi kỳ vọng chép nguyên từ spec fe-dashboard §2.4, §5 (không dùng lại hằng của code để bắt lỗi chính tả).
const NETWORK_MESSAGE = 'Không kết nối được máy chủ';
const R1_PERIOD = 'Tuần 16/11/2026 – 22/11/2026';
const R2_PERIOD = 'Tuần 09/11/2026 – 15/11/2026';
const LIST_TEST_ID = 'reports-list';

function renderReports() {
  return renderWithClient(<ReportsScreen />);
}

function button(name: string) {
  return screen.getByRole('button', { name });
}

function reportCard(id: string) {
  return within(screen.getByTestId(`report-${id}`));
}

function reachEnd() {
  return fireEvent(screen.getByTestId(LIST_TEST_ID), 'endReached');
}

beforeEach(() => {
  jest.clearAllMocks();
  // `useMe` tắt khi `signedOut` nên màn dùng `useMe` cần phiên `signedIn` (spec §5).
  useSession.setState({ status: 'signedIn', user: SESSION_USER });
  mockedGetMe.mockResolvedValue(DEMO_ME);
});

afterEach(async () => {
  await cleanupClients();
});

describe('ReportsScreen: trạng thái', () => {
  it('FEDASH-17 (a) GET /reports đang tải: hiện "Đang tải..." dưới tiêu đề "Báo cáo đã xuất"', async () => {
    mockedListReports.mockReturnValue(neverResolves());
    await renderReports();

    await waitFor(() => expect(mockedListReports).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText('Đang tải...')).toBeTruthy();
    expect(screen.getByRole('header', { name: 'Báo cáo đã xuất' })).toBeTruthy();
  });

  it('FEDASH-17 GET /auth/me đang tải: hiện "Đang tải...", chưa gọi GET /reports', async () => {
    mockedGetMe.mockReturnValue(neverResolves());
    await renderReports();

    await waitFor(() => expect(mockedGetMe).toHaveBeenCalledTimes(1));
    expect(screen.getByLabelText('Đang tải...')).toBeTruthy();
    expect(mockedListReports).not.toHaveBeenCalled();
  });

  it('FEDASH-17 (b) lỗi mạng: hiện thông điệp và "Thử lại"; bấm thì hiện báo cáo, GET /reports gọi 2 lần', async () => {
    mockedListReports.mockRejectedValueOnce(networkError()).mockResolvedValueOnce(page([REPORT_R1]));
    await renderReports();

    expect(await screen.findByText(NETWORK_MESSAGE)).toBeTruthy();
    expect(button('Thử lại')).toBeTruthy();
    expect(screen.queryByText(R1_PERIOD)).toBeNull();

    await fireEvent.press(button('Thử lại'));

    expect(await screen.findByText(R1_PERIOD)).toBeTruthy();
    expect(screen.queryByText(NETWORK_MESSAGE)).toBeNull();
    expect(mockedListReports).toHaveBeenCalledTimes(2);
  });

  it('FEDASH-17 (c) 403 permission_denied: hiện "Bạn không có quyền thực hiện thao tác này"', async () => {
    mockedListReports.mockRejectedValue(apiError(403, 'permission_denied'));
    await renderReports();

    expect(await screen.findByText('Bạn không có quyền thực hiện thao tác này')).toBeTruthy();
    expect(screen.queryByText('Thông điệp server (permission_denied)')).toBeNull();
  });

  it('FEDASH-17 (d) danh sách rỗng: hiện "Chưa có báo cáo nào"', async () => {
    mockedListReports.mockResolvedValue(page([]));
    await renderReports();

    expect(await screen.findByText('Chưa có báo cáo nào')).toBeTruthy();
    expect(screen.queryByText(/Tuần /)).toBeNull();
  });

  it('FEDASH-17 nút "Quay lại" gọi router.back()', async () => {
    mockedListReports.mockResolvedValue(page([]));
    await renderReports();
    await screen.findByText('Chưa có báo cáo nào');

    await fireEvent.press(button('Quay lại'));

    expect(router.back).toHaveBeenCalledTimes(1);
  });
});

describe('ReportsScreen: dữ liệu và phân trang', () => {
  function mockTwoPages() {
    mockedListReports.mockResolvedValueOnce(page([REPORT_R1], 'c-2')).mockResolvedValueOnce(page([REPORT_R2]));
  }

  it('FEDASH-18 metric: thẻ r-1 đủ dòng, không có calo; cuộn cuối tải trang 2 theo cursor, không gọi lần 3', async () => {
    mockTwoPages();
    await renderReports();

    expect(await screen.findByText(R1_PERIOD)).toBeTruthy();
    expect(reportCard('r-1').getByText('3 buổi • 12.450 kg • 185 phút')).toBeTruthy();
    expect(reportCard('r-1').getByText('Tuân thủ 67%')).toBeTruthy();
    expect(reportCard('r-1').getByText('Cân nặng TB 70,3 kg')).toBeTruthy();
    expect(screen.queryByText(/900/)).toBeNull();
    expect(mockedListReports).toHaveBeenCalledTimes(1);
    const firstParams = mockedListReports.mock.calls[0]?.[0];
    expect(firstParams).toMatchObject({ report_type: 'weekly_summary', limit: 20 });
    expect(firstParams?.cursor).toBeUndefined();

    await reachEnd();
    expect(await screen.findByText(R2_PERIOD)).toBeTruthy();
    expect(mockedListReports.mock.calls[1]?.[0]).toMatchObject({ report_type: 'weekly_summary', limit: 20, cursor: 'c-2' });
    expect(reportCard('r-2').getByText('2 buổi • 12.450 kg • 185 phút')).toBeTruthy();
    // r-2 không có tuân thủ và cân nặng TB (null) nên không hiện hai dòng đó.
    expect(reportCard('r-2').queryByText(/Tuân thủ/)).toBeNull();
    expect(reportCard('r-2').queryByText(/Cân nặng TB/)).toBeNull();

    await reachEnd();
    await flushPromises();
    expect(mockedListReports).toHaveBeenCalledTimes(2);
    expect(screen.getByText(R1_PERIOD)).toBeTruthy();
    expect(screen.queryByText(/900/)).toBeNull();
  });

  it('FEDASH-18 gọi endReached liên tiếp khi trang 2 đang tải thì chỉ gửi một request trang 2', async () => {
    mockTwoPages();
    await renderReports();
    await screen.findByText(R1_PERIOD);

    await reachEnd();
    await reachEnd();

    expect(await screen.findByText(R2_PERIOD)).toBeTruthy();
    await flushPromises();
    expect(mockedListReports).toHaveBeenCalledTimes(2);
  });

  it('FEDASH-18 imperial (persona other): cân nặng TB theo lb, không còn "70,3 kg"', async () => {
    mockedGetMe.mockResolvedValue(OTHER_ME);
    mockedListReports.mockResolvedValue(page([REPORT_R1]));
    await renderReports();

    expect(await screen.findByText(R1_PERIOD)).toBeTruthy();
    expect(reportCard('r-1').getByText('Cân nặng TB 155 lb')).toBeTruthy();
    expect(screen.queryByText(/70,3 kg/)).toBeNull();
  });
});
