import { toDevicePlatform } from '@/utils/device';
import { formatDate, formatNumber, formatRetryAfter, parseDateVi, parseDecimalVi } from '@/utils/format';
import { formatWeight, kgToLb, lbToKg } from '@/utils/units';
import { checkDisplayName, checkPasswordPolicy, isValidEmail } from '@/utils/validation';

// Chuỗi kỳ vọng chép nguyên từ spec fe-auth §2.4 (không dùng lại hằng của code để bắt lỗi chính tả).
const PASSWORD_MESSAGE = 'Mật khẩu cần 8–72 byte, có ít nhất 1 chữ cái và 1 chữ số';
const DISPLAY_NAME_MESSAGE = 'Tên hiển thị cần 1–50 ký tự';
// "é" dạng dựng sẵn U+00E9: 1 ký tự, 2 byte UTF-8 (viết escape để không phụ thuộc chuẩn hoá Unicode của editor).
const E_ACUTE = 'é';

describe('validation (spec fe-auth §2.3)', () => {
  it.each([
    { label: 'Demo@123', password: 'Demo@123' },
    { label: '8 byte', password: 'Abcdefg1' },
    { label: '72 byte', password: 'a1' + 'b'.repeat(70) },
    { label: '71 byte có chữ có dấu', password: 'Aa1' + E_ACUTE.repeat(34) },
  ])('FEAUTH-01 checkPasswordPolicy hợp lệ ($label) trả null', ({ password }) => {
    expect(checkPasswordPolicy(password)).toBeNull();
  });

  it.each([
    { label: '7 byte', password: 'Abcdef1' },
    { label: '73 byte', password: 'a1' + 'b'.repeat(71) },
    { label: '38 ký tự nhưng 73 byte', password: 'Aa1' + E_ACUTE.repeat(35) },
    { label: 'không có chữ số', password: 'abcdefgh' },
    { label: 'không có chữ cái', password: '12345678' },
  ])('FEAUTH-01 checkPasswordPolicy không hợp lệ ($label) trả thông điệp chính sách', ({ password }) => {
    expect(checkPasswordPolicy(password)).toBe(PASSWORD_MESSAGE);
  });

  it('FEAUTH-01 checkPasswordPolicy đếm byte UTF-8 chứ không đếm ký tự', () => {
    const password = 'Aa1' + E_ACUTE.repeat(35);
    expect(password).toHaveLength(38);
    expect(checkPasswordPolicy(password)).toBe(PASSWORD_MESSAGE);
  });

  it('FEAUTH-01 isValidEmail chỉ chấp nhận email đúng định dạng và tối đa 254 ký tự', () => {
    const longEmail = 'a'.repeat(243) + '@example.com';
    expect(longEmail).toHaveLength(255);

    expect(isValidEmail('demo@smartworkout.local')).toBe(true);
    expect(isValidEmail('khong-phai-email')).toBe(false);
    expect(isValidEmail('a@b')).toBe(false);
    expect(isValidEmail('a b@c.d')).toBe(false);
    expect(isValidEmail(longEmail)).toBe(false);
  });

  it('FEAUTH-01 isValidEmail chấp nhận đúng 254 ký tự', () => {
    const email = 'a'.repeat(242) + '@example.com';
    expect(email).toHaveLength(254);
    expect(isValidEmail(email)).toBe(true);
  });

  it('FEAUTH-01 checkDisplayName bỏ khoảng trắng hai đầu và giới hạn 1–50 ký tự', () => {
    expect(checkDisplayName(' An ')).toEqual({ value: 'An', error: null });
    expect(checkDisplayName('a'.repeat(50))).toEqual({ value: 'a'.repeat(50), error: null });
    expect(checkDisplayName('   ')).toEqual({ value: '', error: DISPLAY_NAME_MESSAGE });
    expect(checkDisplayName('a'.repeat(51)).error).toBe(DISPLAY_NAME_MESSAGE);
  });

  it('FEAUTH-01 checkDisplayName đếm ký tự có dấu là 1 ký tự', () => {
    expect(checkDisplayName(E_ACUTE.repeat(50)).error).toBeNull();
    expect(checkDisplayName(E_ACUTE.repeat(51)).error).toBe(DISPLAY_NAME_MESSAGE);
  });
});

