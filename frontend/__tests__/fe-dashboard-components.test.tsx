import { fireEvent, render, screen, within } from '@testing-library/react-native';

import { bmiScalePosition, BMI_BOUNDS, BmiScale, chartDomain, LineChartCard } from '@/components/common';
import { formatNumber } from '@/utils/format';

const WEIGHT_POINTS = [
  { label: '26/10', value: 71.5 },
  { label: '02/11', value: 71.1 },
  { label: '23/11', value: 70 },
];

describe('bmiScalePosition, chartDomain', () => {
  it('FEDASH-02 bmiScalePosition nội suy theo 6 dải và kẹp ở hai đầu', () => {
    expect(BMI_BOUNDS).toEqual([15, 16, 18.5, 23, 25, 30, 35]);
    expect(bmiScalePosition(10)).toBe(0);
    expect(bmiScalePosition(15)).toBe(0);
    expect(bmiScalePosition(16)).toBeCloseTo(1 / 6);
    expect(bmiScalePosition(18.5)).toBeCloseTo(2 / 6);
    expect(bmiScalePosition(23)).toBe(0.5);
    expect(bmiScalePosition(23.7)).toBeCloseTo(0.5583, 4);
    expect(bmiScalePosition(25)).toBeCloseTo(4 / 6);
    expect(bmiScalePosition(30)).toBeCloseTo(5 / 6);
    expect(bmiScalePosition(35)).toBe(1);
    expect(bmiScalePosition(42)).toBe(1);
  });

  it('FEDASH-02 chartDomain đệm 10% biên độ, giá trị đơn lẻ ±1, rỗng là null', () => {
    const domain = chartDomain([72.4, 70]);
    expect(domain?.min).toBeCloseTo(69.76);
    expect(domain?.max).toBeCloseTo(72.64);
    expect(chartDomain([60])).toEqual({ min: 59, max: 61 });
    expect(chartDomain([])).toBeNull();
  });
});

describe('LineChartCard', () => {
  it('FEDASH-11 mỗi điểm là nút có nhãn, hiện nhãn trục X và bong bóng theo điểm chọn', async () => {
    await render(<LineChartCard points={WEIGHT_POINTS} formatValue={(v) => formatNumber(v)} />);

    const buttons = screen.getAllByRole('button');
    expect(buttons.map((b) => b.props.accessibilityLabel)).toEqual(['26/10: 71,5', '02/11: 71,1', '23/11: 70']);
    for (const label of ['26/10', '02/11', '23/11']) {
      expect(screen.getByText(label)).toBeTruthy();
    }
    expect(within(screen.getByLabelText('Giá trị đang chọn')).getByText('70')).toBeTruthy();

    await fireEvent.press(screen.getByLabelText('26/10: 71,5'));

    const bubble = screen.getByLabelText('Giá trị đang chọn');
    expect(within(bubble).getByText('71,5')).toBeTruthy();
    expect(within(bubble).queryByText('70')).toBeNull();
  });

  it('FEDASH-11 vẽ đường và lưới khi đã đo được chiều rộng', async () => {
    await render(<LineChartCard points={WEIGHT_POINTS} />);
    await fireEvent(screen.getByTestId('line-chart-plot'), 'layout', {
      nativeEvent: { layout: { x: 0, y: 0, width: 300, height: 176 } },
    });
    expect(screen.getByTestId('line-chart-svg')).toBeTruthy();
    expect(screen.getAllByRole('button')).toHaveLength(3);
  });

  it('FEDASH-11 khi danh sách điểm ngắn lại thì chọn điểm cuối mới', async () => {
    const view = await render(<LineChartCard points={WEIGHT_POINTS} />);
    await fireEvent.press(screen.getByLabelText('02/11: 71,1'));
    expect(within(screen.getByLabelText('Giá trị đang chọn')).getByText('71,1')).toBeTruthy();

    await view.rerender(<LineChartCard points={[{ label: '30/11', value: 69.4 }]} />);

    expect(screen.getAllByRole('button')).toHaveLength(1);
    expect(within(screen.getByLabelText('Giá trị đang chọn')).getByText('69,4')).toBeTruthy();
  });

  it('FEDASH-11 không có điểm thì hiện thông điệp rỗng', async () => {
    await render(<LineChartCard points={[]} />);
    expect(screen.getByText('Chưa có dữ liệu cân nặng')).toBeTruthy();
    expect(screen.queryByLabelText('Giá trị đang chọn')).toBeNull();
    expect(screen.queryAllByRole('button')).toHaveLength(0);
  });

  it('FEDASH-11 dùng emptyText tuỳ chọn khi không có điểm', async () => {
    await render(<LineChartCard points={[]} emptyText="Không có số liệu" />);
    expect(screen.getByText('Không có số liệu')).toBeTruthy();
  });
});

describe('BmiScale', () => {
  it('FEDASH-11 có nhãn truy cập theo BMI và đủ 7 nhãn mốc', async () => {
    await render(<BmiScale bmi={23.7} />);
    expect(screen.getByLabelText('Thang BMI, giá trị 23,7')).toBeTruthy();
    for (const label of ['15', '16', '18,5', '23', '25', '30', '35']) {
      expect(screen.getByText(label)).toBeTruthy();
    }
  });

  it('FEDASH-11 BMI vượt thang vẫn render được', async () => {
    await render(<BmiScale bmi={42} />);
    expect(screen.getByLabelText('Thang BMI, giá trị 42')).toBeTruthy();
  });
});
