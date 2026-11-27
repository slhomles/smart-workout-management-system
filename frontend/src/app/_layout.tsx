// Layout gốc: font, React Query, phiên đăng nhập (frontend-standards §2). File core.
import {
  BeVietnamPro_400Regular,
  BeVietnamPro_600SemiBold,
  BeVietnamPro_700Bold,
  BeVietnamPro_800ExtraBold,
  useFonts,
} from '@expo-google-fonts/be-vietnam-pro';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Stack, router } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { setSessionExpiredHandler } from '@/services/api/client';
import { useSession } from '@/store/session';

SplashScreen.preventAutoHideAsync().catch(() => undefined);

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    BeVietnamPro_400Regular,
    BeVietnamPro_600SemiBold,
    BeVietnamPro_700Bold,
    BeVietnamPro_800ExtraBold,
  });
  const hydrate = useSession((s) => s.hydrate);
  const markExpired = useSession((s) => s.markExpired);

  useEffect(() => {
    hydrate().catch(() => undefined);
    setSessionExpiredHandler(() => {
      markExpired();
      queryClient.clear();
      router.replace('/login');
    });
  }, [hydrate, markExpired]);

  useEffect(() => {
    if (fontsLoaded) SplashScreen.hideAsync().catch(() => undefined);
  }, [fontsLoaded]);

  if (!fontsLoaded) return null;
  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <StatusBar style="auto" />
        <Stack screenOptions={{ headerShown: false }} />
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}
