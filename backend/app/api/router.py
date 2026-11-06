from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.domain import router as domain_router
from app.api.routes.vnpay import router as vnpay_router
from app.api.routes.tutoring_files import router as tutoring_files_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(domain_router)
api_router.include_router(vnpay_router)
api_router.include_router(tutoring_files_router)
