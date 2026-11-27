import { LinearGradient } from 'expo-linear-gradient';
import { ActivityIndicator, Pressable, StyleSheet, View } from 'react-native';

import { radius, sizes, spacing, useTheme } from '@/styles/theme';

import { AppText } from './AppText';

type Props = {
  label: string;
  onPress: () => void;
  variant?: 'gradient' | 'white' | 'ghost';
  loading?: boolean;
  disabled?: boolean;
};

/**
 * Nút viên thuốc (ảnh mẫu 08: gradient cyan → xanh; 01: nút trắng chữ xanh trên thẻ gradient;
 * 10: `ghost` nền trắng mờ trên màn xanh).
 */
export function GradientButton({ label, onPress, variant = 'gradient', loading = false, disabled = false }: Props) {
  const theme = useTheme();
  const isGradient = variant === 'gradient';
  const textColor = isGradient || variant === 'ghost' ? theme.onPrimary : theme.primary;
  const content = loading ? <ActivityIndicator color={textColor} /> : <AppText variant="button" color={textColor}>{label}</AppText>;
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      accessibilityRole="button"
      accessibilityLabel={label}
      style={({ pressed }) => [styles.wrap, { opacity: disabled ? 0.5 : pressed ? 0.85 : 1 }]}
    >
      {isGradient ? (
        <LinearGradient colors={theme.primaryGradient} start={{ x: 0, y: 0.5 }} end={{ x: 1, y: 0.5 }} style={styles.inner}>
          {content}
        </LinearGradient>
      ) : (
        <View style={[styles.inner, { backgroundColor: variant === 'white' ? theme.onPrimary : theme.glass }]}>{content}</View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  wrap: { borderRadius: radius.pill, overflow: 'hidden' },
  inner: {
    minHeight: sizes.button,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
    borderRadius: radius.pill,
  },
});
