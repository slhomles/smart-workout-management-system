import { Ionicons } from '@expo/vector-icons';
import { Image } from 'expo-image';
import { LinearGradient } from 'expo-linear-gradient';
import { useEffect, useState } from 'react';
import { StyleSheet, View, type DimensionValue } from 'react-native';

import { radius, useTheme } from '@/styles/theme';

import type { IconName } from './FilterTile';

/** Ảnh JPG luân phiên khi bài không có GIF (AGENT_RESOURCES.md §1.2: ~0,8 giây). */
export const FRAME_INTERVAL_MS = 800;

type Props = {
  uri?: string | null;
  frames?: string[];
  size?: DimensionValue;
  aspectRatio?: number;
  fallbackIcon?: IconName;
  rounded?: number;
};

/** Nguồn ảnh hiện tại: GIF/ảnh nếu có, không thì luân phiên các khung JPG. */
function useFrameSource(uri: string | null | undefined, frames: string[] | undefined): string | undefined {
  const [frame, setFrame] = useState(0);
  const hasFrames = !uri && (frames?.length ?? 0) > 1;
  useEffect(() => {
    if (!hasFrames) return undefined;
    const timer = setInterval(() => setFrame((f) => f + 1), FRAME_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [hasFrames]);
  if (uri) return uri;
  return frames && frames.length > 0 ? frames[frame % frames.length] : undefined;
}

/**
 * Ảnh/GIF bài tập. GIF nguồn chỉ 180px nên không phóng quá ~2 lần (AGENT_RESOURCES.md §1.1);
 * thiếu media thì hiện khối gradient kèm icon.
 */
export function MediaThumb({ uri, frames, size = 104, aspectRatio = 1, fallbackIcon = 'barbell', rounded = radius.thumb }: Props) {
  const theme = useTheme();
  const source = useFrameSource(uri, frames);
  const box = { width: size, aspectRatio, borderRadius: rounded };
  if (!source) {
    return (
      <LinearGradient colors={theme.heroGradient} style={[styles.center, box]} accessibilityLabel="Chưa có ảnh">
        <Ionicons name={fallbackIcon} size={36} color={theme.onPrimary} />
      </LinearGradient>
    );
  }
  return (
    <View style={[box, styles.clip, { backgroundColor: theme.surfaceMuted }]}>
      <Image source={{ uri: source }} style={styles.fill} contentFit="contain" transition={150} />
    </View>
  );
}

const styles = StyleSheet.create({
  center: { alignItems: 'center', justifyContent: 'center' },
  clip: { overflow: 'hidden' },
  fill: { width: '100%', height: '100%' },
});
