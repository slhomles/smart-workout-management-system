// Ghi cân nặng (spec fe-dashboard §2.1, §2.2 "Ghi cân nặng", §2.4, §6 ý 8, 9; nút theo ảnh mẫu 08).
// Chỉ cần `GET /auth/me` để biết đơn vị nhập: tải và lỗi có "Thử lại" do `MeStates` hiện.
import { StyleSheet, View } from 'react-native';

import { GradientButton, Screen, TextField } from '@/components/common';
import { AccountHeader } from '@/screens/profile/AccountHeader';
import { FormAlert } from '@/screens/profile/FormAlert';
import { MeStates } from '@/screens/profile/MeStates';
import { radius, spacing, useTheme } from '@/styles/theme';
import type { UnitSystem } from '@/types/auth';

import { useRecordWeightForm } from './useRecordWeightForm';

// Cân nặng nhập theo `unit_system` nên đơn vị cạnh ô đổi theo (spec §2.4, §6 ý 8).
const WEIGHT_UNIT_SUFFIX: Record<UnitSystem, string> = { metric: 'kg', imperial: 'lb' };

function RecordWeightForm({ unitSystem }: { unitSystem: UnitSystem }) {
  const theme = useTheme();
  const form = useRecordWeightForm(unitSystem);
  return (
    <View style={[styles.card, { backgroundColor: theme.surface }]}>
      <TextField
        label="Cân nặng"
        value={form.values.weight}
        onChangeText={form.setText('weight')}
        error={form.errors.fields.weight_kg}
        suffix={WEIGHT_UNIT_SUFFIX[unitSystem]}
        keyboardType="decimal-pad"
      />
      <TextField
        label="Tỷ lệ mỡ (%)"
        value={form.values.body_fat}
        onChangeText={form.setText('body_fat')}
        error={form.errors.fields.body_fat_pct}
        keyboardType="decimal-pad"
      />
      <FormAlert message={form.errors.form} />
      <GradientButton label="Lưu" onPress={form.submit} loading={form.isSubmitting} />
    </View>
  );
}

export default function RecordWeightScreen() {
  return (
    <Screen header={<AccountHeader title="Ghi cân nặng" />}>
      {/* `null` coi như `metric` (spec §6 ý 8). */}
      <MeStates>{(me) => <RecordWeightForm unitSystem={me.unit_system ?? 'metric'} />}</MeStates>
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: spacing.lg, gap: spacing.lg },
});
