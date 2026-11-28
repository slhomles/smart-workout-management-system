/**
 * Tempo của một hiệp và % frame đúng form (spec fe-pose-logic §2.7).
 * Công thức khớp `training.v_set_tempo` và cột `ai.pose_analyses.correct_form_pct numeric(5,2)`,
 * để số trên app trùng số backend tính lại (spec §6 ý 9).
 */
import type { RepEvent, TempoSummary } from '@/types/pose';

/** Tổng 4 pha của một rep: thời gian chịu tải (TUT). */
function repDurationMs(rep: RepEvent): number {
  return rep.eccentric_ms + rep.pause_bottom_ms + rep.concentric_ms + rep.pause_top_ms;
}

/**
 * Trung bình làm tròn số nguyên như `round(avg(...))` của PostgreSQL.
 * Giá trị không âm nên `Math.round` (0,5 làm tròn lên) cho cùng kết quả.
 */
function roundedAverage(reps: RepEvent[], pick: (rep: RepEvent) => number): number {
  const sum = reps.reduce((total, rep) => total + pick(rep), 0);
  return Math.round(sum / reps.length);
}

/** Tóm tắt tempo của các rep trong một hiệp; `[]` trả `null` (view không có dòng nào). */
export function summarizeTempo(reps: RepEvent[]): TempoSummary | null {
  const count = reps.length;
  if (count === 0) return null;
  const fullRomCount = reps.filter((rep) => rep.is_full_rom).length;
  return {
    rep_count: count,
    avg_eccentric_ms: roundedAverage(reps, (rep) => rep.eccentric_ms),
    avg_pause_bottom_ms: roundedAverage(reps, (rep) => rep.pause_bottom_ms),
    avg_concentric_ms: roundedAverage(reps, (rep) => rep.concentric_ms),
    avg_pause_top_ms: roundedAverage(reps, (rep) => rep.pause_top_ms),
    time_under_tension_ms: reps.reduce((total, rep) => total + repDurationMs(rep), 0),
    // Nhân trước rồi mới chia để tránh sai số dấu phẩy động khi làm tròn 1 chữ số.
    full_rom_pct: Math.round((1000 * fullRomCount) / count) / 10,
  };
}

function isNonNegativeInteger(value: number): boolean {
  return Number.isInteger(value) && value >= 0;
}

/**
 * % frame đúng form, làm tròn 2 chữ số; `evaluatedFrames = 0` trả `null`.
 * Ném `RangeError` khi tham số không phải số nguyên ≥ 0 hoặc `violatingFrames > evaluatedFrames`.
 */
export function correctFormPct(evaluatedFrames: number, violatingFrames: number): number | null {
  if (!isNonNegativeInteger(evaluatedFrames) || !isNonNegativeInteger(violatingFrames)) {
    throw new RangeError(
      `correctFormPct: evaluatedFrames (${evaluatedFrames}) và violatingFrames (${violatingFrames}) phải là số nguyên >= 0`,
    );
  }
  if (violatingFrames > evaluatedFrames) {
    throw new RangeError(
      `correctFormPct: violatingFrames (${violatingFrames}) lớn hơn evaluatedFrames (${evaluatedFrames})`,
    );
  }
  if (evaluatedFrames === 0) return null;
  // Nhân trước rồi mới chia để tránh sai số dấu phẩy động khi làm tròn 2 chữ số.
  return Math.round((10000 * (evaluatedFrames - violatingFrames)) / evaluatedFrames) / 100;
}
