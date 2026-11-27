// 4 tab cố định (frontend-standards §8.3, ảnh mẫu 01). File core: module KHÔNG thêm tab.
import { Ionicons } from '@expo/vector-icons';
import { Redirect } from 'expo-router';
import { Tabs } from 'expo-router/js-tabs';

import { AUTH_REQUIRED } from '@/constants/features';
import { TABS } from '@/constants/tabs';
import { useSession } from '@/store/session';
import { fonts, sizes, useTheme } from '@/styles/theme';

export default function TabsLayout() {
  const theme = useTheme();
  const status = useSession((s) => s.status);
  if (AUTH_REQUIRED && status === 'signedOut') return <Redirect href="/login" />;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: theme.primary,
        tabBarInactiveTintColor: theme.textMuted,
        tabBarStyle: { backgroundColor: theme.surface, borderTopColor: theme.divider, height: 72, paddingTop: 6 },
        tabBarLabelStyle: { fontFamily: fonts.semibold, fontSize: 13 },
      }}
    >
      {TABS.map((tab) => (
        <Tabs.Screen
          key={tab.name}
          name={tab.name}
          options={{
            title: tab.title,
            tabBarIcon: ({ color }) => <Ionicons name={tab.icon} size={sizes.tabIcon} color={typeof color === 'string' ? color : theme.textMuted} />,
          }}
        />
      ))}
    </Tabs>
  );
}
