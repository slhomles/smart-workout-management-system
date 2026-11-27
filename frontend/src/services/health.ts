/** `GET /api/v1/health` (doc 05 §7.6): kiểm tra app gọi được backend. */
import { api } from './api/client';

export type HealthStatus = {
  database: string;
  redis: string;
  ai_service: string;
  checked_at: string;
};

export async function getHealth(): Promise<HealthStatus> {
  const res = await api.get<HealthStatus>('/health');
  return res.data;
}
