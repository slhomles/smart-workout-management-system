/** Trang kết quả phân trang cursor, dùng chung cho mọi danh sách (`Claude_api_respone.md` §5). */
export type Page<T> = {
  data: T[];
  pagination: { next_cursor: string | null; has_more: boolean };
};
