/** Nhãn hiển thị của nhóm màn tài khoản (spec fe-auth §2.4). */
import type { UnitSystem } from '@/types/auth';

const UNIT_SYSTEM_LABELS: Record<UnitSystem, string> = {
  metric: 'Mét (kg, cm)',
  imperial: 'Anh (lb, in)',
};

/** `null` coi như `metric` (spec fe-auth §6 ý 10). */
export function unitSystemLabel(unit: UnitSystem | null): string {
  return UNIT_SYSTEM_LABELS[unit ?? 'metric'];
}
