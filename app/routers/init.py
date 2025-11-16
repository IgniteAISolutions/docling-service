"""
API Routers for Universal Product Automation
"""
from .pdf import router as pdf_router
from .image import router as image_router
from .sku import router as sku_router
from .url import router as url_router
from .brand_voice import router as brand_voice_router
from .export_csv import router as export_csv_router
from .seo import router as seo_router

__all__ = [
    "pdf_router",
    "image_router",
    "sku_router",
    "url_router",
    "brand_voice_router",
    "export_csv_router",
    "seo_router",
]
