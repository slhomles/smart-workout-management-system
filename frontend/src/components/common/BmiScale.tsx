import { StyleSheet, View } from 'react-native';
import Svg, { Polygon } from 'react-native-svg';

import { radius, spacing, typography, useTheme, type Palette } from '@/styles/theme';
import { formatNumber } from '@/utils/format';

import { AppText } from './AppText';

/**
 * Mốc BMI của thang (fe-dashboard §6 ý 6): chuẩn châu Á 18,5 / 23 / 25 để kim khớp `bmi_category`
 * của server, cộng mốc gầy độ nặng 16 và hai đầu 15, 35.
 */
export const BMI_BOUNDS = [15, 16, 18.5, 23, 25, 30, 35] as const;

const BAND_COUNT = BMI_BOUNDS.length - 1;
const SCALE_MIN = BMI_BOUNDS[0];
const SCALE_MAX = BMI_BOUNDS[6];
const BAR_HEIGHT = spacing.md;
const NEEDLE_SIZE = spacing.md;
const LABEL_HEIGHT = typography.label.lineHeight;

/** Vị trí 0..1 của `bmi` trên thang: 6 dải rộng bằng nhau, nội suy tuyến tính trong từng dải. */
export function bmiScalePosition(bmi: number): number {
  if (bmi <= SCALE_MIN) return 0;
  if (bmi >= SCALE_MAX) return 1;
  // SCALE_MIN < bmi < SCALE_MAX nên mốc đầu tiên lớn hơn bmi luôn có chỉ số 1..BAND_COUNT.
  const band = BMI_BOUNDS.findIndex((bound) => bmi < bound) - 1;
  const lower = BMI_BOUNDS[band] ?? SCALE_MIN;
  const upper = BMI_BOUNDS[band + 1] ?? SCALE_MAX;
  return (band + (bmi - lower) / (upper - lower)) / BAND_COUNT;
}

/** Màu 6 dải mượn token có sẵn (xanh đậm → đỏ, §4 Giao diện); không viết cứng mã màu. */
function bandColors(theme: Palette): string[] {
  return [theme.heroGradient[1], theme.primary, theme.primaryGradient[0], theme.badgeYellow, theme.accentOrange, theme.flame];
}

function percent(fraction: number): `${number}%` {
  return `${fraction * 100}%`;
}

function Needle({ position, color }: { position: number; color: string }) {
  return (
    <View style={[styles.needle, { left: percent(position) }]}>
      <Svg width={NEEDLE_SIZE} height={NEEDLE_SIZE}>
        <Polygon points={`0,0 ${NEEDLE_SIZE},0 ${NEEDLE_SIZE / 2},${NEEDLE_SIZE}`} fill={color} />
      </Svg>
    </View>
  );
}

function BoundLabels({ color }: { color: string }) {
  return (
    <View style={styles.labels}>
      {BMI_BOUNDS.map((bound, i) => (
        // Neo rộng 0 tại mốc, chữ căn giữa tràn ra hai bên để thẳng hàng với ranh giới dải.
        <View key={bound} style={[styles.anchor, { left: percent(i / BAND_COUNT) }]}>
          <AppText variant="label" color={color} numberOfLines={1} style={styles.labelText}>
            {formatNumber(bound, 1)}
          </AppText>
        </View>
      ))}
    </View>
  );
}

/** Thang BMI 6 dải màu có kim tam giác (ảnh mẫu 12). */
export function BmiScale({ bmi }: { bmi: number }) {
  const theme = useTheme();
  return (
    <View accessible accessibilityLabel={`Thang BMI, giá trị ${formatNumber(bmi, 1)}`} style={styles.box}>
      <View style={styles.needleTrack}>
        <Needle position={bmiScalePosition(bmi)} color={theme.text} />
      </View>
      <View style={styles.bar}>
        {bandColors(theme).map((color) => (
          <View key={color} style={[styles.band, { backgroundColor: color }]} />
        ))}
      </View>
      <BoundLabels color={theme.text} />
    </View>
  );
}

const styles = StyleSheet.create({
  box: { gap: spacing.xs, paddingHorizontal: spacing.md },
  needleTrack: { height: NEEDLE_SIZE },
  needle: { position: 'absolute', top: 0, marginLeft: -NEEDLE_SIZE / 2 },
  bar: { flexDirection: 'row', gap: spacing.xs, height: BAR_HEIGHT },
  band: { flex: 1, borderRadius: radius.icon },
  labels: { height: LABEL_HEIGHT },
  anchor: { position: 'absolute', top: 0, width: 0, alignItems: 'center' },
  labelText: { width: spacing.section * 2, textAlign: 'center' },
});