describe('format, units, device (spec fe-auth §2.3)', () => {
  it('FEAUTH-02 formatNumber theo vi-VN, tối đa 1 chữ số thập phân', () => {
    expect(formatNumber(1234.5)).toBe('1.234,5');
    expect(formatNumber(66)).toBe('66');
    expect(formatNumber(145.5051)).toBe('145,5');
    expect(formatNumber(1.236, 2)).toBe('1,24');
  });

  it('FEAUTH-02 kgToLb và lbToKg theo 1 lb = 0,45359237 kg', () => {
    expect(kgToLb(66)).toBeCloseTo(145.505, 3);
    expect(lbToKg(154)).toBeCloseTo(69.853, 3);
  });

  it('FEAUTH-02 formatWeight theo unit_system, null coi như metric', () => {
    expect(formatWeight(66, 'metric')).toBe('66 kg');
    expect(formatWeight(70.5, 'metric')).toBe('70,5 kg');
    expect(formatWeight(66, 'imperial')).toBe('145,5 lb');
    expect(formatWeight(66, null)).toBe('66 kg');
  });

  it('FEAUTH-02 formatDate đổi yyyy-mm-dd sang dd/mm/yyyy không lệch múi giờ', () => {
    expect(formatDate('2027-03-01')).toBe('01/03/2027');
    expect(formatDate('2027-12-31')).toBe('31/12/2027');
  });

  it('FEAUTH-02 formatDate giữ nguyên chuỗi không đúng dạng yyyy-mm-dd', () => {
    expect(formatDate('01/03/2027')).toBe('01/03/2027');
  });

  it('FEAUTH-02 parseDateVi đổi dd/mm/yyyy hợp lệ sang yyyy-mm-dd', () => {
    expect(parseDateVi('01/03/2027')).toBe('2027-03-01');
    expect(parseDateVi('29/02/2028')).toBe('2028-02-29');
    expect(parseDateVi('29/02/2000')).toBe('2000-02-29');
    expect(parseDateVi('31/12/2027')).toBe('2027-12-31');
  });

  it.each(['30/02/2027', '1/3/27', '29/02/2027', '29/02/2100', '31/04/2027', '00/01/2027', '01/13/2027', '01/00/2027', '01/01/0000', '', '2027-03-01'])(
    'FEAUTH-02 parseDateVi trả null với "%s"',
    (text) => {
      expect(parseDateVi(text)).toBeNull();
    },
  );

  it('FEAUTH-02 parseDecimalVi nhận dấu phẩy hoặc dấu chấm thập phân', () => {
    expect(parseDecimalVi('70,5')).toBe(70.5);
    expect(parseDecimalVi('70.5')).toBe(70.5);
    expect(parseDecimalVi('154')).toBe(154);
    expect(parseDecimalVi(' 70,5 ')).toBe(70.5);
  });

  it.each(['abc', '', '   ', '70,', ',5', '1.234,5', '70,5kg'])('FEAUTH-02 parseDecimalVi trả null với "%s"', (text) => {
    expect(parseDecimalVi(text)).toBeNull();
  });

  it('FEAUTH-02 formatRetryAfter làm tròn lên số phút', () => {
    expect(formatRetryAfter(840)).toBe('14 phút');
    expect(formatRetryAfter(1)).toBe('1 phút');
    expect(formatRetryAfter(61)).toBe('2 phút');
  });

  it('FEAUTH-02 toDevicePlatform giữ ios/android, hệ khác thành web', () => {
    expect(toDevicePlatform('ios')).toBe('ios');
    expect(toDevicePlatform('android')).toBe('android');
    expect(toDevicePlatform('web')).toBe('web');
    expect(toDevicePlatform('windows')).toBe('web');
  });
});
