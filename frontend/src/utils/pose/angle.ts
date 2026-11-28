/**
 * Góc khớp từ ba điểm (spec fe-pose-logic §2.4).
 * Làm tròn 2 chữ số thập phân để so ngưỡng tất định và khớp kiểu `numeric` của backend (spec §6 ý 10).
 */
import type { Point } from '@/types/pose';

type Vector = { x: number; y: number; z: number };

export type AngleOptions = { use3d?: boolean };

const DEGREES_PER_RADIAN = 180 / Math.PI;

function roundTo2(value: number): number {
  return Math.round(value * 100) / 100;
}

/** Vector `from→to`; `null` khi có toạ độ không hữu hạn hoặc thiếu `z` ở chế độ 3D (NaN lan sang hiệu). */
function vectorBetween(from: Point, to: Point, isUse3d: boolean): Vector | null {
  const x = to.x - from.x;
  const y = to.y - from.y;
  const z = isUse3d ? (to.z ?? Number.NaN) - (from.z ?? Number.NaN) : 0;
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(z)) return null;
  return { x, y, z };
}

/**
 * Góc tại `b` giữa `b→a` và `b→c`, tính bằng độ trong [0, 180].
 * Trả `null` khi toạ độ không hợp lệ hoặc một vector có độ dài 0.
 */
export function angleDeg(a: Point, b: Point, c: Point, opts?: AngleOptions): number | null {
  const isUse3d = opts?.use3d === true;
  const ba = vectorBetween(b, a, isUse3d);
  const bc = vectorBetween(b, c, isUse3d);
  if (ba === null || bc === null) return null;
  const lengthProduct = Math.hypot(ba.x, ba.y, ba.z) * Math.hypot(bc.x, bc.y, bc.z);
  if (lengthProduct === 0 || !Number.isFinite(lengthProduct)) return null;
  const dot = ba.x * bc.x + ba.y * bc.y + ba.z * bc.z;
  // Sai số dấu phẩy động có thể đẩy cosin ra ngoài [-1, 1] khi ba điểm gần thẳng hàng, làm `acos` ra NaN.
  const cosine = Math.min(1, Math.max(-1, dot / lengthProduct));
  return roundTo2(Math.acos(cosine) * DEGREES_PER_RADIAN);
}
