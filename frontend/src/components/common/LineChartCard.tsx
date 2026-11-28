import { useState } from 'react';
import { Pressable, StyleSheet, View, type LayoutChangeEvent } from 'react-native';
import Svg, { Line, Polyline } from 'react-native-svg';

import { radius, sizes, spacing, typography, useTheme } from '@/styles/theme';
import { formatNumber } from '@/utils/format';

import { AppText } from './AppText';
import { EmptyState } from './StateViews';

export type ChartPoint = { label: string; value: number };
type Domain = { min: number; max: number };
type Props = { points: ChartPoint[]; formatValue?: (v: number) => string; emptyText?: string };

const DEFAULT_EMPTY_TEXT = 'Chưa có dữ liệu cân nặng';
// Kích thước vẽ suy từ token: cao 4 vùng bấm, chừa 1 vùng bấm phía trên cho bong bóng giá trị.
const CHART_HEIGHT = sizes.touch * 4;
const PLOT_TOP = sizes.touch;
const PLOT_BOTTOM = CHART_HEIGHT - sizes.touch / 2;
const GRID_LINE_COUNT = 5;
const LINE_WIDTH = spacing.xs / 2;
const DOT_SIZE = spacing.md;
const GRID_DASH = `${LINE_WIDTH} ${spacing.xs}`;
// Neo nhãn/bong bóng có bề rộng cố định để chữ không bị ép xuống dòng khi căn giữa tại một điểm.
const LABEL_ANCHOR_WIDTH = sizes.touch;
const BUBBLE_ANCHOR_WIDTH = sizes.thumb;

/** Miền trục Y: đệm 10% biên độ mỗi phía; mọi giá trị bằng nhau thì ±1 để đường không dính mép. */
export function chartDomain(values: number[]): Domain | null {
  if (values.length === 0) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  if (min === max) return { min: min - 1, max: max + 1 };
  const pad = (max - min) * 0.1;
  return { min: min - pad, max: max + pad };
}

function xFraction(index: number, count: number): number {
  return count > 1 ? index / (count - 1) : 0.5;
}

function yPixel(value: number, domain: Domain): number {
  const ratio = (value - domain.min) / (domain.max - domain.min);
  return PLOT_BOTTOM - ratio * (PLOT_BOTTOM - PLOT_TOP);
}

function percent(fraction: number): `${number}%` {
  return `${fraction * 100}%`;
}

/** Điểm chọn gắn với bộ điểm hiện tại: bộ điểm đổi (vd đổi khoảng thời gian) thì về điểm cuối. */
function useSelectedIndex(points: ChartPoint[]): [number, (index: number) => void] {
  const key = points.map((p) => `${p.label}=${p.value}`).join('|');
  const [selection, setSelection] = useState<{ key: string; index: number } | null>(null);
  const index = selection?.key === key ? selection.index : points.length - 1;
  return [index, (next) => setSelection({ key, index: next })];
}

function ChartLines({ width, points, domain }: { width: number; points: ChartPoint[]; domain: Domain }) {
  const theme = useTheme();
  const gridStep = (PLOT_BOTTOM - PLOT_TOP) / (GRID_LINE_COUNT - 1);
  const gridYs = Array.from({ length: GRID_LINE_COUNT }, (_, i) => PLOT_TOP + i * gridStep);
  const path = points.map((p, i) => `${xFraction(i, points.length) * width},${yPixel(p.value, domain)}`).join(' ');
  return (
    <Svg testID="line-chart-svg" width={width} height={CHART_HEIGHT} style={StyleSheet.absoluteFill}>
      {gridYs.map((y) => (
        <Line key={y} x1={0} x2={width} y1={y} y2={y} stroke={theme.divider} strokeWidth={LINE_WIDTH} strokeDasharray={GRID_DASH} />
      ))}
      <Polyline points={path} fill="none" stroke={theme.primary} strokeWidth={LINE_WIDTH} strokeLinejoin="round" />
    </Svg>
  );
}

type DotProps = { x: number; y: number; label: string; isSelected: boolean; onPress: () => void };

