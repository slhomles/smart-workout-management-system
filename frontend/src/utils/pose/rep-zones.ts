/**
 * Phân vùng góc và kiểm dữ liệu vào cho FSM đếm rep (spec fe-pose-logic §2.5).
 * Bằng ngưỡng thì tính là ở trong vùng; vùng giữa S và O tạo trễ để không đếm nhiễu.
 */
import type { RepRule, RepSample } from '@/types/pose';

/** `start` = vùng vị trí bắt đầu (S), `opposite` = vùng đối diện (O), `between` = vùng chuyển. */
export type Zone = 'start' | 'between' | 'opposite';

/** Mẫu đã qua kiểm tra: góc và thời gian đều là số hữu hạn. */
export type ValidSample = { t_ms: number; angle_deg: number };

const MIN_DEG = 0;
const MAX_DEG = 180;

function isDegree(value: number): boolean {
  return Number.isFinite(value) && value >= MIN_DEG && value <= MAX_DEG;
}

/** Ném `RangeError` khi ngưỡng không phải góc hợp lệ hoặc không có `flexed < partial < extended`. */
export function assertValidThresholds(rep: RepRule): void {
  const thresholds = { extended_deg: rep.extended_deg, flexed_deg: rep.flexed_deg, partial_deg: rep.partial_deg };
  for (const [name, value] of Object.entries(thresholds)) {
    if (!isDegree(value)) throw new RangeError(`${name} phải là số hữu hạn trong [0, 180]`);
  }
  if (!(rep.flexed_deg < rep.partial_deg && rep.partial_deg < rep.extended_deg)) {
    throw new RangeError('Cần flexed_deg < partial_deg < extended_deg');
  }
}

/** Mẫu hợp lệ khi góc trong [0, 180], `t_ms` hữu hạn và không lùi so với mẫu hợp lệ trước (bằng thì nhận). */
export function toValidSample(sample: RepSample, lastT: number | null): ValidSample | null {
  const { t_ms, angle_deg } = sample;
  if (angle_deg === null || !isDegree(angle_deg)) return null;
  if (!Number.isFinite(t_ms)) return null;
  if (lastT !== null && t_ms < lastT) return null;
  return { t_ms, angle_deg };
}

export function zoneOf(angle: number, rep: RepRule): Zone {
  const isExtendedStart = rep.start === 'extended';
  const isAtExtended = angle >= rep.extended_deg;
  const isAtFlexed = angle <= rep.flexed_deg;
  if (isExtendedStart ? isAtExtended : isAtFlexed) return 'start';
  if (isExtendedStart ? isAtFlexed : isAtExtended) return 'opposite';
  return 'between';
}

/** Góc đã vượt `partial_deg` theo hướng đi từ S sang O. */
export function isPastPartial(angle: number, rep: RepRule): boolean {
  return rep.start === 'extended' ? angle <= rep.partial_deg : angle >= rep.partial_deg;
}

/** Góc cực trị hơn hẳn (không tính bằng) theo hướng đi từ S sang O, dùng để giữ mẫu cực trị đầu tiên. */
export function isMoreExtreme(angle: number, current: number, rep: RepRule): boolean {
  return rep.start === 'extended' ? angle < current : angle > current;
}
