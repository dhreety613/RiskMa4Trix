from fastapi import APIRouter

from app.api.companies import router as companies_router
from app.api.drift import router as drift_router
from app.api.matrix import router as matrix_router
from app.api.risks import router as risks_router

router = APIRouter()
router.include_router(companies_router)
router.include_router(matrix_router)
router.include_router(drift_router)
router.include_router(risks_router)
