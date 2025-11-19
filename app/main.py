# app/main.py - UNIFIED UNIVERSAL API
# Handles: PDF, CSV, Image, Text, URL, SKU/EAN search
# All endpoints working with proper CORS

import os
import logging
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import service modules
try:
    from app.services import csv_parser, image_processor, text_processor, product_search, url_scraper, brand_voice
    logger.info("✅ All service modules imported successfully")
except ImportError as e:
    logger.error(f"❌ Failed to import service modules: {e}")
    # Create stub implementations if imports fail
    csv_parser = None
    image_processor = None
    text_processor = None
    product_search = None
    url_scraper = None
    brand_voice = None

from app.config import ALLOWED_CATEGORIES

# Configuration
API_KEY = os.getenv("DOCLING_API_KEY", "")

# Create FastAPI app
app = FastAPI(
    title="Universal Product Automation",
    description="Complete product automation backend",
    version="2.0.0"
)

# CORS middleware - ALLOW ALL
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def check_key(x_api_key: Optional[str]):
    """Validate API key if configured"""
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# ============================================================
# MODELS
# ============================================================

class ProcessingResponse(BaseModel):
    success: bool
    products: List[dict]
    message: Optional[str] = None


class TextProcessorRequest(BaseModel):
    text: str
    category: str


class ProductSearchRequest(BaseModel):
    query: str
    category: str
    search_type: str = "sku"


class URLScraperRequest(BaseModel):
    url: str
    category: str


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/healthz")
async def healthz():
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": "2.0.0",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "services": {
            "csv_parser": csv_parser is not None,
            "image_processor": image_processor is not None,
            "text_processor": text_processor is not None,
            "product_search": product_search is not None,
            "url_scraper": url_scraper is not None,
            "brand_voice": brand_voice is not None,
        }
    }


# ============================================================
# CSV UPLOAD ENDPOINT
# ============================================================

@app.post("/api/parse-csv")
async def parse_csv_endpoint(
    file: UploadFile = File(...),
    category: str = Form(...),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """
    Parse CSV file and generate brand voice descriptions
    """
    check_key(x_api_key)
    
    try:
        # Validate category
        if category not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
            )

        logger.info(f"📊 Processing CSV upload for category: {category}")

        if not csv_parser:
            raise HTTPException(status_code=503, detail="CSV parser not available")

        # 1. Parse CSV
        file_content = await file.read()
        products = await csv_parser.process(file_content, category)
        logger.info(f"✅ Parsed {len(products)} products from CSV")

        # 2. Generate brand voice
        if brand_voice:
            try:
                products = await brand_voice.generate(products, category)
                logger.info(f"✅ Brand voice generated for {len(products)} products")
            except Exception as e:
                logger.warning(f"⚠️ Brand voice failed: {e}")

        return ProcessingResponse(
            success=True,
            products=products,
            message=f"Successfully processed {len(products)} products"
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


# ============================================================
# IMAGE UPLOAD ENDPOINT
# ============================================================

@app.post("/api/parse-image")
async def parse_image_endpoint(
    file: UploadFile = File(...),
    category: str = Form(...),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """
    Parse image file via OCR and generate brand voice descriptions
    """
    check_key(x_api_key)
    
    try:
        # Validate category
        if category not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
            )

        logger.info(f"📸 Processing image upload for category: {category}")

        if not image_processor:
            raise HTTPException(status_code=503, detail="Image processor not available")

        # 1. Process image (OCR)
        file_content = await file.read()
        products = await image_processor.process(file_content, category, file.filename)
        logger.info(f"✅ Extracted {len(products)} products from image")

        # 2. Generate brand voice
        if brand_voice:
            try:
                products = await brand_voice.generate(products, category)
                logger.info(f"✅ Brand voice generated for {len(products)} products")
            except Exception as e:
                logger.warning(f"⚠️ Brand voice failed: {e}")

        return ProcessingResponse(
            success=True,
            products=products,
            message=f"Successfully processed {len(products)} products from image"
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


# ============================================================
# TEXT PROCESSING ENDPOINT
# ============================================================

@app.post("/api/process-text")
async def process_text_endpoint(
    request: TextProcessorRequest,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """
    Process free-form text and generate brand voice descriptions
    """
    check_key(x_api_key)
    
    try:
        # Validate category
        if request.category not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
            )

        logger.info(f"📝 Processing text input ({len(request.text)} chars)")

        if not text_processor:
            raise HTTPException(status_code=503, detail="Text processor not available")

        # 1. Process text
        products = await text_processor.process(request.text, request.category)
        logger.info(f"✅ Extracted {len(products)} products from text")

        # 2. Generate brand voice
        if brand_voice:
            try:
                products = await brand_voice.generate(products, request.category)
                logger.info(f"✅ Brand voice generated for {len(products)} products")
            except Exception as e:
                logger.warning(f"⚠️ Brand voice failed: {e}")

        return ProcessingResponse(
            success=True,
            products=products,
            message=f"Successfully processed {len(products)} products from text"
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


# ============================================================
# PRODUCT SEARCH ENDPOINT (SKU/EAN)
# ============================================================

@app.post("/api/search-product")
async def search_product_endpoint(
    request: ProductSearchRequest,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """
    Search for product by SKU/EAN and generate brand voice descriptions
    """
    check_key(x_api_key)
    
    try:
        # Validate category
        if request.category not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
            )

        logger.info(f"🔍 Searching for {request.search_type}: {request.query}")

        if not product_search:
            raise HTTPException(status_code=503, detail="Product search not available")

        # 1. Search product
        products = await product_search.search(
            request.query,
            request.category,
            request.search_type
        )
        logger.info(f"✅ Found {len(products)} products")

        # 2. Generate brand voice
        if brand_voice:
            try:
                products = await brand_voice.generate(products, request.category)
                logger.info(f"✅ Brand voice generated for {len(products)} products")
            except Exception as e:
                logger.warning(f"⚠️ Brand voice failed: {e}")

        return ProcessingResponse(
            success=True,
            products=products,
            message=f"Successfully found {len(products)} products"
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


# ============================================================
# URL SCRAPER ENDPOINT
# ============================================================

@app.post("/api/scrape-url")
async def scrape_url_endpoint(
    request: URLScraperRequest,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """
    Scrape URL for product data and generate brand voice descriptions
    """
    check_key(x_api_key)
    
    try:
        # Validate category
        if request.category not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
            )

        logger.info(f"🌐 Scraping URL: {request.url}")

        if not url_scraper:
            raise HTTPException(status_code=503, detail="URL scraper not available")

        # 1. Scrape URL
        products = await url_scraper.scrape(request.url, request.category)
        logger.info(f"✅ Scraped {len(products)} products from URL")

        # 2. Generate brand voice
        if brand_voice:
            try:
                products = await brand_voice.generate(products, request.category)
                logger.info(f"✅ Brand voice generated for {len(products)} products")
            except Exception as e:
                logger.warning(f"⚠️ Brand voice failed: {e}")

        return ProcessingResponse(
            success=True,
            products=products,
            message=f"Successfully scraped {len(products)} products from URL"
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


# ============================================================
# CATEGORIES ENDPOINT
# ============================================================

@app.get("/api/categories")
async def get_categories():
    """Get list of allowed categories"""
    return {
        "categories": sorted(list(ALLOWED_CATEGORIES))
    }


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
        }
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
