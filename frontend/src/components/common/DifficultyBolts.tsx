import { Ionicons } from '@expo/vector-icons';
import { StyleSheet, View } from 'react-native';

import { useTheme } from '@/styles/theme';

type Props = { rank: number; max?: number };

/** 1–3 tia sét độ khó (ảnh mẫu 02); `rank` lấy từ `difficulty.rank` của bài/giáo án. */
export function DifficultyBolts({ rank, max = 3 }: Props) {
  const theme = useTheme();
  const filled = Math.max(0, Math.min(rank, max));
  return (
    <View style={styles.row} accessibilityLabel={`Độ khó ${filled}/${max}`}>
      {Array.from({ length: max }, (_, i) => (
        <Ionicons key={i} name="flash" size={18} color={i < filled ? theme.primary : theme.boltOff} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({ row: { flexDirection: 'row', gap: 2 } });
