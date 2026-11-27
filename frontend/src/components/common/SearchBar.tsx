import { Ionicons } from '@expo/vector-icons';
import { Pressable, StyleSheet, TextInput, View } from 'react-native';

import { fonts, radius, sizes, spacing, useTheme } from '@/styles/theme';

import { AppText } from './AppText';

type Props = {
  value: string;
  onChangeText: (text: string) => void;
  placeholder?: string;
  onCancel?: () => void;
  onPress?: () => void;
};

/** Ô tìm kiếm viên thuốc nền xám (ảnh mẫu 01, 06). `onPress` dùng khi ô chỉ là lối vào màn tìm kiếm. */
export function SearchBar({ value, onChangeText, placeholder = 'Tìm kiếm bài tập, giáo án...', onCancel, onPress }: Props) {
  const theme = useTheme();
  return (
    <View style={styles.row}>
      <Pressable
        onPress={onPress}
        disabled={!onPress}
        style={[styles.box, { backgroundColor: theme.surfaceMuted }]}
        accessibilityRole={onPress ? 'search' : undefined}
      >
        <Ionicons name="search" size={22} color={theme.textMuted} />
        <TextInput
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={theme.textMuted}
          editable={!onPress}
          pointerEvents={onPress ? 'none' : 'auto'}
          style={[styles.input, { color: theme.text }]}
          accessibilityLabel="Ô tìm kiếm"
          returnKeyType="search"
        />
      </Pressable>
      {onCancel && (
        <Pressable onPress={onCancel} hitSlop={8} accessibilityRole="button">
          <AppText color={theme.link}>Huỷ</AppText>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
  box: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    minHeight: sizes.touch + 8,
    borderRadius: radius.pill,
    paddingHorizontal: spacing.lg,
  },
  input: { flex: 1, fontFamily: fonts.regular, fontSize: 16 },
});
