# app/main.py - Complete Universal API with React Frontend
import os
import logging
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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
    csv_parser = image_processor = text_processor = product_search = url_scraper = brand_voice = None

from app.config import ALLOWED_CATEGORIES

# Configuration
API_KEY = os.getenv("DOCLING_API_KEY", "")
FRONTEND_BUILD_DIR = Path(__file__).parent.parent / "frontend" / "build"

# Create FastAPI app
app = FastAPI(
    title="Universal Product Automation",
    description="Complete product automation backend with React frontend",
    version="2.0.0"
)

# CORS middleware
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

# Models
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
# API ENDPOINTS
# ============================================================

@app.get("/healthz")
async def healthz():
    """Health check endpoint"""
    return {
        "status": "ok",
        "version": "2.0.0",
        "openai_configured": bool(os.getenv("OPENAI_API_KEY")),
        "frontend_available": FRONTEND_BUILD_DIR.exists()
    }

@app.post("/api/parse-csv")
async def parse_csv_endpoint(
    file: UploadFile = File(...),
    category: str = Form(...),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """Parse CSV file and generate brand voice descriptions"""
    check_key(x_api_key)
    
    try:
        if category not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"Invalid category")
        
        logger.info(f"📊 Processing CSV upload for category: {category}")
        
        if not csv_parser:
            raise HTTPException(status_code=503, detail="CSV parser not available")
        
        file_content = await file.read()
        products = await csv_parser.process(file_content, category)
        logger.info(f"✅ Parsed {len(products)} products from CSV")
        
        if brand_voice:
            try:
                products = await brand_voice.generate(products, category)
                logger.info(f"✅ Brand voice generated")
            except Exception as e:
                logger.warning(f"⚠️ Brand voice failed: {e}")
        
        return ProcessingResponse(
            success=True,
            products=products,
            message=f"Successfully processed {len(products)} products"
        )
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/parse-image")
async def parse_image_endpoint(
    file: UploadFile = File(...),
    category: str = Form(...),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """Parse image via OCR and generate brand voice"""
    check_key(x_api_key)
    
    try:
        if category not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        
        logger.info(f"📸 Processing image for category: {category}")
        
        if not image_processor:
            raise HTTPException(status_code=503, detail="Image processor not available")
        
        file_content = await file.read()
        products = await image_processor.process(file_content, category, file.filename)
        
        if brand_voice:
            try:
                products = await brand_voice.generate(products, category)
            except Exception as e:
                logger.warning(f"⚠️ Brand voice failed: {e}")
        
        return ProcessingResponse(success=True, products=products)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/process-text")
async def process_text_endpoint(
    request: TextProcessorRequest,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """Process free-form text"""
    check_key(x_api_key)
    
    try:
        if request.category not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        
        if not text_processor:
            raise HTTPException(status_code=503, detail="Text processor not available")
        
        products = await text_processor.process(request.text, request.category)
        
        if brand_voice:
            products = await brand_voice.generate(products, request.category)
        
        return ProcessingResponse(success=True, products=products)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search-product")
async def search_product_endpoint(
    request: ProductSearchRequest,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """Search for product by SKU/EAN"""
    check_key(x_api_key)
    
    try:
        if request.category not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        
        if not product_search:
            raise HTTPException(status_code=503, detail="Product search not available")
        
        products = await product_search.search(request.query, request.category, request.search_type)
        
        if brand_voice:
            products = await brand_voice.generate(products, request.category)
        
        return ProcessingResponse(success=True, products=products)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scrape-url")
async def scrape_url_endpoint(
    request: URLScraperRequest,
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """Scrape URL for product data"""
    check_key(x_api_key)
    
    try:
        if request.category not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        
        if not url_scraper:
            raise HTTPException(status_code=503, detail="URL scraper not available")
        
        products = await url_scraper.scrape(request.url, request.category)
        
        if brand_voice:
            products = await brand_voice.generate(products, request.category)
        
        return ProcessingResponse(success=True, products=products)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/categories")
async def get_categories():
    """Get list of allowed categories"""
    return {"categories": sorted(list(ALLOWED_CATEGORIES))}

# ============================================================
# SERVE REACT FRONTEND
# ============================================================

# Mount static files
if FRONTEND_BUILD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_BUILD_DIR / "static")), name="static")
    
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """Serve React app for all non-API routes"""
        # If path starts with /api, let FastAPI handle it
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        
        # Check if specific file exists
        file_path = FRONTEND_BUILD_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        
        # Otherwise serve index.html (SPA fallback)
        return FileResponse(FRONTEND_BUILD_DIR / "index.html")
else:
    logger.warning("⚠️ Frontend build directory not found. Run 'cd frontend && npm run build'")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

# ============================================================
# SERVE REACT FRONTEND (Added)
# ============================================================

from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

FRONTEND_BUILD_DIR = Path(__file__).parent.parent / "frontend" / "build"

# Mount static files
if FRONTEND_BUILD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_BUILD_DIR / "static")), name="static")
    
    @app.get("/{full_path:path}")
    async def serve_react_app(full_path: str):
        """Serve React app for all non-API routes"""
        # If path starts with /api, let FastAPI handle it
        if full_path.startswith("api/"):
            from fastapi import HTTPException
            raise HTTPException(status_code=404)
        
        # Check if specific file exists
        file_path = FRONTEND_BUILD_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        
        # Otherwise serve index.html (SPA fallback)
        return FileResponse(FRONTEND_BUILD_DIR / "index.html")
else:
    logger.warning("⚠️ Frontend build directory not found")
