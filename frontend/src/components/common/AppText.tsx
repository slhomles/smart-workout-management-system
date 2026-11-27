import { Text, type TextProps } from 'react-native';

import { typography, useTheme } from '@/styles/theme';

export type TextVariant = keyof typeof typography;

type Props = TextProps & { variant?: TextVariant; color?: string; align?: 'left' | 'center' | 'right' };

/** Chữ theo thang `typography` (frontend-standards §8.1); mặc định màu `text` của theme. */
export function AppText({ variant = 'body', color, align, style, ...rest }: Props) {
  const theme = useTheme();
  return <Text {...rest} style={[typography[variant], { color: color ?? theme.text, textAlign: align }, style]} />;
}
