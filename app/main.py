"""
Universal Product Automation Backend
FastAPI application with complete Elestio consolidation
"""
import os
import logging
from typing import List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware

from .models import (
    Product,
    ProcessingResponse,
    HealthResponse,
    ProductSearchRequest,
    URLScraperRequest,
    TextProcessorRequest,
    ExportCSVRequest
)
from .services import (
    csv_parser,
    image_processor,
    product_search,
    url_scraper,
    text_processor,
    brand_voice,
    seo_lighthouse
)
from .utils import normalizers, csv_exporter
from .config import ALLOWED_CATEGORIES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Universal Product Automation",
    description="Complete product automation backend with brand voice generation",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    return {"status":"ok"}
        status="ok",
        version="1.0.0",
        openai_configured=bool(os.getenv("OPENAI_API_KEY"))
    )


@app.post("/api/parse-csv", response_model=ProcessingResponse)
async def parse_csv_endpoint(
    file: UploadFile = File(...),
    category: str = Form(...)
):
    """
    Parse CSV file and generate brand voice descriptions
    Args:
        file: CSV file upload
        category: Product category
    Returns:
        ProcessingResponse with enhanced products
    """
    try:
        # Validate category
        if category not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
            )

        logger.info(f"Processing CSV upload for category: {category}")

        # 1. Parse CSV
        file_content = await file.read()
        products = await csv_parser.process(file_content, category)

        logger.info(f"Parsed {len(products)} products from CSV")

        # 2. Normalize structure
        products = normalizers.normalize_products(products, category)

        # 3. Generate brand voice (includes retry logic)
        products = await brand_voice.generate(products, category)

        # 4. SEO validation & auto-fix
        for product in products:
            descriptions = product.get("descriptions", {})
            meta = descriptions.get("metaDescription", "")

            # Extract keywords from product
            keywords = seo_lighthouse.extract_keywords_from_product(product)

            # Validate and fix meta description
            seo_result = await seo_lighthouse.validate_and_fix_meta(
                meta,
                product.get("name", ""),
                keywords
            )

            # Update with fixed meta
            product["descriptions"]["metaDescription"] = seo_result["fixed"]

            # Store validation result for logging
            product["_seo_validation"] = seo_result

        logger.info(f"Successfully processed {len(products)} products")

        return ProcessingResponse(
            success=True,
            products=products
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.post("/api/parse-image", response_model=ProcessingResponse)
async def parse_image_endpoint(
    file: UploadFile = File(...),
    category: str = Form(...)
):
    """
    Parse image file via OCR and generate brand voice descriptions
    Args:
        file: Image file upload
        category: Product category
    Returns:
        ProcessingResponse with enhanced products
    """
    try:
        # Validate category
        if category not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
            )

        logger.info(f"Processing image upload for category: {category}")

        # 1. Process image (OCR)
        file_content = await file.read()
        products = await image_processor.process(file_content, category, file.filename)

        # 2. Normalize structure
        products = normalizers.normalize_products(products, category)

        # 3. Generate brand voice
        products = await brand_voice.generate(products, category)

        # 4. SEO validation & auto-fix
        for product in products:
            descriptions = product.get("descriptions", {})
            meta = descriptions.get("metaDescription", "")
            keywords = seo_lighthouse.extract_keywords_from_product(product)

            seo_result = await seo_lighthouse.validate_and_fix_meta(
                meta,
                product.get("name", ""),
                keywords
            )

            product["descriptions"]["metaDescription"] = seo_result["fixed"]
            product["_seo_validation"] = seo_result

        logger.info(f"Successfully processed {len(products)} products from image")

        return ProcessingResponse(
            success=True,
            products=products
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.post("/api/search-product", response_model=ProcessingResponse)
async def search_product_endpoint(request: ProductSearchRequest):
    """
    Search for product by SKU/EAN and generate brand voice descriptions
    Args:
        request: ProductSearchRequest with query, category, search_type
    Returns:
        ProcessingResponse with enhanced products
    """
    try:
        # Validate category
        if request.category not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
            )

        logger.info(f"Searching for {request.search_type}: {request.query}")

        # 1. Search product
        products = await product_search.search(
            request.query,
            request.category,
            request.search_type
        )

        # 2. Normalize structure
        products = normalizers.normalize_products(products, request.category)

        # 3. Generate brand voice
        products = await brand_voice.generate(products, request.category)

        # 4. SEO validation & auto-fix
        for product in products:
            descriptions = product.get("descriptions", {})
            meta = descriptions.get("metaDescription", "")
            keywords = seo_lighthouse.extract_keywords_from_product(product)

            seo_result = await seo_lighthouse.validate_and_fix_meta(
                meta,
                product.get("name", ""),
                keywords
            )

            product["descriptions"]["metaDescription"] = seo_result["fixed"]
            product["_seo_validation"] = seo_result

        logger.info(f"Successfully processed {len(products)} products from search")

        return ProcessingResponse(
            success=True,
            products=products
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.post("/api/scrape-url", response_model=ProcessingResponse)
async def scrape_url_endpoint(request: URLScraperRequest):
    """
    Scrape URL for product data and generate brand voice descriptions
    Args:
        request: URLScraperRequest with url and category
    Returns:
        ProcessingResponse with enhanced products
    """
    try:
        # Validate category
        if request.category not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
            )

        logger.info(f"Scraping URL: {request.url}")

        # 1. Scrape URL
        products = await url_scraper.scrape(request.url, request.category)

        # 2. Normalize structure
        products = normalizers.normalize_products(products, request.category)

        # 3. Generate brand voice
        products = await brand_voice.generate(products, request.category)

        # 4. SEO validation & auto-fix
        for product in products:
            descriptions = product.get("descriptions", {})
            meta = descriptions.get("metaDescription", "")
            keywords = seo_lighthouse.extract_keywords_from_product(product)

            seo_result = await seo_lighthouse.validate_and_fix_meta(
                meta,
                product.get("name", ""),
                keywords
            )

            product["descriptions"]["metaDescription"] = seo_result["fixed"]
            product["_seo_validation"] = seo_result

        logger.info(f"Successfully processed {len(products)} products from URL")

        return ProcessingResponse(
            success=True,
            products=products
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.post("/api/process-text", response_model=ProcessingResponse)
async def process_text_endpoint(request: TextProcessorRequest):
    """
    Process free-form text and generate brand voice descriptions
    Args:
        request: TextProcessorRequest with text and category
    Returns:
        ProcessingResponse with enhanced products
    """
    try:
        # Validate category
        if request.category not in ALLOWED_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {', '.join(ALLOWED_CATEGORIES)}"
            )

        logger.info(f"Processing text input ({len(request.text)} chars)")

        # 1. Process text
        products = await text_processor.process(request.text, request.category)

        # 2. Normalize structure
        products = normalizers.normalize_products(products, request.category)

        # 3. Generate brand voice
        products = await brand_voice.generate(products, request.category)

        # 4. SEO validation & auto-fix
        for product in products:
            descriptions = product.get("descriptions", {})
            meta = descriptions.get("metaDescription", "")
            keywords = seo_lighthouse.extract_keywords_from_product(product)

            seo_result = await seo_lighthouse.validate_and_fix_meta(
                meta,
                product.get("name", ""),
                keywords
            )

            product["descriptions"]["metaDescription"] = seo_result["fixed"]
            product["_seo_validation"] = seo_result

        logger.info(f"Successfully processed {len(products)} products from text")

        return ProcessingResponse(
            success=True,
            products=products
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@app.post("/api/export-csv")
async def export_csv_endpoint(request: Request):
    """
    Export products to CSV with BOM, sanitization, and dynamic columns
    Args:
        request: Request with JSON body containing products array
    Returns:
        CSV file with UTF-8 BOM
    Headers:
        x-prefer-p-tags: "true" or "false" (default: true)
    """
    try:
        # Parse request body
        body = await request.json()
        products = body.get("products", [])

        if not products:
            raise HTTPException(status_code=400, detail="No products provided")

        # Get preference for <p> tags vs <br> tags
        prefer_p_tags = request.headers.get("x-prefer-p-tags", "true").lower() != "false"

        logger.info(f"Exporting {len(products)} products to CSV (prefer_p_tags={prefer_p_tags})")

        # Generate CSV
        csv_content = csv_exporter.generate_csv(products, prefer_p_tags)

        # Return CSV response
        return Response(
            content=csv_content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="harts_products_export.csv"'
            }
        )

    except Exception as e:
        logger.error(f"Export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@app.get("/api/categories")
async def get_categories():
    """Get list of allowed categories"""
    return {
        "categories": sorted(list(ALLOWED_CATEGORIES))
    }


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    logger.error(f"HTTP {exc.status_code}: {exc.detail}")
    return {
        "success": False,
        "error": exc.detail,
        "status_code": exc.status_code
    }


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return {
        "success": False,
        "error": "Internal server error",
        "status_code": 500
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
