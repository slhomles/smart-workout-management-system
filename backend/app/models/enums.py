"""
Enum Python — một nơi duy nhất, giá trị trùng khớp enum của DB (doc 05 §2.3).
Pydantic schema và model SQLAlchemy đều import từ đây.
"""

from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:  # giá trị khi format chuỗi/log
        return self.value


# --- auth ---
class UserStatus(StrEnum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    LOCKED = "locked"
    DISABLED = "disabled"


class UnitSystem(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class DevicePlatform(StrEnum):
    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class RoleCode(StrEnum):
    ADMIN = "admin"
    CONTENT_EDITOR = "content_editor"
    USER = "user"


class TokenRevokeReason(StrEnum):
    LOGOUT = "logout"
    ROTATED = "rotated"
    REUSE_DETECTED = "reuse_detected"
    PASSWORD_CHANGED = "password_changed"
    ADMIN_REVOKED = "admin_revoked"
    DEVICE_REVOKED = "device_revoked"


class LoginFailureReason(StrEnum):
    INVALID_CREDENTIALS = "invalid_credentials"
    ACCOUNT_LOCKED = "account_locked"
    ACCOUNT_DISABLED = "account_disabled"
    EMAIL_NOT_VERIFIED = "email_not_verified"
    OAUTH_ERROR = "oauth_error"


# --- catalog ---
class ContentStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ExerciseCategory(StrEnum):
    STRENGTH = "strength"
    CARDIO = "cardio"
    STRETCHING = "stretching"
    PLYOMETRIC = "plyometric"
    MOBILITY = "mobility"


class MechanicType(StrEnum):
    COMPOUND = "compound"
    ISOLATION = "isolation"


class ForceType(StrEnum):
    PUSH = "push"
    PULL = "pull"
    STATIC = "static"


class MuscleRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    STABILIZER = "stabilizer"


class MediaRole(StrEnum):
    THUMBNAIL = "thumbnail"
    GIF = "gif"
    VIDEO = "video"
    IMAGE = "image"


class JointType(StrEnum):
    NECK = "neck"
    SHOULDER = "shoulder"
    ELBOW = "elbow"
    WRIST = "wrist"
    SPINE = "spine"
    HIP = "hip"
    KNEE = "knee"
    ANKLE = "ankle"


# --- body ---
class Gender(StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    UNSPECIFIED = "unspecified"


class MeasurementSource(StrEnum):
    MANUAL = "manual"
    SMART_SCALE = "smart_scale"
    IMPORTED = "imported"


class GoalStatus(StrEnum):
    ACTIVE = "active"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"


# --- training ---
class PlanStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ScheduleStatus(StrEnum):
    PLANNED = "planned"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


class SessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SetType(StrEnum):
    WARMUP = "warmup"
    WORKING = "working"
    DROP = "drop"
    FAILURE = "failure"


class LogSource(StrEnum):
    MANUAL = "manual"
    AI_REALTIME = "ai_realtime"
    AI_VIDEO = "ai_video"


class AddedVia(StrEnum):
    PLAN = "plan"
    MANUAL = "manual"
    WIKI = "wiki"
    EQUIPMENT_SCAN = "equipment_scan"


# --- ai ---
class AnalysisMode(StrEnum):
    REALTIME_EDGE = "realtime_edge"
    VIDEO_SERVER = "video_server"


class IssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ScanFeedback(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"


class JobStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# --- media ---
class StorageProvider(StrEnum):
    S3 = "s3"
    FIREBASE = "firebase"


class MediaStatus(StrEnum):
    PENDING_UPLOAD = "pending_upload"
    AVAILABLE = "available"
    FAILED = "failed"
    QUARANTINED = "quarantined"


class PhotoAngle(StrEnum):
    FRONT = "front"
    SIDE = "side"
    BACK = "back"


class CaptureSource(StrEnum):
    CAMERA = "camera"
    LIBRARY = "library"


# --- analytics ---
class ReportType(StrEnum):
    WEEKLY_SUMMARY = "weekly_summary"
    MONTHLY_SUMMARY = "monthly_summary"
