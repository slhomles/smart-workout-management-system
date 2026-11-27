// Màn đăng nhập (spec fe-auth §2.1, §2.2, §2.4). Không có ảnh mẫu riêng; nút theo ảnh 08 (`GradientButton`).
import { router, useLocalSearchParams } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText, GradientButton, Screen, ScreenHeader, TextField } from '@/components/common';
import { radius, sizes, spacing, useTheme } from '@/styles/theme';

import { useLoginForm } from './useLoginForm';

const REGISTER_LINK = 'Chưa có tài khoản? Đăng ký';

// Map thay vì object để `notice` lạ (vd "constructor") không đọc nhầm thuộc tính của Object.
const NOTICE_MESSAGES = new Map<string, string>([
  ['password_changed', 'Đã đổi mật khẩu. Vui lòng đăng nhập lại.'],
  ['registered', 'Đăng ký thành công. Vui lòng đăng nhập.'],
]);

function NoticeBanner() {
  const theme = useTheme();
  const { notice } = useLocalSearchParams<{ notice?: string }>();
  const message = typeof notice === 'string' ? NOTICE_MESSAGES.get(notice) : undefined;
  if (!message) return null;
  return (
    <View style={[styles.notice, { backgroundColor: theme.primarySoft }]}>
      <AppText color={theme.primary}>{message}</AppText>
    </View>
  );
}

export default function LoginScreen() {
  const theme = useTheme();
  const form = useLoginForm();
  return (
    <Screen header={<ScreenHeader title="Đăng nhập" />}>
      <View style={styles.form}>
        <NoticeBanner />
        <TextField
          label="Email"
          value={form.email}
          onChangeText={form.setEmail}
          error={form.errors.fields.email}
          keyboardType="email-address"
          autoCapitalize="none"
        />
        <TextField
          label="Mật khẩu"
          value={form.password}
          onChangeText={form.setPassword}
          error={form.errors.fields.password}
          secureTextEntry
        />
        {form.errors.form ? (
          <AppText variant="meta" color={theme.flame} accessibilityRole="alert">
            {form.errors.form}
          </AppText>
        ) : null}
        <GradientButton label="Đăng nhập" onPress={form.submit} loading={form.isSubmitting} />
        <Pressable
          onPress={() => router.push('/register')}
          accessibilityRole="button"
          accessibilityLabel={REGISTER_LINK}
          style={styles.link}
        >
          <AppText color={theme.link}>{REGISTER_LINK}</AppText>
        </Pressable>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  form: { gap: spacing.lg },
  notice: { borderRadius: radius.card, padding: spacing.lg },
  link: { minHeight: sizes.touch, alignItems: 'center', justifyContent: 'center' },
});
