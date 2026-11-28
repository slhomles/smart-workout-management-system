/**
 * Service tab Báo cáo: `/dashboard`, `/body`, `/recovery`, `/reports` (spec fe-dashboard §2.3).
 * Mọi hàm trả thẳng `res.data`; danh sách có dạng `Page<T>` (`Claude_api_respone.md` §1, §5).
 */
import type {
  BodyMeasurement,
  BodyProfile,
  CreateMeasurementRequest,
  CreateReportRequest,
  Dashboard,
  ListMuscleRecoveryParams,
  ListReportsParams,
  MuscleRecoveryStatus,
  ReplaceBodyProfileRequest,
  ReportExport,
  TrendRange,
  WeightTrend,
} from '@/types/dashboard';
import type { Page } from '@/types/page';

import { api } from './api/client';

export async function getDashboard(): Promise<Dashboard> {
  const res = await api.get<Dashboard>('/dashboard');
  return res.data;
}

export async function getWeightTrend(range: TrendRange): Promise<WeightTrend> {
  const res = await api.get<WeightTrend>('/dashboard/weight-trend', { params: { range } });
  return res.data;
}

export async function getBodyProfile(): Promise<BodyProfile> {
  const res = await api.get<BodyProfile>('/body/profile');
  return res.data;
}

/** PUT thay toàn bộ hồ sơ thể chất: phải gửi đủ mọi field. */
export async function replaceBodyProfile(body: ReplaceBodyProfileRequest): Promise<BodyProfile> {
  const res = await api.put<BodyProfile>('/body/profile', body);
  return res.data;
}

export async function createMeasurement(body: CreateMeasurementRequest): Promise<BodyMeasurement> {
  const res = await api.post<BodyMeasurement>('/body/measurements', body);
  return res.data;
}

export async function listMuscleRecovery(params: ListMuscleRecoveryParams): Promise<Page<MuscleRecoveryStatus>> {
  const res = await api.get<Page<MuscleRecoveryStatus>>('/recovery/muscle-groups', { params });
  return res.data;
}

export async function createReport(body: CreateReportRequest): Promise<ReportExport> {
  const res = await api.post<ReportExport>('/reports', body);
  return res.data;
}

export async function listReports(params: ListReportsParams): Promise<Page<ReportExport>> {
  const res = await api.get<Page<ReportExport>>('/reports', { params });
  return res.data;
}
