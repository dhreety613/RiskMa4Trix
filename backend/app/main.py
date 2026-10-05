import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.config import get_settings

# Without this, INFO-level logs from the ingestion pipeline (including
# BackgroundTasks, which run detached from any request) never reach
# stdout - "no error logged" would silently look like "nothing ran".
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

settings = get_settings()

app = FastAPI(title="Ma3Trix API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
