// Thẻ một mục tiêu (spec fe-auth §4 "Mục tiêu"; thẻ danh sách theo ảnh mẫu 04, phong cách ảnh 13).
import { Pressable, StyleSheet, View } from 'react-native';

import { AppText } from '@/components/common';
import { radius, sizes, spacing, useTheme } from '@/styles/theme';
import type { UnitSystem } from '@/types/auth';
import type { GoalStatus, UserGoal } from '@/types/profile';
import { formatDate } from '@/utils/format';
import { formatWeight } from '@/utils/units';

import { goalStatusLabel } from './labels';
import type { GoalCloseStatus } from './useCloseGoal';

/** Dòng `meta` "66 kg • 01/03/2027"; bỏ phần nào không có. `target_body_fat_pct` ngoài phạm vi (spec §3). */
function goalMeta(goal: UserGoal, unitSystem: UnitSystem | null): string {
  const parts: string[] = [];
  if (goal.target_weight_kg !== null) parts.push(formatWeight(goal.target_weight_kg, unitSystem));
  if (goal.target_date !== null) parts.push(formatDate(goal.target_date));
  return parts.join(' • ');
}

function StatusPill({ status }: { status: GoalStatus }) {
  const theme = useTheme();
  const isActive = status === 'active';
  return (
    <View style={[styles.pill, { backgroundColor: isActive ? theme.primarySoft : theme.surfaceMuted }]}>
      <AppText variant="label" color={isActive ? theme.primary : theme.textMuted}>
        {goalStatusLabel(status)}
      </AppText>
    </View>
  );
}

type ActionProps = { label: string; color: string; isDisabled: boolean; onPress: () => void };

function ActionButton({ label, color, isDisabled, onPress }: ActionProps) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: isDisabled }}
      style={[styles.action, { backgroundColor: theme.surfaceMuted, opacity: isDisabled ? 0.5 : 1 }]}
    >
      <AppText variant="label" color={color}>
        {label}
      </AppText>
    </Pressable>
  );
}

type CloseActionsProps = { goalId: string; isClosing: boolean; onClose: (goalId: string, status: GoalCloseStatus) => void };

/** Chỉ mục tiêu `active` mới đóng được (spec fe-auth §2.2); khoá cả hai nút khi đang gửi. */
function CloseActions({ goalId, isClosing, onClose }: CloseActionsProps) {
  const theme = useTheme();
  return (
    <View style={styles.actions}>
      <ActionButton
        label="Đánh dấu đã đạt"
        color={theme.primary}
        isDisabled={isClosing}
        onPress={() => onClose(goalId, 'achieved')}
      />
      <ActionButton
        label="Bỏ mục tiêu"
        color={theme.flame}
        isDisabled={isClosing}
        onPress={() => onClose(goalId, 'abandoned')}
      />
    </View>
  );
}

type Props = {
  goal: UserGoal;
  unitSystem: UnitSystem | null;
  isClosing: boolean;
  onClose: (goalId: string, status: GoalCloseStatus) => void;
};

export function GoalCard({ goal, unitSystem, isClosing, onClose }: Props) {
  const theme = useTheme();
  const meta = goalMeta(goal, unitSystem);
  return (
    <View testID={`goal-${goal.id}`} style={[styles.card, { backgroundColor: theme.surface }]}>
      <View style={styles.header}>
        <AppText variant="itemTitle" style={styles.title}>
          {goal.goal_type.name}
        </AppText>
        <StatusPill status={goal.status} />
      </View>
      {meta ? (
        <AppText variant="meta" color={theme.textMuted}>
          {meta}
        </AppText>
      ) : null}
      {goal.status === 'active' ? <CloseActions goalId={goal.id} isClosing={isClosing} onClose={onClose} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { borderRadius: radius.card, padding: spacing.lg, gap: spacing.sm },
  header: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  title: { flex: 1 },
  pill: { borderRadius: radius.pill, paddingHorizontal: spacing.md, paddingVertical: spacing.xs },
  actions: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xs },
  action: {
    flex: 1,
    minHeight: sizes.touch,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.pill,
    paddingHorizontal: spacing.md,
  },
});
