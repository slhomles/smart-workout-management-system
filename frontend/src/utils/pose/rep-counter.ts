/**
 * Máy trạng thái đếm rep (spec fe-pose-logic §2.5). Đây là hợp đồng mà worker Python cài lại,
 * nên mỗi mốc thời gian lấy đúng `t_ms` của mẫu gây chuyển trạng thái, không nội suy.
 */
import type { Phase, RepEvent, RepRule, RepSample, RepState, RepUpdate } from '@/types/pose';

import { buildRepEvent, withPauseS, type RepTiming } from './rep-events';
import {
  assertValidThresholds,
  isMoreExtreme,
  isPastPartial,
  toValidSample,
  zoneOf,
  type ValidSample,
  type Zone,
} from './rep-zones';

export type RepCounter = {
  update(sample: RepSample): RepUpdate;
  getReps(): RepEvent[];
  reset(): void;
};

/** Trạng thái nội bộ của một counter; `reset()` thay bằng context mới. */
type Context = {
  state: RepState;
  t0: number | null;
  lastT: number | null;
  leaveS: number;
  enterO: number;
  leaveO: number;
  minAngle: number;
  maxAngle: number;
  turnT: number;
  turnAngle: number;
  hasPassedPartial: boolean;
  lastEnterS: number | null;
  reps: RepEvent[];
};

type Transition = (ctx: Context, rule: RepRule, zone: Zone, sample: ValidSample) => RepEvent | null;

type Completion = { enterS: number; timing: RepTiming; is_full_rom: boolean };

function createContext(): Context {
  return {
    state: 'idle',
    t0: null,
    lastT: null,
    leaveS: 0,
    enterO: 0,
    leaveO: 0,
    minAngle: 0,
    maxAngle: 0,
    turnT: 0,
    turnAngle: 0,
    hasPassedPartial: false,
    lastEnterS: null,
    reps: [],
  };
}

export function phaseOf(state: RepState, rep: RepRule): Phase | null {
  const isEccentricFirst = rep.first_phase === 'eccentric';
  const phases: Record<RepState, Phase | null> = {
    idle: null,
    at_start: isEccentricFirst ? 'top' : 'bottom',
    moving_out: rep.first_phase,
    at_end: isEccentricFirst ? 'bottom' : 'top',
    moving_back: isEccentricFirst ? 'concentric' : 'eccentric',
  };
  return phases[state];
}

function trackRange(ctx: Context, angle: number): void {
  ctx.minAngle = Math.min(ctx.minAngle, angle);
  ctx.maxAngle = Math.max(ctx.maxAngle, angle);
}

/** Giữ mẫu cực trị ĐẦU TIÊN của lần ra (tTurn) và đánh dấu đã vượt partial, cho rep thiếu biên độ. */
function trackOutward(ctx: Context, rule: RepRule, sample: ValidSample): void {
  if (isMoreExtreme(sample.angle_deg, ctx.turnAngle, rule)) {
    ctx.turnT = sample.t_ms;
    ctx.turnAngle = sample.angle_deg;
  }
  if (isPastPartial(sample.angle_deg, rule)) ctx.hasPassedPartial = true;
}

function setLastPause(ctx: Context, rule: RepRule, pauseS: number): void {
  const lastIndex = ctx.reps.length - 1;
  const last = ctx.reps[lastIndex];
  if (last === undefined) return;
  ctx.reps[lastIndex] = withPauseS(rule, last, pauseS);
}

/** Pha nghỉ ở S của rep trước = leaveS(n+1) − enterS(n); lần rời S sau (kể cả sau nhiễu) ghi đè. */
function updatePreviousPause(ctx: Context, rule: RepRule, leaveS: number): void {
  if (ctx.lastEnterS === null) return;
  setLastPause(ctx, rule, leaveS - ctx.lastEnterS);
}

function leaveStart(ctx: Context, rule: RepRule, zone: Zone, sample: ValidSample): void {
  const { t_ms, angle_deg } = sample;
  ctx.leaveS = t_ms;
  ctx.minAngle = angle_deg;
  ctx.maxAngle = angle_deg;
  ctx.turnT = t_ms;
  ctx.turnAngle = angle_deg;
  ctx.hasPassedPartial = isPastPartial(angle_deg, rule);
  updatePreviousPause(ctx, rule, t_ms);
  if (zone === 'opposite') {
    ctx.enterO = t_ms;
    ctx.state = 'at_end';
    return;
  }
  ctx.state = 'moving_out';
}

