import type { Ionicons } from '@expo/vector-icons';
import type { ComponentProps } from 'react';

type IconName = ComponentProps<typeof Ionicons>['name'];

/** 4 tab cố định theo ảnh mẫu (frontend-standards §8.3); `name` trùng tên file trong src/app/(tabs)/. */
export const TABS: { name: string; title: string; icon: IconName }[] = [
  { name: 'index', title: 'Tập luyện', icon: 'stopwatch' },
  { name: 'explore', title: 'Khám phá', icon: 'compass' },
  { name: 'report', title: 'Báo cáo', icon: 'bar-chart' },
  { name: 'profile', title: 'Cá nhân', icon: 'person' },
];
