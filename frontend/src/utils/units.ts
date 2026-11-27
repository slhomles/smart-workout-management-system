/**
 * Quy đổi đơn vị cân nặng. API luôn dùng kg (SI); hiển thị theo `unit_system` của
 * `GET /auth/me`, `null` coi như `metric` (frontend-standards §3; spec fe-auth §6 ý 10).
 */
import type { UnitSystem } from '@/types/auth';

import { formatNumber } from './format';

// Định nghĩa quốc tế: 1 lb = 0,45359237 kg.
const KG_PER_LB = 0.45359237;

export function kgToLb(kg: number): number {
  return kg / KG_PER_LB;
}

export function lbToKg(lb: number): number {
  return lb * KG_PER_LB;
}

export function formatWeight(kg: number, unitSystem: UnitSystem | null): string {
  if (unitSystem === 'imperial') return `${formatNumber(kgToLb(kg))} lb`;
  return `${formatNumber(kg)} kg`;
}
