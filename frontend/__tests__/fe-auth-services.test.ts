import { api } from '@/services/api/client';
import { changePassword, getMe, login, logout, logoutAll, register, updateMe } from '@/services/auth';
import { createGoal, listGoals, listGoalTypes, updateGoal } from '@/services/profile';
import type { ChangePasswordRequest, LoginRequest, RegisterRequest, UpdateMeRequest } from '@/types/auth';
import type { CreateGoalRequest } from '@/types/profile';

type HttpMethod = 'get' | 'post' | 'patch';
type ServiceCase = {
  name: string;
  method: HttpMethod;
  call: () => Promise<unknown>;
  expectedArgs: unknown[];
};

// Dữ liệu giả theo persona seed (spec fe-auth §5), không phải dữ liệu người dùng thật.
const loginBody: LoginRequest = {
  email: 'demo@smartworkout.local',
  password: 'Demo@123',
  device: { device_id: null, platform: 'android' },
};
const registerBody: RegisterRequest = {
  email: 'moi.user@example.com',
  password: 'Moi@12345',
  display_name: 'Mới',
  full_name: null,
};
const updateMeBody: UpdateMeRequest = { display_name: 'An Nguyễn', full_name: null };
const changePasswordBody: ChangePasswordRequest = { current_password: 'Demo@123', new_password: 'Moi@12345' };
const createGoalBody: CreateGoalRequest = { goal_type_id: 2, target_weight_kg: 70.5, target_date: '2027-03-01' };

// Thứ tự theo bảng spec fe-auth §2.3.
const SERVICE_CASES: ServiceCase[] = [
  { name: 'login', method: 'post', call: () => login(loginBody), expectedArgs: ['/auth/login', loginBody] },
  { name: 'register', method: 'post', call: () => register(registerBody), expectedArgs: ['/auth/register', registerBody] },
  {
    name: 'logout',
    method: 'post',
    call: () => logout('r-1'),
    expectedArgs: ['/auth/logout', { refresh_token: 'r-1' }],
  },
  { name: 'logoutAll', method: 'post', call: () => logoutAll(), expectedArgs: ['/auth/logout-all'] },
  { name: 'getMe', method: 'get', call: () => getMe(), expectedArgs: ['/auth/me'] },
  { name: 'updateMe', method: 'patch', call: () => updateMe(updateMeBody), expectedArgs: ['/auth/me', updateMeBody] },
  {
    name: 'changePassword',
    method: 'patch',
    call: () => changePassword(changePasswordBody),
    expectedArgs: ['/auth/change-password', changePasswordBody],
  },
  {
    name: 'listGoals',
    method: 'get',
    call: () => listGoals({ limit: 20, cursor: 'c-2' }),
    expectedArgs: ['/body/goals', { params: { limit: 20, cursor: 'c-2' } }],
  },
  { name: 'listGoalTypes', method: 'get', call: () => listGoalTypes(), expectedArgs: ['/body/goal-types'] },
  { name: 'createGoal', method: 'post', call: () => createGoal(createGoalBody), expectedArgs: ['/body/goals', createGoalBody] },
  {
    name: 'updateGoal',
    method: 'patch',
    call: () => updateGoal('g-1', { status: 'achieved' }),
    expectedArgs: ['/body/goals/g-1', { status: 'achieved' }],
  },
];

describe('services auth/profile (spec fe-auth §2.3)', () => {
  afterEach(() => jest.restoreAllMocks());

  it('FEAUTH-03 bảng kiểm tra phủ đủ 11 hàm service', () => {
    expect(SERVICE_CASES.map((c) => c.name)).toEqual([
      'login',
      'register',
      'logout',
      'logoutAll',
      'getMe',
      'updateMe',
      'changePassword',
      'listGoals',
      'listGoalTypes',
      'createGoal',
      'updateGoal',
    ]);
  });

  it.each(SERVICE_CASES)(
    'FEAUTH-03 $name gọi api.$method đúng URL, body/params và trả thẳng res.data',
    async ({ method, call, expectedArgs }) => {
      const payload = { marker: 'X' };
      const spy = jest.spyOn(api, method).mockResolvedValue({ data: payload });

      await expect(call()).resolves.toBe(payload);

      expect(spy).toHaveBeenCalledTimes(1);
      // toStrictEqual: bắt cả tham số thừa (vd logoutAll không được truyền body thứ 2).
      expect(spy.mock.calls[0]).toStrictEqual(expectedArgs);
    },
  );

  it('FEAUTH-03 listGoals truyền status vào params', async () => {
    const page = { data: [], pagination: { next_cursor: null, has_more: false } };
    const spy = jest.spyOn(api, 'get').mockResolvedValue({ data: page });

    await expect(listGoals({ status: 'active' })).resolves.toBe(page);

    expect(spy).toHaveBeenCalledWith('/body/goals', { params: { status: 'active' } });
  });
});
