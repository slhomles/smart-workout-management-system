// Đổi mật khẩu (spec fe-auth §2.1, §2.2 "Đổi mật khẩu", §2.4; nút theo ảnh mẫu 08). Màn dạng form: trạng thái tải
// là `GradientButton loading`, trạng thái lỗi là thông điệp tại form (spec fe-auth §6 ý 14).
import { StyleSheet, View } from 'react-native';

import { GradientButton, Screen, TextField } from '@/components/common';
import { radius, spacing, useTheme } from '@/styles/theme';

import { AccountHeader } from './AccountHeader';
import type { ChangePasswordField } from './change-password-errors';
import { FormAlert } from './FormAlert';
import { useChangePasswordForm } from './useChangePasswordForm';

// Nhãn theo spec fe-auth §2.4; cũng là `accessibilityLabel` và `testID` (`field-<nhãn>`) của ô.
const FIELDS: readonly { field: ChangePasswordField; label: string }[] = [
  { field: 'current_password', label: 'Mật khẩu hiện tại' },
  { field: 'new_password', label: 'Mật khẩu mới' },
  { field: 'new_password_confirm', label: 'Nhập lại mật khẩu mới' },
];

export default function ChangePasswordScreen() {
  const theme = useTheme();
  const form = useChangePasswordForm();
  return (
    <Screen header={<AccountHeader title="Đổi mật khẩu" />}>
      <View style={[styles.card, { backgroundColor: theme.surface }]}>
        {FIELDS.map(({ field, label }) => (
          <TextField
            key={field}
            label={label}
            value={form.values[field]}
            onChangeText={form.setValue(field)}
            error={form.errors.fields[field]}
            secureTextEntry
            autoCapitalize="none"
          />
        ))}
        <FormAlert message={form.errors.form} />
        <GradientButton label="Đổi mật khẩu" onPress={form.submit} loading={form.isSubmitting} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: spacing.lg, gap: spacing.lg },
});
