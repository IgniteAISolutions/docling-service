"""
Image OCR Product Extraction Router
Extracts product information from images using Google Cloud Vision API
"""
import base64
import logging
import os
import re
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File
from google.cloud import vision

from ..models import ImageExtractionRequest, ImageExtractionResponse, Product
from ..utils import categorize_product, extract_specifications, generate_product_id
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Image Extraction"])

# Initialize Google Vision client
vision_client = None
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("GOOGLE_VISION_API_KEY"):
    try:
        vision_client = vision.ImageAnnotatorClient()
    except Exception as e:
        logger.warning(f"Google Vision client initialization failed: {e}")


async def perform_ocr(image_bytes: bytes) -> str:
    """
    Perform OCR using Google Cloud Vision API
    """
    if not vision_client:
        raise HTTPException(
            status_code=500,
            detail="Google Vision API not configured. Please set GOOGLE_APPLICATION_CREDENTIALS"
        )

    try:
        image = vision.Image(content=image_bytes)
        response = vision_client.text_detection(image=image)

        if response.error.message:
            raise Exception(response.error.message)

        texts = response.text_annotations
        if texts:
            return texts[0].description
        return ""

    except Exception as e:
        logger.error(f"OCR failed: {e}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")


def extract_product_from_ocr(ocr_text: str, notes: str = "") -> Dict[str, Any]:
    """
    Extract product information from OCR text using regex patterns
    """
    combined_text = f"{ocr_text}\n{notes}"

    # Extract SKU patterns
    sku = None
    sku_patterns = [
        r'(?:SKU|Item|Code|Model)[:\s]*([A-Z0-9\-_.]{3,})',
        r'\b([A-Z]{2,}[0-9]{4,})\b',
        r'\b([0-9]{5,})\b'
    ]
    for pattern in sku_patterns:
        match = re.search(pattern, combined_text, re.IGNORECASE)
        if match:
            sku = match.group(1)
            break

    # Extract barcode (EAN/GTIN)
    barcode = None
    barcode_patterns = [
        r'(?:EAN|GTIN|Barcode)[:\s]*([0-9]{8,14})',
        r'\b([0-9]{12,14})\b'
    ]
    for pattern in barcode_patterns:
        match = re.search(pattern, combined_text)
        if match:
            barcode = match.group(1)
            break

    # Extract brand
    brand = ""
    brand_keywords = ['ZWILLING', 'LE CREUSET', 'SAGE', 'DUALIT', 'KITCHENAID', 'KENWOOD']
    for keyword in brand_keywords:
        if keyword.lower() in combined_text.lower():
            brand = keyword
            break

    # Extract specifications
    specs = extract_specifications(combined_text)

    # Extract product name (first substantial line)
    lines = [line.strip() for line in combined_text.split('\n') if line.strip()]
    name = next((line for line in lines if len(line) > 10), "Product from Image")

    # Categorize
    category = categorize_product(combined_text)

    return {
        "name": name[:100],  # Limit length
        "brand": brand,
        "category": category,
        "sku": sku,
        "barcode": barcode,
        "specifications": specs,
        "ocrText": ocr_text[:500],  # Truncate for response
        "ocrConfidence": "medium",
        "extractedAt": None  # Will be set by caller
    }


@router.post("/extract-image-products", response_model=ImageExtractionResponse)
async def extract_image_products(file: UploadFile = File(...)):
    """
    Extract product information from product image using OCR

    Accepts: JPG, PNG, BMP, WebP images
    Returns: Structured product data with OCR-extracted information

    The endpoint will:
    1. Perform OCR using Google Cloud Vision
    2. Extract product details (SKU, barcode, brand, specs)
    3. Categorize the product
    4. Return structured data
    """
    logger.info(f"Processing image: {file.filename}")

    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Read image bytes
        image_bytes = await file.read()

        logger.info(f"Image size: {len(image_bytes)} bytes")

        # Validate size (10MB max)
        max_size = 10 * 1024 * 1024
        if len(image_bytes) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Image too large: {len(image_bytes) / 1024 / 1024:.2f}MB. Maximum: 10MB"
            )

        # Perform OCR
        ocr_text = await perform_ocr(image_bytes)

        if not ocr_text or len(ocr_text.strip()) < 10:
            return ImageExtractionResponse(
                success=False,
                products=[]
            )

        logger.info(f"OCR extracted {len(ocr_text)} characters")

        # Extract product information
        import time
        product_data = extract_product_from_ocr(ocr_text)
        product_data["extractedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        product_data["processed_at"] = product_data["extractedAt"]
        product_data["extraction_method"] = "google-vision-ocr"
        product_data["confidence"] = 0.7

        # Convert to Product model
        product = Product(**product_data)

        logger.info(f"Extracted product: {product.name}")

        return ImageExtractionResponse(
            success=True,
            products=[product]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image extraction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")
