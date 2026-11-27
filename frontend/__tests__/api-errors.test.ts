import { AxiosError, AxiosHeaders } from 'axios';

import { getErrorCode, getErrorMessage, getFieldErrors, NETWORK_ERROR } from '@/services/api/errors';

function apiError(status: number, data: unknown): AxiosError {
  const config = { headers: new AxiosHeaders() };
  return new AxiosError('fail', 'ERR', config, null, { status, statusText: '', headers: {}, config, data });
}

describe('getErrorCode', () => {
  it('đọc error.code chữ thường từ body lỗi chuẩn', () => {
    const err = apiError(404, { error: { code: 'exercise_not_found', message: 'Không có', details: [] } });
    expect(getErrorCode(err)).toBe('exercise_not_found');
  });

  it('trả network_error khi không có response', () => {
    expect(getErrorCode(new AxiosError('Network Error'))).toBe(NETWORK_ERROR);
  });

  it('trả null với lỗi không phải của axios hoặc body lạ', () => {
    expect(getErrorCode(new Error('x'))).toBeNull();
    expect(getErrorCode(apiError(500, '<html>'))).toBeNull();
  });
});

describe('getFieldErrors và getErrorMessage', () => {
  it('gom lỗi validation theo field', () => {
    const err = apiError(422, {
      error: {
        code: 'validation_error',
        message: 'Dữ liệu không hợp lệ',
        details: [
          { field: 'email', message: 'Email sai', code: 'value_error' },
          { field: null, message: 'Chung', code: 'x' },
        ],
      },
    });
    expect(getFieldErrors(err)).toEqual({ email: 'Email sai' });
    expect(getErrorMessage(err)).toBe('Dữ liệu không hợp lệ');
  });

  it('báo mất kết nối khi lỗi mạng', () => {
    expect(getErrorMessage(new AxiosError('Network Error'))).toBe('Không kết nối được máy chủ');
  });
});
