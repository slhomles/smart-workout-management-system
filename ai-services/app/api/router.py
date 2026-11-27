"""Tổng hợp router của AI service. Mỗi module chỉ thêm đúng một dòng import và một dòng include_router
của mình, theo thứ tự bảng chữ cái (như backend, doc 05 §9.4). Đường dẫn theo 06-ai-contracts.md §2,
không có tiền tố `/api/v1`.
"""

from fastapi import APIRouter

from app.api import health

api_router = APIRouter()

api_router.include_router(health.router)
