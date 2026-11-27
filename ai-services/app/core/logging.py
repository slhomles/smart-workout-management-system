"""Logging dạng một dòng; KHÔNG log ảnh, video, token hay dữ liệu cá nhân (06-ai-contracts.md §5)."""

import logging


def setup_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")
