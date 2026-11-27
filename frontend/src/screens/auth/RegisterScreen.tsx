// Màn đăng ký (spec fe-auth §2.1, §2.2, §2.4). Không có ảnh mẫu riêng; nút theo ảnh 08 (`GradientButton`).
import { router } from 'expo-router';
import type { ComponentProps } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText, GradientButton, Screen, ScreenHeader, TextField } from '@/components/common';
import { sizes, spacing, useTheme } from '@/styles/theme';

import type { RegisterField } from './register-errors';
import { useRegisterForm, type RegisterForm } from './useRegisterForm';

const LOGIN_LINK = 'Đã có tài khoản? Đăng nhập';

type FieldConfig = { field: RegisterField; label: string } & Pick<
  ComponentProps<typeof TextField>,
  'keyboardType' | 'autoCapitalize' | 'secureTextEntry'
>;

// Nhãn theo spec fe-auth §2.4; cũng là `accessibilityLabel` và `testID` (`field-<nhãn>`) của ô.
const FIELDS: readonly FieldConfig[] = [
  { field: 'email', label: 'Email', keyboardType: 'email-address', autoCapitalize: 'none' },
  { field: 'display_name', label: 'Tên hiển thị' },
  { field: 'full_name', label: 'Họ và tên' },
  { field: 'password', label: 'Mật khẩu', secureTextEntry: true },
  { field: 'password_confirm', label: 'Nhập lại mật khẩu', secureTextEntry: true },
];

function RegisterFields({ form }: { form: RegisterForm }) {
  return (
    <>
      {FIELDS.map(({ field, ...inputProps }) => (
        <TextField
          key={field}
          {...inputProps}
          value={form.values[field]}
          onChangeText={form.setValue(field)}
          error={form.errors.fields[field]}
        />
      ))}
    </>
  );
}

export default function RegisterScreen() {
  const theme = useTheme();
  const form = useRegisterForm();
  return (
    <Screen header={<ScreenHeader title="Đăng ký" />}>
      <View style={styles.form}>
        <RegisterFields form={form} />
        {form.errors.form ? (
          <AppText variant="meta" color={theme.flame} accessibilityRole="alert">
            {form.errors.form}
          </AppText>
        ) : null}
        <GradientButton label="Đăng ký" onPress={form.submit} loading={form.isSubmitting} />
        <Pressable
          onPress={() => router.replace('/login')}
          accessibilityRole="button"
          accessibilityLabel={LOGIN_LINK}
          style={styles.link}
        >
          <AppText color={theme.link}>{LOGIN_LINK}</AppText>
        </Pressable>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  form: { gap: spacing.lg },
  link: { minHeight: sizes.touch, alignItems: 'center', justifyContent: 'center' },
});
