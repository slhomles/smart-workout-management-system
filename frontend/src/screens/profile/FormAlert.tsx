import { AppText } from '@/components/common';
import { useTheme } from '@/styles/theme';

/** Lỗi chung của form (không gắn ô nào), cùng kiểu với màn đăng nhập: chữ `meta` màu `flame`, role `alert`. */
export function FormAlert({ message }: { message: string | null }) {
  const theme = useTheme();
  if (!message) return null;
  return (
    <AppText variant="meta" color={theme.flame} accessibilityRole="alert">
      {message}
    </AppText>
  );
}
