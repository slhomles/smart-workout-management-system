"""
Custom exception handlers for the application.
"""

from fastapi import HTTPException, status


class NotFoundException(HTTPException):
    """Resource not found."""
    def __init__(self, detail: str = "Không tìm thấy tài nguyên"):
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class UnauthorizedException(HTTPException):
    """Unauthorized access."""
    def __init__(self, detail: str = "Chưa đăng nhập hoặc token hết hạn"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenException(HTTPException):
    """Forbidden access."""
    def __init__(self, detail: str = "Không có quyền truy cập"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class BadRequestException(HTTPException):
    """Bad request."""
    def __init__(self, detail: str = "Yêu cầu không hợp lệ"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class ConflictException(HTTPException):
    """Resource conflict (duplicate)."""
    def __init__(self, detail: str = "Dữ liệu đã tồn tại"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)
