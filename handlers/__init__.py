from handlers.admin import router as admin_router
from handlers.student import router as student_router
from handlers.booking import router as booking_router
from handlers.homework import router as homework_router
from handlers.payments import router as payments_router
from handlers.reviews import router as reviews_router
from handlers.analytics import router as analytics_router
from handlers.mailing import router as mailing_router
from handlers.referral import router as referral_router
__all__ = [
    "admin_router",
    "student_router",
    "booking_router",
    "homework_router",
    "payments_router",
    "reviews_router",
    "analytics_router",
    "mailing_router",
    "referral_router",
]
