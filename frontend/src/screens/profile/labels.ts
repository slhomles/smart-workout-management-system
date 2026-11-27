/** Nhãn hiển thị của nhóm màn tài khoản (spec fe-auth §2.4). */
import type { UnitSystem } from '@/types/auth';
import type { GoalStatus } from '@/types/profile';

const UNIT_SYSTEM_LABELS: Record<UnitSystem, string> = {
  metric: 'Mét (kg, cm)',
  imperial: 'Anh (lb, in)',
};

const GOAL_STATUS_LABELS: Record<GoalStatus, string> = {
  active: 'Đang thực hiện',
  achieved: 'Đã đạt',
  abandoned: 'Đã bỏ',
};

/** `null` coi như `metric` (spec fe-auth §6 ý 10). */
export function unitSystemLabel(unit: UnitSystem | null): string {
  return UNIT_SYSTEM_LABELS[unit ?? 'metric'];
}

export function goalStatusLabel(status: GoalStatus): string {
  return GOAL_STATUS_LABELS[status];
}
