/**
 * Chạy một tác vụ bất đồng bộ và bỏ qua lần gọi mới khi lần trước chưa xong (chặn bấm hai lần).
 * Dùng cho đăng xuất, đăng xuất mọi thiết bị và các thao tác tài khoản sau.
 */
import { useRef, useState } from 'react';

export function useSingleFlight(task: () => Promise<void>) {
  const [isPending, setIsPending] = useState(false);
  // `isPending` chỉ có hiệu lực sau lần render kế tiếp; ref chặn ngay lần gọi thứ hai trong cùng khung hình.
  const isRunningRef = useRef(false);

  const run = async () => {
    if (isRunningRef.current) return;
    isRunningRef.current = true;
    setIsPending(true);
    try {
      await task();
    } finally {
      isRunningRef.current = false;
      setIsPending(false);
    }
  };

  return { run, isPending };
}