function ChartDot({ x, y, label, isSelected, onPress }: DotProps) {
  const theme = useTheme();
  const fill = isSelected ? theme.primary : theme.surface;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: isSelected }}
      style={[styles.dotTouch, { left: percent(x), top: y - sizes.touch / 2 }]}
    >
      <View style={[styles.dot, { borderColor: theme.primary, backgroundColor: fill }]} />
    </Pressable>
  );
}

function ValueBubble({ x, y, text }: { x: number; y: number; text: string }) {
  const theme = useTheme();
  return (
    <View style={[styles.bubbleAnchor, { left: percent(x), bottom: CHART_HEIGHT - y + DOT_SIZE }]}>
      <View accessibilityLabel="Giá trị đang chọn" style={[styles.bubble, { backgroundColor: theme.tooltip }]}>
        <AppText variant="label" color={theme.onPrimary}>
          {text}
        </AppText>
      </View>
    </View>
  );
}

function AxisLabels({ labels }: { labels: string[] }) {
  const theme = useTheme();
  return (
    <View style={styles.axis}>
      {labels.map((label, i) => (
        <View key={`${label}-${i}`} style={[styles.labelAnchor, { left: percent(xFraction(i, labels.length)) }]}>
          <AppText variant="label" color={theme.textMuted} numberOfLines={1}>
            {label}
          </AppText>
        </View>
      ))}
    </View>
  );
}

/** Biểu đồ đường có lưới chấm, điểm bấm được và bong bóng giá trị (ảnh mẫu 12). */
export function LineChartCard({ points, formatValue = (v) => formatNumber(v), emptyText = DEFAULT_EMPTY_TEXT }: Props) {
  const [width, setWidth] = useState(0);
  const [selectedIndex, select] = useSelectedIndex(points);
  const domain = chartDomain(points.map((p) => p.value));
  const selected = points[selectedIndex];
  if (!domain || !selected) return <EmptyState title={emptyText} icon="stats-chart-outline" />;
  const count = points.length;
  const onLayout = (e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width);
  return (
    <View>
      <View testID="line-chart-plot" style={styles.plot} onLayout={onLayout}>
        {width > 0 && <ChartLines width={width} points={points} domain={domain} />}
        {points.map((p, i) => (
          <ChartDot
            key={`${p.label}-${i}`}
            x={xFraction(i, count)}
            y={yPixel(p.value, domain)}
            label={`${p.label}: ${formatValue(p.value)}`}
            isSelected={i === selectedIndex}
            onPress={() => select(i)}
          />
        ))}
        <ValueBubble x={xFraction(selectedIndex, count)} y={yPixel(selected.value, domain)} text={formatValue(selected.value)} />
      </View>
      <AxisLabels labels={points.map((p) => p.label)} />
    </View>
  );
}

const styles = StyleSheet.create({
  // Lề ngang nửa vùng bấm để điểm đầu/cuối vẫn bấm trọn trong thẻ.
  plot: { height: CHART_HEIGHT, marginHorizontal: sizes.touch / 2 },
  dotTouch: {
    position: 'absolute',
    width: sizes.touch,
    height: sizes.touch,
    marginLeft: -sizes.touch / 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dot: { width: DOT_SIZE, height: DOT_SIZE, borderRadius: radius.pill, borderWidth: LINE_WIDTH },
  bubbleAnchor: {
    position: 'absolute',
    width: BUBBLE_ANCHOR_WIDTH,
    marginLeft: -BUBBLE_ANCHOR_WIDTH / 2,
    alignItems: 'center',
    pointerEvents: 'none',
  },
  bubble: { borderRadius: radius.pill, paddingHorizontal: spacing.sm, paddingVertical: spacing.xs },
  axis: { height: typography.label.lineHeight, marginHorizontal: sizes.touch / 2, marginTop: spacing.xs },
  labelAnchor: { position: 'absolute', top: 0, width: LABEL_ANCHOR_WIDTH, marginLeft: -LABEL_ANCHOR_WIDTH / 2, alignItems: 'center' },
});
