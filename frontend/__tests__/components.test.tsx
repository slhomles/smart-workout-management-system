import { fireEvent, render, screen } from '@testing-library/react-native';

import { buildWeek, Chip, DifficultyBolts, formatClock, ListItem, StatCard, startOfWeek, WeekStrip } from '@/components/common';

describe('WeekStrip', () => {
  it('tuần bắt đầu từ Thứ Hai', async () => {
    const sunday = new Date(2026, 10, 29);
    expect(startOfWeek(sunday).getDate()).toBe(23);
  });

  it('đánh dấu hôm nay và ngày đã tập', async () => {
    const days = buildWeek(new Date(2026, 10, 27), ['2026-11-25']);
    expect(days).toHaveLength(7);
    expect(days.find((d) => d.isToday)?.date.getDate()).toBe(27);
    expect(days.filter((d) => d.isDone).map((d) => d.date.getDate())).toEqual([25]);
    await render(<WeekStrip days={days} />);
    expect(screen.getByLabelText('T4 ngày 25, đã tập')).toBeTruthy();
  });
});

describe('component cơ bản', () => {
  it('formatClock định dạng mm:ss và không âm', async () => {
    expect(formatClock(21)).toBe('00:21');
    expect(formatClock(125)).toBe('02:05');
    expect(formatClock(-3)).toBe('00:00');
  });

  it('DifficultyBolts giới hạn trong 0..max', async () => {
    await render(<DifficultyBolts rank={5} />);
    expect(screen.getByLabelText('Độ khó 3/3')).toBeTruthy();
  });

  it('Chip báo trạng thái chọn và gọi onPress', async () => {
    const onPress = jest.fn();
    await render(<Chip label="Ngực" selected onPress={onPress} />);
    await fireEvent.press(screen.getByRole('button'));
    expect(onPress).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button').props.accessibilityState).toMatchObject({ selected: true });
  });

  it('ListItem hiện tên, dòng phụ, nhãn và độ khó', async () => {
    await render(<ListItem title="Barbell Back Squat" meta="4 hiệp × 8 rep" badge="AI" difficultyRank={2} />);
    expect(screen.getByText('Barbell Back Squat')).toBeTruthy();
    expect(screen.getByText('4 hiệp × 8 rep')).toBeTruthy();
    expect(screen.getByText('AI')).toBeTruthy();
    expect(screen.getByLabelText('Độ khó 2/3')).toBeTruthy();
  });

  it('StatCard hiện đủ các chỉ số', async () => {
    await render(
      <StatCard
        stats={[
          { icon: 'medal-outline', value: '3', label: 'Buổi tập' },
          { icon: 'time-outline', value: '95', label: 'Phút' },
        ]}
      />,
    );
    expect(screen.getByText('Buổi tập')).toBeTruthy();
    expect(screen.getByText('95')).toBeTruthy();
  });
});
