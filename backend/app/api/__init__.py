from fastapi import APIRouter

from app.api.companies import router as companies_router

router = APIRouter()
router.include_router(companies_router)
