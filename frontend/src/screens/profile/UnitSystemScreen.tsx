// Đơn vị đo (spec fe-auth §2.1, §2.2 "Đơn vị đo", §4; phong cách ảnh mẫu 13, Chip theo ảnh 02).
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { AppText, Chip, Screen } from '@/components/common';
import { radius, spacing, useTheme } from '@/styles/theme';
import type { Me, UnitSystem } from '@/types/auth';

import { AccountHeader } from './AccountHeader';
import { FormAlert } from './FormAlert';
import { unitSystemLabel } from './labels';
import { MeStates } from './MeStates';
import { useUnitSystem } from './useUnitSystem';

const UNIT_SYSTEMS: readonly UnitSystem[] = ['metric', 'imperial'];

/** Chip được chọn luôn theo `me` trong cache; `null` coi như `metric` (spec fe-auth §6 ý 10). */
function UnitSystemOptions({ me }: { me: Me }) {
  const theme = useTheme();
  const current = me.unit_system ?? 'metric';
  const { select, isPending, error } = useUnitSystem(current);
  return (
    <View style={[styles.card, { backgroundColor: theme.surface }]}>
      <AppText color={theme.textMuted}>Cân nặng và số đo sẽ hiển thị theo hệ đơn vị bạn chọn.</AppText>
      <View style={styles.chips}>
        {UNIT_SYSTEMS.map((unit) => (
          <Chip
            key={unit}
            label={unitSystemLabel(unit)}
            selected={unit === current}
            onPress={() => select(unit)}
          />
        ))}
      </View>
      {isPending ? <ActivityIndicator color={theme.primary} /> : null}
      <FormAlert message={error} />
    </View>
  );
}

export default function UnitSystemScreen() {
  return (
    <Screen header={<AccountHeader title="Đơn vị đo" />}>
      <MeStates>{(me) => <UnitSystemOptions me={me} />}</MeStates>
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: spacing.lg, gap: spacing.lg },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
});
