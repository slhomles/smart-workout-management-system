import { StyleSheet, View } from 'react-native';

import { AppText } from '@/components/common';
import { spacing, useTheme } from '@/styles/theme';

type Props = { label: string; value: string; testID?: string };

/** Một dòng "nhãn — giá trị" trong thẻ (ảnh 11, 12: "Nặng nhất 60", "Height 157 cm"). */
export function MetricRow({ label, value, testID }: Props) {
  const theme = useTheme();
  return (
    <View testID={testID} style={styles.row}>
      <AppText variant="body" color={theme.textMuted}>
        {label}
      </AppText>
      <AppText variant="itemTitle">{value}</AppText>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
});
