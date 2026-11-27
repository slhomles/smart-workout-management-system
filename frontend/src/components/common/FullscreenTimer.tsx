import { StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { spacing, typography, useTheme } from '@/styles/theme';

import { AppText } from './AppText';
import { GradientButton } from './GradientButton';

/** mm:ss từ số giây (không âm). */
export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.round(totalSeconds));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
}

type Props = {
  title: string;
  secondsLeft: number;
  nextLabel?: string;
  onAdd?: () => void;
  addLabel?: string;
  onSkip?: () => void;
};

/**
 * Màn nghỉ toàn màn xanh (ảnh mẫu 10): "TIẾP THEO", đồng hồ trắng rất lớn, "+20s" và "Bỏ qua".
 * Đồng hồ hiển thị `secondsLeft` do màn gọi tính từ thời điểm kết thúc đã lưu (AGENT_RESOURCES.md §3.1).
 */
export function FullscreenTimer({ title, secondsLeft, nextLabel, onAdd, addLabel = '+20s', onSkip }: Props) {
  const theme = useTheme();
  return (
    <SafeAreaView style={[styles.fill, { backgroundColor: theme.primary }]}>
      {nextLabel && (
        <AppText variant="itemTitle" color={theme.onPrimary} style={styles.next}>
          {nextLabel}
        </AppText>
      )}
      <View style={styles.center}>
        <AppText variant="display" color={theme.onPrimary}>
          {title}
        </AppText>
        <AppText style={[typography.numberXL, styles.clock]} color={theme.onPrimary}>
          {formatClock(secondsLeft)}
        </AppText>
      </View>
      <View style={styles.actions}>
        {onAdd && (
          <View style={styles.fill}>
            <GradientButton label={addLabel} onPress={onAdd} variant="ghost" />
          </View>
        )}
        {onSkip && (
          <View style={styles.fill}>
            <GradientButton label="Bỏ qua" onPress={onSkip} variant="white" />
          </View>
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1 },
  next: { padding: spacing.lg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: spacing.md },
  clock: { fontSize: 96, lineHeight: 110 },
  actions: { flexDirection: 'row', gap: spacing.lg, padding: spacing.xl },
});
