import axios, { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';

import { createApiClient, setSessionExpiredHandler } from '@/services/api/client';
import { getAccessToken, getRefreshToken, saveTokens } from '@/services/api/session-storage';

type Reply = { status: number; data: unknown };

/** Adapter giả: trả lần lượt các phản hồi theo URL, ghi lại header Authorization đã gửi. */
function fakeAdapter(replies: Record<string, Reply[]>, sentAuth: string[]) {
  return async (config: InternalAxiosRequestConfig) => {
    sentAuth.push(String(config.headers.Authorization ?? ''));
    const reply = replies[config.url ?? '']?.shift() ?? { status: 200, data: { ok: true } };
    const response = { status: reply.status, statusText: '', headers: {}, config, data: reply.data };
    if (reply.status >= 400) throw new AxiosError('fail', 'ERR', config, null, response);
    return response;
  };
}

const expired = { status: 401, data: { error: { code: 'token_expired', message: 'Hết hạn', details: [] } } };

describe('api client', () => {
  afterEach(() => jest.restoreAllMocks());

  it('gắn Bearer token từ SecureStore', async () => {
    await saveTokens({ access_token: 'acc-1', refresh_token: 'ref-1' });
    const sent: string[] = [];
    const api = createApiClient('http://api');
    api.defaults.adapter = fakeAdapter({}, sent);
    await api.get('/exercises');
    expect(sent).toEqual(['Bearer acc-1']);
  });

  it('token_expired: refresh một lần cho các request song song rồi retry đúng một lần', async () => {
    await saveTokens({ access_token: 'old', refresh_token: 'ref-old' });
    const refresh = jest
      .spyOn(axios, 'post')
      .mockResolvedValue({ data: { access_token: 'new', refresh_token: 'ref-new', device_id: 'dev-1' } });
    const sent: string[] = [];
    const api = createApiClient('http://api');
    api.defaults.adapter = fakeAdapter({ '/a': [expired], '/b': [expired] }, sent);

    await Promise.all([api.get('/a'), api.get('/b')]);

    expect(refresh).toHaveBeenCalledTimes(1);
    expect(await getAccessToken()).toBe('new');
    expect(await getRefreshToken()).toBe('ref-new');
    expect(sent.filter((h) => h === 'Bearer new')).toHaveLength(2);
  });

  it('refresh thất bại thì xoá token và báo phiên hết hạn', async () => {
    await saveTokens({ access_token: 'old', refresh_token: 'ref-old' });
    jest.spyOn(axios, 'post').mockRejectedValue(new Error('refresh failed'));
    const onExpired = jest.fn();
    setSessionExpiredHandler(onExpired);
    const api = createApiClient('http://api');
    api.defaults.adapter = fakeAdapter({ '/a': [expired] }, []);

    await expect(api.get('/a')).rejects.toBeInstanceOf(AxiosError);
    expect(onExpired).toHaveBeenCalledTimes(1);
    expect(await getAccessToken()).toBeNull();
  });

  it.each(['token_invalid', 'token_reused', 'account_disabled'])('%s kết thúc phiên ngay, không refresh', async (code) => {
    await saveTokens({ access_token: 'old', refresh_token: 'ref-old' });
    const refresh = jest.spyOn(axios, 'post');
    const onExpired = jest.fn();
    setSessionExpiredHandler(onExpired);
    const api = createApiClient('http://api');
    api.defaults.adapter = fakeAdapter({ '/a': [{ status: 401, data: { error: { code, message: '', details: [] } } }] }, []);

    await expect(api.get('/a')).rejects.toBeInstanceOf(AxiosError);
    expect(refresh).not.toHaveBeenCalled();
    expect(onExpired).toHaveBeenCalledTimes(1);
  });

  it('lỗi nghiệp vụ khác được trả nguyên cho màn hình xử lý', async () => {
    const onExpired = jest.fn();
    setSessionExpiredHandler(onExpired);
    const api = createApiClient('http://api');
    const notFound = { status: 404, data: { error: { code: 'exercise_not_found', message: '', details: [] } } };
    api.defaults.adapter = fakeAdapter({ '/a': [notFound] }, []);

    await expect(api.get('/a')).rejects.toMatchObject({ response: { status: 404 } });
    expect(onExpired).not.toHaveBeenCalled();
  });

  it('headers giả dùng AxiosHeaders', () => {
    expect(new AxiosHeaders().toJSON()).toEqual({});
  });
});
