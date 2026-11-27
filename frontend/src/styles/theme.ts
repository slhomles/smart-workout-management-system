/**
 * Design system theo app mẫu (frontend-standards §8.1, docs/ui-refs/home-workout/). File core.
 * Màn hình CHỈ lấy màu, chữ, khoảng cách, bo góc từ đây; không viết mã màu hay số pixel rời rạc.
 */
import { useColorScheme } from 'react-native';

const brand = {
  primary: '#1E5EFF',
  primaryGradient: ['#19C6FF', '#1E5EFF'] as const,
  heroGradient: ['#2F80FF', '#0B4DFF'] as const,
  orangeGradient: ['#FF9A3D', '#FF6A1F'] as const,
  accentOrange: '#FF7A2F',
  flame: '#FF4D4F',
  badgeYellow: '#FFD84D',
  tagPeach: '#FBE3C4',
  onPrimary: '#FFFFFF',
  link: '#1E5EFF',
  boltOff: '#D5D9E0',
  glass: 'rgba(255,255,255,0.22)', // nút/ô mờ trên nền gradient (ảnh mẫu 01, 10)
  scrim: 'rgba(0,0,0,0.35)', // nút tròn mờ trên ảnh (ảnh mẫu 08)
};

const light = {
  ...brand,
  background: '#F5F6F8',
  surface: '#FFFFFF',
  surfaceMuted: '#EEF1F6',
  primarySoft: '#EEF3FF',
  divider: '#E7E9EE',
  text: '#111318',
  textMuted: '#9A9FA8',
  tooltip: '#3B3F48',
};

const dark: typeof light = {
  ...brand,
  background: '#0F1115',
  surface: '#1A1D23',
  surfaceMuted: '#242832',
  primarySoft: '#1B2A4D',
  divider: '#2C313B',
  text: '#F3F4F6',
  textMuted: '#9AA1AD',
  tooltip: '#E7E9EE',
};

export type Palette = typeof light;
export type LevelCode = 'beginner' | 'intermediate' | 'advanced';

export const levelColors: Record<LevelCode, { bg: string; fg: string; label: string }> = {
  beginner: { bg: '#E8EEFF', fg: '#1E5EFF', label: 'Người bắt đầu' },
  intermediate: { bg: '#FFF1E4', fg: '#FF8A1E', label: 'Trung bình' },
  advanced: { bg: '#FFE9EC', fg: '#F0384F', label: 'Nâng cao' },
};

export const fonts = {
  regular: 'BeVietnamPro_400Regular',
  semibold: 'BeVietnamPro_600SemiBold',
  bold: 'BeVietnamPro_700Bold',
  extrabold: 'BeVietnamPro_800ExtraBold',
};

export const typography = {
  display: { fontFamily: fonts.extrabold, fontSize: 28, lineHeight: 34, textTransform: 'uppercase' as const },
  title: { fontFamily: fonts.bold, fontSize: 22, lineHeight: 28 },
  itemTitle: { fontFamily: fonts.semibold, fontSize: 18, lineHeight: 24 },
  body: { fontFamily: fonts.regular, fontSize: 16, lineHeight: 22 },
  meta: { fontFamily: fonts.regular, fontSize: 15, lineHeight: 20 },
  label: { fontFamily: fonts.semibold, fontSize: 13, lineHeight: 18 },
  button: { fontFamily: fonts.bold, fontSize: 17, lineHeight: 22 },
  number: { fontFamily: fonts.extrabold, fontSize: 40, lineHeight: 46 },
  numberXL: { fontFamily: fonts.extrabold, fontSize: 64, lineHeight: 72 },
};

export const radius = { card: 20, hero: 24, thumb: 20, icon: 12, pill: 999 };
export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 20, section: 32 };
export const sizes = { touch: 44, button: 56, thumb: 104, thumbSmall: 64, tabIcon: 26 };

export const palettes = { light, dark };

export function useTheme(): Palette {
  return useColorScheme() === 'dark' ? dark : light;
}
