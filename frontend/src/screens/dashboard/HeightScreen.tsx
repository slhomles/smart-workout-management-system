// Chiều cao (spec fe-dashboard §2.1, §2.2 "Chiều cao", §2.4, §6 ý 8, 10; dòng chiều cao theo ảnh mẫu 12, nút theo
// ảnh 08). Trạng thái của `GET /body/profile`: tải, lỗi có "Thử lại", có dữ liệu. Không có trạng thái rỗng vì
// `/body/profile` luôn trả một resource (chưa tạo hồ sơ thì các field là `null`, ô để trống).
import { StyleSheet, View } from 'react-native';

import { ErrorState, GradientButton, LoadingState, Screen, TextField } from '@/components/common';
import { useBodyProfile } from '@/hooks/dashboard/useBodyProfile';
import { AccountHeader } from '@/screens/profile/AccountHeader';
import { FormAlert } from '@/screens/profile/FormAlert';
import { screenErrorMessage } from '@/screens/profile/screen-error';
import { radius, spacing, useTheme } from '@/styles/theme';
import type { BodyProfile } from '@/types/dashboard';

import { useHeightForm } from './useHeightForm';

/** Chỉ mount khi đã có hồ sơ để ô được điền sẵn một lần và giữ nguyên giá trị đang nhập. */
function HeightForm({ profile }: { profile: BodyProfile }) {
  const theme = useTheme();
  const form = useHeightForm(profile);
  return (
    <View style={[styles.card, { backgroundColor: theme.surface }]}>
      <TextField
        label="Chiều cao (cm)"
        value={form.height}
        onChangeText={form.setHeight}
        error={form.errors.fields.height_cm}
        keyboardType="decimal-pad"
      />
      <FormAlert message={form.errors.form} />
      <GradientButton label="Lưu" onPress={form.submit} loading={form.isSubmitting} />
    </View>
  );
}

/** Đã có hồ sơ thì luôn hiện form, kể cả khi lần tải lại sau đó lỗi, để không mất dữ liệu đang nhập. */
function HeightContent() {
  const query = useBodyProfile();
  if (query.data) return <HeightForm profile={query.data} />;
  if (query.isError) return <ErrorState message={screenErrorMessage(query.error)} onRetry={() => query.refetch()} />;
  return <LoadingState />;
}

export default function HeightScreen() {
  return (
    <Screen header={<AccountHeader title="Chiều cao" />}>
      <HeightContent />
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: spacing.lg, gap: spacing.lg },
});
