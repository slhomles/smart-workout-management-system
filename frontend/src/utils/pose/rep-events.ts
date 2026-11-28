/**
 * Dựng `RepEvent` (khớp `RepEventInput` của backend) từ các mốc thời gian của FSM
 * và gán pha theo `first_phase` (spec fe-pose-logic §2.5, mục "Gán trường RepEvent").
 */
import type { RepEvent, RepRule } from '@/types/pose';

/** Thời lượng ba đoạn của một rep: ra khỏi S, nghỉ ở O, quay về S. */
export type RepTiming = { phase1: number; pauseO: number; phase2: number };

export type RepEventParts = {
  rep_no: number;
  start_offset_ms: number;
  timing: RepTiming;
  min_joint_angle_deg: number;
  max_joint_angle_deg: number;
  is_full_rom: boolean;
};

/** Rep mới hoàn tất có `pauseS = 0`; giá trị thật được gán khi rep sau rời S (`withPauseS`). */
export function buildRepEvent(rule: RepRule, input: RepEventParts): RepEvent {
  const phase1 = Math.round(input.timing.phase1);
  const pauseO = Math.round(input.timing.pauseO);
  const phase2 = Math.round(input.timing.phase2);
  const isEccentricFirst = rule.first_phase === 'eccentric';
  return {
    rep_no: input.rep_no,
    start_offset_ms: Math.round(input.start_offset_ms),
    eccentric_ms: isEccentricFirst ? phase1 : phase2,
    pause_bottom_ms: isEccentricFirst ? pauseO : 0,
    concentric_ms: isEccentricFirst ? phase2 : phase1,
    pause_top_ms: isEccentricFirst ? 0 : pauseO,
    min_joint_angle_deg: input.min_joint_angle_deg,
    max_joint_angle_deg: input.max_joint_angle_deg,
    is_full_rom: input.is_full_rom,
  };
}

/** Bản sao của `event` với pha nghỉ ở vị trí bắt đầu (`pauseS`) gán vào đúng field theo `first_phase`. */
export function withPauseS(rule: RepRule, event: RepEvent, pauseS: number): RepEvent {
  const pause = Math.round(pauseS);
  if (rule.first_phase === 'eccentric') return { ...event, pause_top_ms: pause };
  return { ...event, pause_bottom_ms: pause };
}
