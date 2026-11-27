import { StyleSheet, View } from 'react-native';

import { AppText, Chip } from '@/components/common';
import { spacing } from '@/styles/theme';
import type { GoalType } from '@/types/profile';

import { FormAlert } from './FormAlert';

const GROUP_LABEL = 'Loại mục tiêu';

type Props = {
  goalTypes: readonly GoalType[];
  selectedId: number | null;
  error: string | undefined;
  onSelect: (goalTypeId: number) => void;
};

/**
 * Chọn loại mục tiêu bằng `Chip` (ảnh mẫu 02; spec fe-auth §4). Chip lấy từ `GET /body/goal-types`, KHÔNG viết
 * cứng id danh mục (spec §6 ý 3). Lỗi hiện ngay dưới nhóm; `testID` theo quy ước `field-<nhãn>` của `TextField`.
 */
export function GoalTypePicker({ goalTypes, selectedId, error, onSelect }: Props) {
  return (
    <View style={styles.wrap} testID={`field-${GROUP_LABEL}`}>
      <AppText variant="label">{GROUP_LABEL}</AppText>
      <View style={styles.chips}>
        {goalTypes.map((type) => (
          <Chip key={type.id} label={type.name} selected={type.id === selectedId} onPress={() => onSelect(type.id)} />
        ))}
      </View>
      <FormAlert message={error ?? null} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
});
