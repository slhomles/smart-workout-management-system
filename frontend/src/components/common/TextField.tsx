import { StyleSheet, TextInput, View, type KeyboardTypeOptions, type TextInputProps } from 'react-native';

import { fonts, radius, sizes, spacing, typography, useTheme } from '@/styles/theme';

import { AppText } from './AppText';

type Props = {
  label: string;
  value: string;
  onChangeText: (text: string) => void;
  error?: string | null;
  secureTextEntry?: boolean;
  keyboardType?: KeyboardTypeOptions;
  placeholder?: string;
  /** Đơn vị hiện cạnh ô, vd "kg"/"lb". */
  suffix?: string;
  autoCapitalize?: TextInputProps['autoCapitalize'];
};

/**
 * Ô nhập có nhãn (frontend-standards §4, §8.2; cùng phong cách `SearchBar`): ô `pill` nền `surfaceMuted`,
 * nhãn phía trên, lỗi màu `flame` ngay dưới ô. `testID` theo nhãn để test kiểm lỗi nằm đúng ô.
 */
export function TextField({ label, error, suffix, ...inputProps }: Props) {
  const theme = useTheme();
  return (
    <View style={styles.wrap} testID={`field-${label}`}>
      <AppText variant="label">{label}</AppText>
      <View style={[styles.box, { backgroundColor: theme.surfaceMuted }]}>
        <TextInput
          {...inputProps}
          placeholderTextColor={theme.textMuted}
          accessibilityLabel={label}
          style={[styles.input, { color: theme.text }]}
        />
        {suffix ? (
          <AppText variant="meta" color={theme.textMuted}>
            {suffix}
          </AppText>
        ) : null}
      </View>
      {error ? (
        <AppText variant="meta" color={theme.flame}>
          {error}
        </AppText>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  box: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    minHeight: sizes.button,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.xl,
  },
  // Không lấy lineHeight của `body`: TextInput iOS lệch chữ theo chiều dọc khi có lineHeight.
  input: { flex: 1, fontFamily: fonts.regular, fontSize: typography.body.fontSize },
});
