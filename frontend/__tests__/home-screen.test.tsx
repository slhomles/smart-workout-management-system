import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react-native';
import { AxiosError } from 'axios';
import type { ReactNode } from 'react';

import { HealthCard } from '@/screens/home/HomeScreen';
import { getHealth } from '@/services/health';

jest.mock('@/services/health', () => ({ getHealth: jest.fn() }));
const mockedGetHealth = jest.mocked(getHealth);

async function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe('HealthCard', () => {
  it('hiện trạng thái từng thành phần khi gọi /health thành công', async () => {
    mockedGetHealth.mockResolvedValue({ database: 'up', redis: 'up', ai_service: 'degraded', checked_at: '2026-11-27T10:00:00Z' });
    await wrap(<HealthCard />);
    expect(await screen.findByText('degraded')).toBeTruthy();
    expect(screen.getAllByText('up')).toHaveLength(2);
  });

  it('lỗi mạng: báo không kết nối được và thử lại', async () => {
    mockedGetHealth.mockRejectedValueOnce(new AxiosError('Network Error'));
    mockedGetHealth.mockResolvedValueOnce({ database: 'up', redis: 'up', ai_service: 'up', checked_at: '2026-11-27T10:00:00Z' });
    await wrap(<HealthCard />);
    expect(await screen.findByText('Không kết nối được máy chủ')).toBeTruthy();
    await fireEvent.press(screen.getByText('Thử lại'));
    expect(await screen.findAllByText('up')).toHaveLength(3);
  });
});
