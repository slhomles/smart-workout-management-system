// Tab "Cá nhân" (spec fe-auth §2.1, §4 "Tab Cá nhân"; ảnh mẫu 13): thẻ tài khoản và các dòng cài đặt.
import { router } from 'expo-router';
import { View } from 'react-native';

import { ErrorState, LoadingState, Screen, ScreenHeader, SettingsRow } from '@/components/common';
import { useLogout } from '@/hooks/auth/useLogout';
import { useMe } from '@/hooks/auth/useMe';
import { getErrorMessage } from '@/services/api/errors';
import { useTheme } from '@/styles/theme';

import { AccountCard } from './AccountCard';
import { ProfileSettings } from './ProfileSettings';

type MeQuery = ReturnType<typeof useMe>;

/**
 * Không có trạng thái rỗng vì `GET /auth/me` luôn trả một resource (spec fe-auth §6 ý 14). Đã có dữ liệu thì
 * hiện thẻ, kể cả khi lần tải lại sau đó lỗi, để thẻ và các dòng cài đặt luôn đi cùng nhau.
 */
function AccountSection({ me }: { me: MeQuery }) {
  if (me.data) return <AccountCard me={me.data} />;
  if (me.isError) return <ErrorState message={getErrorMessage(me.error)} onRetry={() => me.refetch()} />;
  return <LoadingState />;
}

export default function ProfileScreen() {
  const theme = useTheme();
  const me = useMe();
  const { logout } = useLogout();
  return (
    <Screen header={<ScreenHeader title="Cá nhân" />}>
      <AccountSection me={me} />
      <ProfileSettings me={me.data} onLogout={logout} />
      {__DEV__ && (
        <View>
          <SettingsRow
            icon="color-palette"
            iconColor={theme.primary}
            label="Xem bộ component (dev)"
            onPress={() => router.push('/dev/components')}
          />
        </View>
      )}
    </Screen>
  );
}
