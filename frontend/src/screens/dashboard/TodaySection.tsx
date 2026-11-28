import { View } from 'react-native';

import { SectionHeader, StatCard, type Stat } from '@/components/common';
import type { UnitSystem } from '@/types/auth';
import type { TodaySummary } from '@/types/dashboard';
import { formatNumber } from '@/utils/format';
import { kgToLb } from '@/utils/units';

type Props = { today: TodaySummary; unitSystem: UnitSystem | null };

/**
 * "Hôm nay": số buổi, tổng khối lượng, số phút (spec §2.2 ý 2). KHÔNG hiện calo tiêu hao
 * `est_calories_burned_kcal` (spec §3, §6 ý 4).
 */
export function TodaySection({ today, unitSystem }: Props) {
  const isImperial = unitSystem === 'imperial';
  const volume = isImperial ? kgToLb(today.total_volume_kg) : today.total_volume_kg;
  const stats: Stat[] = [
    { icon: 'medal', value: formatNumber(today.sessions_completed, 0), label: 'Buổi tập' },
    { icon: 'barbell', value: formatNumber(volume, 0), label: isImperial ? 'Khối lượng (lb)' : 'Khối lượng (kg)' },
    { icon: 'time', value: formatNumber(today.duration_minutes, 0), label: 'Phút' },
  ];
  return (
    <View>
      <SectionHeader title="Hôm nay" />
      <StatCard stats={stats} />
    </View>
  );
}
