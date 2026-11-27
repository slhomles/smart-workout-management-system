"""Sổ đăng ký model cho `/health` (06-ai-contracts.md §2.2).

Mỗi module AI đăng ký model của mình lúc khởi động: tên khoá ("recovery", "equipment", ...) và
chuỗi phiên bản đang phục vụ. Model bắt buộc chưa sẵn sàng thì `/health` trả 503.
"""

from dataclasses import dataclass, field


@dataclass
class ModelStatus:
    version: str | None = None  # None = chưa nạp xong
    required: bool = True


@dataclass
class ModelRegistry:
    models: dict[str, ModelStatus] = field(default_factory=dict)

    def register(self, key: str, required: bool = True) -> None:
        self.models.setdefault(key, ModelStatus(required=required))

    def mark_ready(self, key: str, version: str) -> None:
        self.models.setdefault(key, ModelStatus()).version = version

    def is_ready(self) -> bool:
        return all(m.version is not None for m in self.models.values() if m.required)

    def versions(self) -> dict[str, str | None]:
        return {key: m.version for key, m in sorted(self.models.items())}


registry = ModelRegistry()
