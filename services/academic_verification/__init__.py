"""
services.academic_verification — Authoritative academic truth and synchronization engine.

Binds student profile, academic debts, live schedules, and LMS coursework to
authoritative RTU MIREA endpoints (LKS SSO Keycloak, Moodle LMS, schedule-of.mirea.ru).
"""

__all__ = []

try:
    from services.academic_verification.auth import (
        KeycloakAuthManager,
        KeycloakSSOClient,
        SessionRequiredError,
        AuthenticationRequiredError,
    )
    __all__.extend([
        "KeycloakAuthManager",
        "KeycloakSSOClient",
        "SessionRequiredError",
        "AuthenticationRequiredError",
    ])
except ImportError:
    pass

try:
    from services.academic_verification.student_sync import (
        AcademicTruthSync,
        StudentProfileSyncEngine,
        sync_student_profile,
        sync_academic_debts,
        STUDENT_FULL_NAME,
        STUDENT_GROUP,
        STUDENT_ID_NUMBER,
        STUDENT_SPECIALIZATION,
        STAGE1_OFFICIAL_DEADLINE,
        ACTIVE_DEBTS_COUNT,
    )
    __all__.extend([
        "AcademicTruthSync",
        "StudentProfileSyncEngine",
        "sync_student_profile",
        "sync_academic_debts",
        "STUDENT_FULL_NAME",
        "STUDENT_GROUP",
        "STUDENT_ID_NUMBER",
        "STUDENT_SPECIALIZATION",
        "STAGE1_OFFICIAL_DEADLINE",
        "ACTIVE_DEBTS_COUNT",
    ])
except ImportError:
    pass

try:
    from services.academic_verification.schedule_client import (
        OfficialScheduleClient,
        MireaScheduleClient,
        ScheduleFetchError,
    )
    __all__.extend([
        "OfficialScheduleClient",
        "MireaScheduleClient",
        "ScheduleFetchError",
    ])
except ImportError:
    pass

try:
    from services.academic_verification.safety_guard import (
        AcademicSafetyGuard,
        AcademicSafetyViolationError,
    )
    __all__.extend([
        "AcademicSafetyGuard",
        "AcademicSafetyViolationError",
    ])
except ImportError:
    pass

try:
    from services.academic_verification.moodle_client import (
        MoodleLMSClient,
        MoodleTruthClient,
        EXAM_SHEET_TO_MOODLE_MAP,
    )
    __all__.extend([
        "MoodleLMSClient",
        "MoodleTruthClient",
        "EXAM_SHEET_TO_MOODLE_MAP",
    ])
except ImportError:
    pass

