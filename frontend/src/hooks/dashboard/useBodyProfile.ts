/** Hồ sơ thể chất `GET /body/profile` (spec fe-dashboard §2.3). */
import { useQuery } from '@tanstack/react-query';

import { getBodyProfile } from '@/services/dashboard';

export const BODY_PROFILE_QUERY_KEY = ['body', 'profile'] as const;

export function useBodyProfile() {
  return useQuery({ queryKey: BODY_PROFILE_QUERY_KEY, queryFn: getBodyProfile });
}
