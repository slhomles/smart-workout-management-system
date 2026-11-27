// Màn DEV để duyệt bộ component theo ảnh mẫu. Dữ liệu ở đây là minh hoạ, KHÔNG dùng lại trong màn thật.
import { router } from 'expo-router';
import { useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';

import {
  buildWeek,
  Chip,
  CountdownRing,
  FilterTile,
  GradientButton,
  HeroCard,
  LevelChip,
  ListItem,
  MediaThumb,
  Screen,
  ScreenHeader,
  SearchBar,
  SectionHeader,
  SettingsRow,
  StatCard,
  WeekStrip,
} from '@/components/common';
import { radius, spacing, useTheme } from '@/styles/theme';

const MUSCLES = ['Ngực', 'Lưng', 'Chân', 'Vai', 'Tay'];

function CardsSection() {
  const theme = useTheme();
  return (
    <View style={styles.gap}>
      <View style={[styles.card, { backgroundColor: theme.surface }]}>
        <SectionHeader title="Mục tiêu tuần" />
        <WeekStrip days={buildWeek(new Date())} showLabels={false} />
      </View>
      <HeroCard
        tag="Tuỳ chỉnh cho bạn"
        title="Toàn thân cơ bản"
        stats={[
          { icon: 'calendar', value: '45–60 phút', label: 'Mỗi buổi' },
          { icon: 'stats-chart', value: 'Trung bình', label: 'Cấp độ' },
          { icon: 'body', value: 'Toàn thân', label: 'Nhóm cơ' },
          { icon: 'barbell', value: 'Tạ đòn', label: 'Thiết bị' },
        ]}
        ctaLabel="BẮT ĐẦU NGÀY 1"
        onPress={() => undefined}
      />
    </View>
  );
}

function ListSection() {
  const [muscle, setMuscle] = useState(0);
  return (
    <View style={styles.gap}>
      <SectionHeader title="Cơ thể tập trung" onMore={() => undefined} />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
        {MUSCLES.map((m, i) => (
          <Chip key={m} label={m} selected={i === muscle} onPress={() => setMuscle(i)} />
        ))}
      </ScrollView>
      <ListItem title="Barbell Back Squat" meta="4 hiệp × 8 rep • 60 kg" thumb={<MediaThumb />} difficultyRank={2} badge="AI" onPress={() => undefined} />
      <ListItem title="Dumbbell Row" meta="3 hiệp × 10 rep • 20 kg" thumb={<MediaThumb fallbackIcon="body" />} difficultyRank={1} showArrow />
      <View style={styles.wrap}>
        <FilterTile label="Tạ đơn" icon="barbell-outline" />
        <FilterTile label="Máy cáp" icon="git-network-outline" selected />
      </View>
      <View style={styles.wrap}>
        <LevelChip level="beginner" />
        <LevelChip level="intermediate" />
        <LevelChip level="advanced" />
      </View>
    </View>
  );
}

export default function ComponentGallery() {
  const [query, setQuery] = useState('');
  return (
    <Screen header={<ScreenHeader title="Component" streakDays={3} />}>
      <SearchBar value={query} onChangeText={setQuery} />
      <CardsSection />
      <ListSection />
      <StatCard
        stats={[
          { icon: 'medal-outline', value: '3', label: 'Buổi tập' },
          { icon: 'barbell-outline', value: '2.400', label: 'kg khối lượng' },
          { icon: 'time-outline', value: '95', label: 'Phút' },
        ]}
      />
      <View style={styles.center}>
        <CountdownRing remaining={14} total={20} />
      </View>
      <GradientButton label="Bắt đầu" onPress={() => undefined} />
      <View>
        <SettingsRow icon="person" iconColor="#1E5EFF" label="Hồ sơ cá nhân" />
        <SettingsRow icon="flag" iconColor="#22B573" label="Mục tiêu" hasDot />
        <SettingsRow icon="log-out" iconColor="#FF7A2F" label="Đăng xuất" onPress={() => router.back()} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  gap: { gap: spacing.lg },
  card: { borderRadius: radius.card, padding: spacing.xl },
  row: { gap: spacing.md },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
  center: { alignItems: 'center' },
});
