import { StyleSheet, View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

import { typography, useTheme } from '@/styles/theme';

import { AppText } from './AppText';

type Props = { remaining: number; total: number; size?: number; stroke?: number };

/** Vòng đếm ngược (ảnh mẫu 09): cung xanh theo tỉ lệ thời gian còn lại, số lớn ở giữa. */
export function CountdownRing({ remaining, total, size = 160, stroke = 12 }: Props) {
  const theme = useTheme();
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  const ratio = total > 0 ? Math.max(0, Math.min(remaining / total, 1)) : 0;
  return (
    <View style={{ width: size, height: size }} accessibilityLabel={`Còn ${remaining} giây`}>
      <Svg width={size} height={size}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={theme.surfaceMuted} strokeWidth={stroke} fill="none" />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={theme.primary}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={circumference * (1 - ratio)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      <View style={StyleSheet.absoluteFill}>
        <View style={styles.center}>
          <AppText style={typography.numberXL}>{remaining}</AppText>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({ center: { flex: 1, alignItems: 'center', justifyContent: 'center' } });
