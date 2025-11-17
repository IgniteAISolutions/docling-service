"""
Universal Product Automation - FastAPI Application
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings

# Import routers
from .routers import (
    image_router,
    sku_router,
    url_router,
    brand_voice_router,
    export_csv_router,
    seo_router,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Universal Product Automation",
    description="Harts Product Automation API",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(export_csv_router)
app.include_router(url_router)
app.include_router(sku_router)
app.include_router(image_router)
app.include_router(brand_voice_router)
app.include_router(seo_router)


@app.get("/")
async def root():
    return {
        "service": "Universal Product Automation",
        "version": "2.0.0",
        "status": "running"
    }


@app.get("/healthz")
async def health_check():
    return {"status": "healthy", "version": "2.0.0"}