function recordRep(ctx: Context, rule: RepRule, completion: Completion): RepEvent {
  const event = buildRepEvent(rule, {
    rep_no: ctx.reps.length + 1,
    start_offset_ms: ctx.leaveS - (ctx.t0 ?? ctx.leaveS),
    timing: completion.timing,
    min_joint_angle_deg: ctx.minAngle,
    max_joint_angle_deg: ctx.maxAngle,
    is_full_rom: completion.is_full_rom,
  });
  ctx.reps.push(event);
  ctx.lastEnterS = completion.enterS;
  ctx.state = 'at_start';
  return event;
}

function completeFullRep(ctx: Context, rule: RepRule, enterS: number): RepEvent {
  const timing = { phase1: ctx.enterO - ctx.leaveS, pauseO: ctx.leaveO - ctx.enterO, phase2: enterS - ctx.leaveO };
  return recordRep(ctx, rule, { enterS, timing, is_full_rom: true });
}

function completePartialRep(ctx: Context, rule: RepRule, enterS: number): RepEvent {
  const timing = { phase1: ctx.turnT - ctx.leaveS, pauseO: 0, phase2: enterS - ctx.turnT };
  return recordRep(ctx, rule, { enterS, timing, is_full_rom: false });
}

const fromIdle: Transition = (ctx, _rule, zone) => {
  if (zone === 'start') ctx.state = 'at_start';
  return null;
};

const fromAtStart: Transition = (ctx, rule, zone, sample) => {
  if (zone !== 'start') leaveStart(ctx, rule, zone, sample);
  return null;
};

const fromMovingOut: Transition = (ctx, rule, zone, sample) => {
  trackRange(ctx, sample.angle_deg);
  if (zone === 'opposite') {
    ctx.enterO = sample.t_ms;
    ctx.state = 'at_end';
    return null;
  }
  if (zone === 'start') {
    if (ctx.hasPassedPartial) return completePartialRep(ctx, rule, sample.t_ms);
    // Chưa vượt partial: coi là nhiễu, không đếm; lần rời S sau ghi đè leaveS. Nhiễu không phải
    // rep sau nên rep cuối vẫn là rep cuối: pauseS về 0 cho tới lần rời S thật (spec §2.5, §6 ý 7).
    setLastPause(ctx, rule, 0);
    ctx.state = 'at_start';
    return null;
  }
  trackOutward(ctx, rule, sample);
  return null;
};

const fromAtEnd: Transition = (ctx, rule, zone, sample) => {
  trackRange(ctx, sample.angle_deg);
  if (zone === 'opposite') return null;
  ctx.leaveO = sample.t_ms;
  if (zone === 'start') return completeFullRep(ctx, rule, sample.t_ms);
  ctx.state = 'moving_back';
  return null;
};

const fromMovingBack: Transition = (ctx, rule, zone, sample) => {
  trackRange(ctx, sample.angle_deg);
  // Quay lại O: enterO giữ nguyên, leaveO sẽ ghi lại ở lần rời O sau cùng.
  if (zone === 'opposite') ctx.state = 'at_end';
  if (zone === 'start') return completeFullRep(ctx, rule, sample.t_ms);
  return null;
};

const TRANSITIONS: Record<RepState, Transition> = {
  idle: fromIdle,
  at_start: fromAtStart,
  moving_out: fromMovingOut,
  at_end: fromAtEnd,
  moving_back: fromMovingBack,
};

function toUpdate(ctx: Context, rule: RepRule, completed: RepEvent | null): RepUpdate {
  const isPartialRep = completed !== null && !completed.is_full_rom;
  return {
    state: ctx.state,
    phase: phaseOf(ctx.state, rule),
    rep_count: ctx.reps.length,
    completed_rep: completed === null ? null : { ...completed },
    partial_mistake_code: isPartialRep ? rule.partial_mistake_code : null,
  };
}

/** Tạo counter cho một set; ném `RangeError` khi ngưỡng của `rep` sai (spec §2.5). */
export function createRepCounter(rep: RepRule): RepCounter {
  assertValidThresholds(rep);
  // Chép rule để bên gọi sửa object gốc giữa chừng không làm lệch FSM.
  const rule: RepRule = { ...rep };
  let ctx = createContext();

  return {
    update(sample: RepSample): RepUpdate {
      const valid = toValidSample(sample, ctx.lastT);
      if (valid === null) return toUpdate(ctx, rule, null);
      ctx.lastT = valid.t_ms;
      ctx.t0 ??= valid.t_ms;
      const completed = TRANSITIONS[ctx.state](ctx, rule, zoneOf(valid.angle_deg, rule), valid);
      return toUpdate(ctx, rule, completed);
    },
    getReps(): RepEvent[] {
      return ctx.reps.map((event) => ({ ...event }));
    },
    reset(): void {
      ctx = createContext();
    },
  };
}
