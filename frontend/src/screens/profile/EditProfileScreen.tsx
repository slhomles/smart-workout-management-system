// Hồ sơ (spec fe-auth §2.1, §2.2 "Sửa hồ sơ", §2.4; phong cách ảnh mẫu 13, nút theo ảnh 08).
import { StyleSheet, View } from 'react-native';

import { GradientButton, Screen, TextField } from '@/components/common';
import { radius, spacing, useTheme } from '@/styles/theme';
import type { Me } from '@/types/auth';

import { AccountHeader } from './AccountHeader';
import { FormAlert } from './FormAlert';
import { MeStates } from './MeStates';
import { useEditProfileForm } from './useEditProfileForm';

/** Chỉ mount khi đã có `me` để khởi tạo ô nhập một lần từ dữ liệu server, không cần `useEffect` đồng bộ. */
function EditProfileForm({ me }: { me: Me }) {
  const theme = useTheme();
  const form = useEditProfileForm(me);
  return (
    <View style={[styles.card, { backgroundColor: theme.surface }]}>
      <TextField
        label="Tên hiển thị"
        value={form.values.display_name}
        onChangeText={form.setValue('display_name')}
        error={form.errors.fields.display_name}
      />
      <TextField
        label="Họ và tên"
        value={form.values.full_name}
        onChangeText={form.setValue('full_name')}
        error={form.errors.fields.full_name}
      />
      <FormAlert message={form.errors.form} />
      <GradientButton label="Lưu" onPress={form.submit} loading={form.isSubmitting} />
    </View>
  );
}

export default function EditProfileScreen() {
  return (
    <Screen header={<AccountHeader title="Hồ sơ" />}>
      <MeStates>{(me) => <EditProfileForm me={me} />}</MeStates>
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: spacing.lg, gap: spacing.lg },
});
