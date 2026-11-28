/**
 * Bảng luật tư thế dùng chung với worker video (spec fe-pose-logic §2.2, §6 ý 1).
 * Import thẳng `shared/constants/pose-rules.json` (không chép vào `frontend/`) để chỉ có một nguồn ngưỡng;
 * Metro bundle được file này nhờ `watchFolders` trong `metro.config.js`.
 */
import type { ExerciseRule, PoseRulesFile } from '@/types/pose';

import rawPoseRules from '../../../../shared/constants/pose-rules.json';
import { validatePoseRules } from './rules-validate';

export { PoseRulesError, validatePoseRules } from './rules-validate';

/** Kiểm một lần lúc nạp module: file luật sai thì app báo lỗi ngay thay vì chấm tư thế sai. */
export const POSE_RULES: PoseRulesFile = validatePoseRules(rawPoseRules);

export const AI_RULE_SLUGS: readonly string[] = Object.freeze(Object.keys(POSE_RULES.exercises).sort());

/** So khớp chính xác own key, để `'__proto__'`, `'toString'`… không bị coi là có luật. */
export function hasAiRules(slug: string): boolean {
  return Object.hasOwn(POSE_RULES.exercises, slug);
}

export function getPoseRules(slug: string): ExerciseRule | null {
  if (!hasAiRules(slug)) return null;
  return POSE_RULES.exercises[slug] ?? null;
}

export type AiTrainerCandidate = { slug: string; supports_ai_tracking: boolean };

/** Nút AI chỉ hiện khi bài vừa bật `supports_ai_tracking` vừa có luật tư thế (frontend-standards §8.3). */
export function canUseAiTrainer({ slug, supports_ai_tracking: isAiTrackingSupported }: AiTrainerCandidate): boolean {
  return isAiTrackingSupported && hasAiRules(slug);
}
