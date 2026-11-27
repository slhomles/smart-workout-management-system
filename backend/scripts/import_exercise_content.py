"""Nhập nội dung bài tập (GIF, thumbnail, ảnh, bài mới, hướng dẫn tiếng Việt) vào DB app + S3.

Nguồn theo AGENT_RESOURCES.md §1: `resources/exercises-dataset` (GIF, thumbnail) và `resources/free-exercise-db`
(ảnh JPG), ghép và dịch sẵn trong `data/` (exercise_map.json, new_exercises.json). Script chạy lại được nhiều lần:
file đã có trên S3 cùng kích thước thì bỏ qua, bài đã có slug thì không thêm lại.

KHÔNG chạy trên DB test (`POSTGRES_DB` trong backend/.env): test của catalog khẳng định đúng 71 bài.

    cd backend
    .venv\\Scripts\\python scripts\\import_exercise_content.py --database smart_workout_app [--dry-run] [--limit 5]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import asyncpg
import boto3
from botocore.exceptions import ClientError

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from app.core.config import get_settings  # noqa: E402

DATA = REPO / "data"
EXDS = REPO / "resources" / "exercises-dataset"
FEDB = REPO / "resources" / "free-exercise-db" / "exercises"
logger = logging.getLogger("import_exercise_content")


@dataclass(frozen=True)
class MediaItem:
    role: str  # catalog.media_role
    path: Path
    key: str
    mime: str
    order: int


def media_plan(slug: str, exds: dict | None, fedb_images: list[str]) -> list[MediaItem]:
    """GIF + thumbnail từ exercises-dataset; tối đa 2 ảnh JPG từ free-exercise-db (luân phiên khi không có GIF)."""
    base = f"catalog/exercises/{slug}"
    items = []
    if exds:
        items.append(MediaItem("gif", EXDS / exds["gif_url"], f"{base}/demo.gif", "image/gif", 0))
        items.append(MediaItem("thumbnail", EXDS / exds["image"], f"{base}/thumbnail.jpg", "image/jpeg", 0))
    for i, rel in enumerate(fedb_images[:2]):
        items.append(MediaItem("image", FEDB / rel, f"{base}/image-{i}.jpg", "image/jpeg", i))
    return [m for m in items if m.path.is_file()]


class Uploader:
    def __init__(self, dry_run: bool) -> None:
        s = get_settings()
        self.bucket, self.dry_run = s.AWS_S3_BUCKET, dry_run
        self.client = boto3.client("s3", aws_access_key_id=s.AWS_ACCESS_KEY_ID,
                                   aws_secret_access_key=s.AWS_SECRET_ACCESS_KEY, region_name=s.AWS_S3_REGION)

    def _remote_size(self, key: str) -> int | None:
        try:
            return int(self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"])
        except ClientError:
            return None

    def put(self, item: MediaItem) -> tuple[int, str]:
        data = item.path.read_bytes()
        if not self.dry_run and self._remote_size(item.key) != len(data):
            self.client.put_object(Bucket=self.bucket, Key=item.key, Body=data, ContentType=item.mime)
        return len(data), hashlib.sha256(data).hexdigest()


async def upsert_media(conn: asyncpg.Connection, exercise_id: int, item: MediaItem, stored: tuple[int, str]) -> None:
    """Dòng media cùng object_key (seed cũ trỏ bucket khác) thì sửa bucket/size/checksum; chưa có thì thêm."""
    size, checksum = stored
    bucket = get_settings().AWS_S3_BUCKET
    media_id = await conn.fetchval(
        "SELECT f.id FROM catalog.exercise_media em JOIN media.media_files f ON f.id = em.media_id "
        "WHERE em.exercise_id = $1 AND f.object_key = $2", exercise_id, item.key)
    if media_id:
        await conn.execute("UPDATE media.media_files SET bucket = $2, size_bytes = $3, checksum_sha256 = $4, "
                           "mime_type = $5, status = 'available', updated_at = now() WHERE id = $1",
                           media_id, bucket, size, checksum, item.mime)
        return
    media_id = await conn.fetchval(
        "INSERT INTO media.media_files (bucket, object_key, original_filename, mime_type, size_bytes, checksum_sha256, "
        "status) VALUES ($1, $2, $3, $4, $5, $6, 'available') RETURNING id",
        bucket, item.key, item.path.name, item.mime, size, checksum)
    has_primary = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM catalog.exercise_media WHERE exercise_id = $1 "
                                      "AND media_role = $2::catalog.media_role AND is_primary)", exercise_id, item.role)
    await conn.execute("INSERT INTO catalog.exercise_media (exercise_id, media_id, media_role, is_primary, display_order) "
                       "VALUES ($1, $2, $3::catalog.media_role, $4, $5)",
                       exercise_id, media_id, item.role, not has_primary, item.order)


async def insert_exercise(conn: asyncpg.Connection, ex: dict) -> int | None:
    """Thêm bài mới (published) cùng nhóm cơ, thiết bị, các bước; slug đã có thì bỏ qua."""
    exercise_id = await conn.fetchval(
        "INSERT INTO catalog.exercises (slug, name, name_en, description, difficulty_level_id, category, mechanic, "
        "force_type, is_unilateral, status, published_at) SELECT $1, $2, $3, $4, d.id, $6::catalog.exercise_category, "
        "$7::catalog.mechanic_type, $8::catalog.force_type, $9, 'published', now() FROM catalog.difficulty_levels d "
        "WHERE d.code = $5 ON CONFLICT (slug) DO NOTHING RETURNING id",
        ex["slug"], ex["name"], ex["name_en"], ex["description"], ex["difficulty"], ex["category"],
        ex.get("mechanic"), ex.get("force_type"), bool(ex.get("is_unilateral")))
    if exercise_id is None:
        return None
    for m in ex["muscles"]:
        await conn.execute("INSERT INTO catalog.exercise_muscles (exercise_id, muscle_group_id, role, activation_ratio) "
                           "SELECT $1, id, $3::catalog.muscle_role, $4 FROM catalog.muscle_groups WHERE code = $2",
                           exercise_id, m["code"], m["role"], m["activation_ratio"])
    for code in ex["equipment"]:
        await conn.execute("INSERT INTO catalog.exercise_equipment (exercise_id, equipment_id) "
                           "SELECT $1, id FROM catalog.equipment WHERE code = $2", exercise_id, code)
    for step_no, text in enumerate(ex["instructions_vi"], start=1):
        await conn.execute("INSERT INTO catalog.exercise_instructions (exercise_id, step_no, content) VALUES ($1, $2, $3)",
                           exercise_id, step_no, text)
    return exercise_id


def load_sources() -> tuple[dict, dict, list[dict]]:
    exds = {x["id"]: x for x in json.loads((EXDS / "data" / "exercises.json").read_text(encoding="utf-8"))}
    fedb = {x["id"]: x for x in json.loads((FEDB.parent / "dist" / "exercises.json").read_text(encoding="utf-8"))}
    mapping = json.loads((DATA / "exercise_map.json").read_text(encoding="utf-8"))
    new = json.loads((DATA / "new_exercises.json").read_text(encoding="utf-8"))
    targets = [{"slug": slug, **m, "is_new": False} for slug, m in mapping.items() if m.get("confidence") != "low"]
    targets += [{**ex, "is_new": True} for ex in new]
    return exds, fedb, targets


async def import_one(conn: asyncpg.Connection, up: Uploader, target: dict, sources: tuple[dict, dict]) -> str:
    exds, fedb = sources
    async with conn.transaction():
        exercise_id = await (insert_exercise(conn, target) if target["is_new"] else conn.fetchval(
            "SELECT id FROM catalog.exercises WHERE slug = $1", target["slug"]))
        if exercise_id is None:
            exercise_id = await conn.fetchval("SELECT id FROM catalog.exercises WHERE slug = $1", target["slug"])
        if exercise_id is None:
            return "bỏ qua (không có trong DB)"
        images = fedb.get(target.get("fedb_id") or "", {}).get("images", [])
        plan = media_plan(target["slug"], exds.get(target.get("exds_id") or ""), images)
        for item in plan:
            await upsert_media(conn, exercise_id, item, up.put(item))
    return f"{len(plan)} media"


async def run(args: argparse.Namespace) -> None:
    s = get_settings()
    if args.database == s.POSTGRES_DB and not args.allow_test_db:
        raise SystemExit(f"{args.database} là DB test (POSTGRES_DB); dùng DB app hoặc thêm --allow-test-db")
    exds, fedb, targets = load_sources()
    conn = await asyncpg.connect(host=s.POSTGRES_HOST, port=s.POSTGRES_PORT, user=s.POSTGRES_USER,
                                 password=s.POSTGRES_PASSWORD, database=args.database)
    up = Uploader(args.dry_run)
    outer = conn.transaction()
    await outer.start()
    try:
        for target in targets[: args.limit or None]:
            logger.info("%s: %s", target["slug"], await import_one(conn, up, target, (exds, fedb)))
        published = await conn.fetchval("SELECT count(*) FROM catalog.exercises WHERE status = 'published'")
        logger.info("%s: %s bài đã xuất bản trong %s", "dry-run" if args.dry_run else "xong", published, args.database)
    except BaseException:
        await outer.rollback()
        raise
    else:
        await (outer.rollback() if args.dry_run else outer.commit())
    finally:
        await conn.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--database", required=True, help="DB đích, vd smart_workout_app")
    ap.add_argument("--dry-run", action="store_true", help="chạy đủ bước rồi rollback DB, không upload S3")
    ap.add_argument("--limit", type=int, default=0, help="chỉ xử lý N bài đầu (thử)")
    ap.add_argument("--allow-test-db", action="store_true", help="cho phép chạy trên POSTGRES_DB (KHÔNG khuyến nghị)")
    asyncio.run(run(ap.parse_args()))


if __name__ == "__main__":
    main()
