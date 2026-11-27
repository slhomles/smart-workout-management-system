import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import type { ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import { radius, spacing, useTheme } from '@/styles/theme';

import { AppText } from './AppText';
import type { IconName } from './FilterTile';
import { GradientButton } from './GradientButton';

export type HeroStat = { icon: IconName; value: string; label: string };

type Props = {
  title: string;
  tag?: string;
  subtitle?: string;
  stats?: HeroStat[];
  ctaLabel?: string;
  onPress?: () => void;
  tone?: 'blue' | 'orange';
  media?: ReactNode;
};

/** Thẻ lớn gradient (ảnh mẫu 01, 07): nhãn góc, tiêu đề VIẾT HOA, lưới 2×2 thông số, nút trắng. */
export function HeroCard({ title, tag, subtitle, stats = [], ctaLabel, onPress, tone = 'blue', media }: Props) {
  const theme = useTheme();
  const colors = tone === 'orange' ? theme.orangeGradient : theme.heroGradient;
  return (
    <View style={styles.wrap}>
      {tag && (
        <View style={[styles.tag, { backgroundColor: theme.tagPeach }]}>
          <AppText variant="label" color="#111318">
            {tag.toUpperCase()}
          </AppText>
        </View>
      )}
      <LinearGradient colors={colors} start={{ x: 0, y: 0 }} end={{ x: 1, y: 1 }} style={styles.card}>
        {media && <View style={styles.media}>{media}</View>}
        <AppText variant="display" color={theme.onPrimary} style={styles.title}>
          {title}
        </AppText>
        {subtitle && <AppText color={theme.onPrimary}>{subtitle}</AppText>}
        {stats.length > 0 && (
          <View style={styles.grid}>
            {stats.map((s) => (
              <View key={s.label} style={styles.stat}>
                <View style={[styles.statIcon, { backgroundColor: theme.glass }]}>
                  <Ionicons name={s.icon} size={22} color={theme.onPrimary} />
                </View>
                <View>
                  <AppText variant="itemTitle" color={theme.onPrimary}>
                    {s.value}
                  </AppText>
                  <AppText variant="meta" color={theme.onPrimary} style={styles.dim}>
                    {s.label}
                  </AppText>
                </View>
              </View>
            ))}
          </View>
        )}
        {ctaLabel && onPress && <GradientButton label={ctaLabel} onPress={onPress} variant="white" />}
      </LinearGradient>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingTop: spacing.md },
  tag: {
    position: 'absolute',
    top: 0,
    left: spacing.xl,
    zIndex: 1,
    borderRadius: radius.icon,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  card: { borderRadius: radius.hero, padding: spacing.xl, paddingTop: spacing.section, gap: spacing.lg, overflow: 'hidden' },
  media: { position: 'absolute', right: 0, bottom: 0, top: 0, width: '45%' },
  title: { maxWidth: '65%' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', rowGap: spacing.md },
  stat: { width: '50%', flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  statIcon: { width: 40, height: 40, borderRadius: radius.icon, alignItems: 'center', justifyContent: 'center' },
  dim: { opacity: 0.75 },
});
