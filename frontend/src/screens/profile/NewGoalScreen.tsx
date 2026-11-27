// Đặt mục tiêu (spec fe-auth §2.1, §2.2 "Mục tiêu", §2.4, §4 "Đơn vị đo và Đặt mục tiêu", §6 ý 10, 11; Chip theo
// ảnh mẫu 02, nút theo ảnh 08). Danh mục loại mục tiêu đủ 4 trạng thái: tải, lỗi có "Thử lại", rỗng, có dữ liệu.
import { StyleSheet, View } from 'react-native';

import { EmptyState, ErrorState, GradientButton, LoadingState, Screen, TextField } from '@/components/common';
import { useGoalTypes } from '@/hooks/profile/useGoalTypes';
import { radius, spacing, useTheme } from '@/styles/theme';
import type { UnitSystem } from '@/types/auth';
import type { GoalType } from '@/types/profile';

import { AccountHeader } from './AccountHeader';
import { FormAlert } from './FormAlert';
import { GoalTypePicker } from './GoalTypePicker';
import { MeStates } from './MeStates';
import { screenErrorMessage } from './screen-error';
import { useNewGoalForm } from './useNewGoalForm';

// Cân nặng nhập theo `unit_system` nên đơn vị cạnh ô đổi theo (spec fe-auth §2.4, §6 ý 10).
const WEIGHT_UNIT_SUFFIX: Record<UnitSystem, string> = { metric: 'kg', imperial: 'lb' };

type NewGoalFormProps = { goalTypes: readonly GoalType[]; unitSystem: UnitSystem };

/** Chỉ mount khi đã có danh mục để form giữ nguyên giá trị đang nhập suốt vòng đời màn. */
function NewGoalForm({ goalTypes, unitSystem }: NewGoalFormProps) {
  const theme = useTheme();
  const form = useNewGoalForm(unitSystem);
  return (
    <View style={[styles.card, { backgroundColor: theme.surface }]}>
      <GoalTypePicker
        goalTypes={goalTypes}
        selectedId={form.values.goal_type_id}
        error={form.errors.fields.goal_type_id}
        onSelect={form.selectGoalType}
      />
      <TextField
        label="Cân nặng mục tiêu"
        value={form.values.target_weight}
        onChangeText={form.setText('target_weight')}
        error={form.errors.fields.target_weight_kg}
        suffix={WEIGHT_UNIT_SUFFIX[unitSystem]}
        keyboardType="decimal-pad"
      />
      <TextField
        label="Ngày đạt mục tiêu"
        value={form.values.target_date}
        onChangeText={form.setText('target_date')}
        error={form.errors.fields.target_date}
        placeholder="dd/mm/yyyy"
        keyboardType="numbers-and-punctuation"
      />
      <FormAlert message={form.errors.form} />
      <GradientButton label="Lưu mục tiêu" onPress={form.submit} loading={form.isSubmitting} />
    </View>
  );
}

/** Đã có danh mục thì luôn hiện form, kể cả khi lần tải lại sau đó lỗi, để không mất dữ liệu đang nhập. */
function NewGoalContent({ unitSystem }: { unitSystem: UnitSystem }) {
  const query = useGoalTypes();
  if (query.data) {
    if (query.data.length === 0) return <EmptyState title="Chưa có loại mục tiêu" icon="flag-outline" />;
    return <NewGoalForm goalTypes={query.data} unitSystem={unitSystem} />;
  }
  if (query.isError) return <ErrorState message={screenErrorMessage(query.error)} onRetry={() => query.refetch()} />;
  return <LoadingState />;
}

export default function NewGoalScreen() {
  return (
    <Screen header={<AccountHeader title="Đặt mục tiêu" />}>
      {/* `null` coi như `metric` (spec fe-auth §6 ý 10). */}
      <MeStates>{(me) => <NewGoalContent unitSystem={me.unit_system ?? 'metric'} />}</MeStates>
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: spacing.lg, gap: spacing.lg },
});
