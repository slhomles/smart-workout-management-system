import { Ionicons } from '@expo/vector-icons';
import { StyleSheet, View } from 'react-native';

import { radius, spacing, useTheme } from '@/styles/theme';

import { AppText } from './AppText';

const WEEKDAY_LABELS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];

export type WeekDay = { date: Date; isToday?: boolean; isDone?: boolean };

/** Thứ Hai của tuần chứa `date` (tuần Việt Nam bắt đầu từ Thứ Hai). */
export function startOfWeek(date: Date): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const offset = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - offset);
  return d;
}

/** 7 ngày từ Thứ Hai; `doneDates` là chuỗi YYYY-MM-DD theo giờ địa phương. */
export function buildWeek(today: Date, doneDates: string[] = []): WeekDay[] {
  const start = startOfWeek(today);
  const key = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return Array.from({ length: 7 }, (_, i) => {
    const date = new Date(start);
    date.setDate(start.getDate() + i);
    return { date, isToday: key(date) === key(today), isDone: doneDates.includes(key(date)) };
  });
}

type Props = { days: WeekDay[]; showLabels?: boolean };

/** Dải 7 ngày (ảnh mẫu 01, 11): hôm nay có vòng xanh, ngày đã tập tô tròn xanh kèm tick. */
export function WeekStrip({ days, showLabels = true }: Props) {
  const theme = useTheme();
  return (
    <View style={styles.row}>
      {days.map((day, i) => (
        <View key={day.date.toISOString()} style={styles.col}>
          {showLabels && (
            <AppText variant="meta" color={theme.textMuted}>
              {WEEKDAY_LABELS[i]}
            </AppText>
          )}
          <View
            style={[
              styles.circle,
              day.isDone && { backgroundColor: theme.primary },
              day.isToday && !day.isDone && { borderColor: theme.primary, borderWidth: 2 },
            ]}
            accessibilityLabel={`${WEEKDAY_LABELS[i]} ngày ${day.date.getDate()}${day.isDone ? ', đã tập' : ''}`}
          >
            {day.isDone ? (
              <Ionicons name="checkmark" size={24} color={theme.onPrimary} />
            ) : (
              <AppText variant="itemTitle" color={day.isToday ? theme.primary : theme.text}>
                {day.date.getDate()}
              </AppText>
            )}
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', justifyContent: 'space-between' },
  col: { alignItems: 'center', gap: spacing.sm },
  circle: { width: 44, height: 44, borderRadius: radius.pill, alignItems: 'center', justifyContent: 'center' },
});
