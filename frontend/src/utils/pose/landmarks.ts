/**
 * Landmark MediaPipe Pose (33 điểm) và cách chọn bên trái/phải để đo khớp (spec fe-pose-logic §2.4, §6 ý 5).
 */
import type { JointMeasurement, JointName, JointTriple, Landmark, Side } from '@/types/pose';

import { angleDeg } from './angle';

/** Chỉ số MediaPipe Pose của sáu khớp dùng chung với COCO-17 của worker. */
export const LANDMARK_INDEX = {
  shoulder: { left: 11, right: 12 },
  elbow: { left: 13, right: 14 },
  wrist: { left: 15, right: 16 },
  hip: { left: 23, right: 24 },
  knee: { left: 25, right: 26 },
  ankle: { left: 27, right: 28 },
} as const satisfies Record<JointName, Record<Side, number>>;

type LandmarkTriple = [Landmark, Landmark, Landmark];

// Thiếu `visibility` coi là thấy rõ (spec §2.4).
const DEFAULT_VISIBILITY = 1;

function assertPositiveSize(name: string, value: number): void {
  if (!Number.isFinite(value) || value <= 0) {
    throw new RangeError(`${name} phải là số hữu hạn > 0, nhận ${value}`);
  }
}

/** Đổi toạ độ chuẩn hoá sang pixel; `z` theo tỉ lệ `width` như quy ước của MediaPipe. */
export function toPixelLandmarks(landmarks: readonly Landmark[], width: number, height: number): Landmark[] {
  assertPositiveSize('width', width);
  assertPositiveSize('height', height);
  return landmarks.map((landmark) => {
    const pixel: Landmark = { x: landmark.x * width, y: landmark.y * height };
    if (landmark.z !== undefined) pixel.z = landmark.z * width;
    if (landmark.visibility !== undefined) pixel.visibility = landmark.visibility;
    return pixel;
  });
}

function isUsableLandmark(landmark: Landmark | undefined): landmark is Landmark {
  if (landmark === undefined) return false;
  if (!Number.isFinite(landmark.x) || !Number.isFinite(landmark.y)) return false;
  // Visibility NaN sẽ lọt qua mọi phép so ngưỡng, nên loại luôn bên đó.
  return landmark.visibility === undefined || Number.isFinite(landmark.visibility);
}

function landmarksOfSide(landmarks: readonly Landmark[], joint: JointTriple, side: Side): LandmarkTriple | null {
  const [first, middle, last] = joint.map((name) => landmarks[LANDMARK_INDEX[name][side]]);
  if (!isUsableLandmark(first) || !isUsableLandmark(middle) || !isUsableLandmark(last)) return null;
  return [first, middle, last];
}

type SideCandidate = { side: Side; triple: LandmarkTriple; score: number };

/** Điểm của một bên = visibility nhỏ nhất của 3 landmark; `null` nếu bên đó không dùng được. */
function sideCandidate(landmarks: readonly Landmark[], joint: JointTriple, side: Side): SideCandidate | null {
  const triple = landmarksOfSide(landmarks, joint, side);
  if (triple === null) return null;
  const score = Math.min(...triple.map((landmark) => landmark.visibility ?? DEFAULT_VISIBILITY));
  return { side, triple, score };
}

/** Bên nhìn rõ hơn (bằng nhau chọn `left`); điểm tốt nhất dưới `minVisibility` thì `null` (bằng thì nhận). */
function chooseSide(landmarks: readonly Landmark[], joint: JointTriple, minVisibility: number): SideCandidate | null {
  const left = sideCandidate(landmarks, joint, 'left');
  const right = sideCandidate(landmarks, joint, 'right');
  const best = right !== null && (left === null || right.score > left.score) ? right : left;
  if (best === null || best.score < minVisibility) return null;
  return best;
}

export function pickSide(landmarks: readonly Landmark[], joint: JointTriple, minVisibility: number): Side | null {
  return chooseSide(landmarks, joint, minVisibility)?.side ?? null;
}

/** Góc 2D tại khớp giữa của `joint`, đo ở bên do `pickSide` chọn. */
export function measureJoint(
  landmarks: readonly Landmark[],
  joint: JointTriple,
  minVisibility: number,
): JointMeasurement | null {
  const chosen = chooseSide(landmarks, joint, minVisibility);
  if (chosen === null) return null;
  const angle = angleDeg(...chosen.triple);
  if (angle === null) return null;
  return { side: chosen.side, angle_deg: angle };
}
