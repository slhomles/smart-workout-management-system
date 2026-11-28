"""
Nghiệp vụ route worker video `/ai/video-jobs/...` (06-ai-contracts §3): nhận job, tải video gốc,
báo kết quả hoặc lỗi.

Chuyển trạng thái job dùng lại `video_job_service.start_job`/`record_result`/`record_failure`;
module này không sửa `video_job_service`, chỉ thêm phần hàng đợi, đọc/ghi file và ngữ cảnh worker cần.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.crud import video_job as crud
from app.schemas.video_job import ClaimedVideoJobResponse
from app.services import video_job_service

# Giới hạn video kết quả worker gửi lên, chặn request làm đầy bộ nhớ/kho; hằng số tạm (spec §6 ý 6.5, Q6).
MAX_RESULT_VIDEO_BYTES = 200 * 1024 * 1024


async def claim_next_job(db: AsyncSession, worker_id: str) -> ClaimedVideoJobResponse | None:
    """Nhận job `queued` ưu tiên cao nhất rồi cũ nhất, chuyển `processing`; None nếu hàng đợi trống."""
    job_id = await crud.claim_next_job_id(db)
    if job_id is None:
        return None
    # start_job khoá lại dòng trong cùng transaction, kiểm lượt thử rồi commit (nhả khoá SKIP LOCKED).
    await video_job_service.start_job(db, job_id, worker_id)
    # Luôn có dòng: câu claim đã đòi buổi chưa xoá (EXISTS trên view) và FK media nguồn NOT NULL.
    context = await crud.get_claim_context(db, job_id)
    return ClaimedVideoJobResponse.model_validate(context)
