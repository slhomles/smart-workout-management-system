import { api } from '@/services/api/client';
import {
  createMeasurement,
  createReport,
  getBodyProfile,
  getDashboard,
  getWeightTrend,
  listMuscleRecovery,
  listReports,
  replaceBodyProfile,
} from '@/services/dashboard';
import type { ReplaceBodyProfileRequest } from '@/types/dashboard';

type HttpMethod = 'get' | 'post' | 'put';
type ServiceCase = {
  name: string;
  method: HttpMethod;
  call: () => Promise<unknown>;
  expectedArgs: unknown[];
};

// Persona demo theo seed (spec fe-dashboard §5), không phải dữ liệu người dùng thật.
const profileDemoBody: ReplaceBodyProfileRequest = {
  gender: 'male',
  date_of_birth: '2003-05-10',
  height_cm: 172,
  activity_level_id: 3,
  experience_level_id: 1,
};

// Thứ tự theo bảng spec fe-dashboard §2.3.
const SERVICE_CASES: ServiceCase[] = [
  { name: 'getDashboard', method: 'get', call: () => getDashboard(), expectedArgs: ['/dashboard'] },
  {
    name: 'getWeightTrend',
    method: 'get',
    call: () => getWeightTrend('3months'),
    expectedArgs: ['/dashboard/weight-trend', { params: { range: '3months' } }],
  },
  { name: 'getBodyProfile', method: 'get', call: () => getBodyProfile(), expectedArgs: ['/body/profile'] },
  {
    name: 'replaceBodyProfile',
    method: 'put',
    call: () => replaceBodyProfile(profileDemoBody),
    expectedArgs: ['/body/profile', profileDemoBody],
  },
  {
    name: 'createMeasurement',
    method: 'post',
    call: () => createMeasurement({ weight_kg: 70.5 }),
    expectedArgs: ['/body/measurements', { weight_kg: 70.5 }],
  },
  {
    name: 'listMuscleRecovery',
    method: 'get',
    call: () => listMuscleRecovery({ limit: 100 }),
    expectedArgs: ['/recovery/muscle-groups', { params: { limit: 100 } }],
  },
  {
    name: 'createReport',
    method: 'post',
    call: () => createReport({ report_type: 'weekly_summary', period_start: '2026-11-16' }),
    expectedArgs: ['/reports', { report_type: 'weekly_summary', period_start: '2026-11-16' }],
  },
  {
    name: 'listReports',
    method: 'get',
    call: () => listReports({ report_type: 'weekly_summary', limit: 20, cursor: 'c-2' }),
    expectedArgs: ['/reports', { params: { report_type: 'weekly_summary', limit: 20, cursor: 'c-2' } }],
  },
];

describe('services dashboard (spec fe-dashboard §2.3)', () => {
  afterEach(() => jest.restoreAllMocks());

  it('FEDASH-03 bảng kiểm tra phủ đủ 8 hàm service theo đúng thứ tự', () => {
    expect(SERVICE_CASES.map((c) => c.name)).toEqual([
      'getDashboard',
      'getWeightTrend',
      'getBodyProfile',
      'replaceBodyProfile',
      'createMeasurement',
      'listMuscleRecovery',
      'createReport',
      'listReports',
    ]);
  });

  it.each(SERVICE_CASES)(
    'FEDASH-03 $name gọi api.$method đúng URL, body/params và trả thẳng res.data',
    async ({ method, call, expectedArgs }) => {
      const payload = { data: ['X'], marker: 'X' };
      const spy = jest.spyOn(api, method).mockResolvedValue({ data: payload });

      // toBe: phải là đúng object `res.data`, không đọc tiếp `.data.data`.
      await expect(call()).resolves.toBe(payload);

      expect(spy).toHaveBeenCalledTimes(1);
      // toStrictEqual: bắt cả tham số thừa (vd getDashboard không được truyền config thứ 2).
      expect(spy.mock.calls[0]).toStrictEqual(expectedArgs);
    },
  );

  it('FEDASH-03 lỗi từ api được ném nguyên cho tầng gọi xử lý', async () => {
    const failure = new Error('network');
    jest.spyOn(api, 'post').mockRejectedValue(failure);

    await expect(createReport({ report_type: 'weekly_summary', period_start: '2026-11-16' })).rejects.toBe(failure);
  });
});
