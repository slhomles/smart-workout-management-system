import { StyleSheet, View } from 'react-native';

import { GradientButton } from '@/components/common';
import { FormAlert } from '@/screens/profile/FormAlert';
import { spacing } from '@/styles/theme';

import { useExportWeeklyReport } from './useExportWeeklyReport';

/** Nút "Xuất báo cáo tuần" (chỉ mount khi có `report:export_own`); lỗi hiện ngay trên nút, không điều hướng. */
export function ExportReportButton() {
  const { exportReport, isPending, error } = useExportWeeklyReport();
  return (
    <View style={styles.box}>
      <FormAlert message={error} />
      <GradientButton label="Xuất báo cáo tuần" onPress={exportReport} loading={isPending} />
    </View>
  );
}

const styles = StyleSheet.create({
  box: { gap: spacing.sm },
});
