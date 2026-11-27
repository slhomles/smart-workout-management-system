// Giữ chỗ cho tab "Cá nhân". Module `fe-auth` thay bằng màn tài khoản thật (frontend-standards §8.3).
import { router } from 'expo-router';
import { View } from 'react-native';

import { EmptyState, Screen, ScreenHeader, SettingsRow } from '@/components/common';

export default function ProfileScreen() {
  return (
    <Screen header={<ScreenHeader title="Cá nhân" />}>
      <EmptyState title="Tài khoản đang được xây dựng" message="Hồ sơ, mục tiêu, đơn vị đo, thiết bị, đổi mật khẩu." icon="person-outline" />
      {__DEV__ && (
        <View>
          <SettingsRow icon="color-palette" iconColor="#7B4DFF" label="Xem bộ component (dev)" onPress={() => router.push('/dev/components')} />
        </View>
      )}
    </Screen>
  );
}
