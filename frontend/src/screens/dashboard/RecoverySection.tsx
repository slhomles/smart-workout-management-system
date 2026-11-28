import { StyleSheet, View } from 'react-native';

import { AppText, ErrorState, LoadingState, SectionHeader } from '@/components/common';
import { useMuscleRecovery } from '@/hooks/dashboard/useMuscleRecovery';
import { screenErrorMessage } from '@/screens/profile/screen-error';
import { spacing, useTheme } from '@/styles/theme';
import type { MuscleRecoveryStatus } from '@/types/dashboard';

import { ReportCard } from './ReportCard';
import { recoveryStatusLabel } from './report-utils';

function RecoveryRow({ item }: { item: MuscleRecoveryStatus }) {
  const theme = useTheme();
  const color = item.recovery_status === 'fatigued' ? theme.flame : theme.accentOrange;
  return (
    <View style={styles.row}>
      <AppText variant="itemTitle" style={styles.name}>
        {item.muscle_name}
      </AppText>
      <AppText variant="meta" color={color}>
        {recoveryStatusLabel(item.recovery_status)}
      </AppText>
      <AppText variant="itemTitle">{`${item.recovery_pct}%`}</AppText>
    </View>
  );
}

/** Chỉ liệt kê nhóm cơ chưa sẵn sàng; danh sách rỗng và "mọi nhóm sẵn sàng" có thông điệp riêng (spec §2.2 ý 6). */
function RecoveryList({ items }: { items: MuscleRecoveryStatus[] }) {
  const theme = useTheme();
  const pending = items.filter((item) => item.recovery_status !== 'ready');
  if (items.length === 0 || pending.length === 0) {
    return (
      <AppText variant="meta" color={theme.textMuted}>
        {items.length === 0 ? 'Chưa có dữ liệu phục hồi' : 'Mọi nhóm cơ đã sẵn sàng tập'}
      </AppText>
    );
  }
  return (
    <>
      {pending.map((item) => (
        <RecoveryRow key={item.muscle_group_id} item={item} />
      ))}
    </>
  );
}

function RecoveryBody() {
  const recovery = useMuscleRecovery();
  if (recovery.data) return <RecoveryList items={recovery.data.data} />;
  if (recovery.isError) {
    return <ErrorState message={screenErrorMessage(recovery.error)} onRetry={() => recovery.refetch()} />;
  }
  return <LoadingState />;
}

/** "Phục hồi" (spec §2.2 ý 6): chỉ mount khi có `workout:manage_own`, nên không có quyền thì không gọi API. */
export function RecoverySection() {
  return (
    <View testID="recovery-section">
      <SectionHeader title="Phục hồi" />
      <ReportCard>
        <RecoveryBody />
      </ReportCard>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  name: { flex: 1 },
});
