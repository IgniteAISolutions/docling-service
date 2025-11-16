"""
Image OCR Product Extraction Router
Uses pytesseract-img repository for OCR processing
"""
import logging
import os
import re
import time
import tempfile
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File
from PIL import Image
import pytesseract

from ..models import ImageExtractionResponse, Product
from ..utils import categorize_product, extract_specifications, generate_product_id
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Image Extraction"])

# Configure Tesseract path if needed (already done in pytesseract-img repo)
# Tesseract should be installed via: apt-get install tesseract-ocr


async def perform_ocr_with_tesseract(image_bytes: bytes) -> tuple[str, float]:
    """
    Perform OCR using Tesseract (from pytesseract-img repo)
    Returns: (extracted_text, confidence)
    """
    temp_path = None
    
    try:
        # Save image to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(image_bytes)
            temp_path = tmp.name
        
        # Open image with PIL
        img = Image.open(temp_path)
        
        # Perform OCR with Tesseract
        ocr_text = pytesseract.image_to_string(img, lang='eng')
        
        # Get confidence data
        data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        confidences = [int(conf) for conf in data['conf'] if int(conf) > 0]
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        
        logger.info(f"Tesseract OCR: {len(ocr_text)} chars, {avg_confidence:.1f}% confidence")
        
        return ocr_text, avg_confidence / 100
    
    except Exception as e:
        logger.error(f"Tesseract OCR failed: {e}")
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
    
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except:
                pass


def extract_product_from_ocr(ocr_text: str, confidence: float) -> Dict[str, Any]:
    """
    Extract product information from OCR text using regex patterns
    Enhanced from pytesseract-img repository logic
    """
    # Extract SKU patterns
    sku = None
    sku_patterns = [
        r'(?:SKU|Item|Code|Model)[:\s]*([A-Z0-9\-_.]{3,20})',
        r'\b([A-Z]{2,}[0-9]{4,})\b',
        r'\b([0-9]{5,10})\b'
    ]
    for pattern in sku_patterns:
        match = re.search(pattern, ocr_text, re.IGNORECASE)
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
        match = re.search(pattern, ocr_text)
        if match:
            potential_barcode = match.group(1)
            # Validate it's actually a barcode (not a random number)
            if len(potential_barcode) in [8, 12, 13, 14]:
                barcode = potential_barcode
                break

    # Extract brand
    brand = ""
    brand_keywords = [
        'ZWILLING', 'LE CREUSET', 'SAGE', 'DUALIT', 'KITCHENAID', 
        'KENWOOD', 'NESPRESSO', 'GLOBAL', 'VICTORINOX', 'OXO'
    ]
    for keyword in brand_keywords:
        if keyword.lower() in ocr_text.lower():
            brand = keyword
            break

    # Extract specifications
    specs = extract_specifications(ocr_text)

    # Extract product name (first substantial line with actual words)
    lines = [line.strip() for line in ocr_text.split('\n') if line.strip()]
    name = "Product from Image"
    for line in lines:
        # Skip lines that are just numbers or codes
        if len(line) > 10 and not re.match(r'^[0-9\s\-_]+$', line):
            name = line[:100]  # Limit length
            break

    # Categorize
    category = categorize_product(ocr_text)
    
    # Determine confidence level
    confidence_level = "high" if confidence > 0.8 else "medium" if confidence > 0.6 else "low"

    return {
        "name": name,
        "brand": brand,
        "category": category,
        "sku": sku or "",
        "barcode": barcode or "",
        "specifications": specs,
        "ocrText": ocr_text[:500],  # Truncate for response
        "ocrConfidence": confidence_level,
        "extraction_method": "tesseract-ocr",
        "confidence": confidence
    }


@router.post("/extract-image-products", response_model=ImageExtractionResponse)
async def extract_image_products(file: UploadFile = File(...)):
    """
    Extract product information from image using Tesseract OCR
    
    Uses pytesseract-img repository for free, open-source OCR.
    No API costs, fully self-hosted.
    
    Accepts: JPG, PNG, BMP, WebP, TIFF images
    Returns: Structured product data with OCR-extracted information
    
    The endpoint will:
    1. Perform OCR using Tesseract
    2. Extract product details (SKU, barcode, brand, specs)
    3. Categorize the product
    4. Return structured data with confidence scores
    """
    logger.info(f"Processing image with Tesseract: {file.filename}")

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

        # Perform OCR with Tesseract
        ocr_text, confidence = await perform_ocr_with_tesseract(image_bytes)

        if not ocr_text or len(ocr_text.strip()) < 10:
            return ImageExtractionResponse(
                success=False,
                products=[],
                message="No readable text found in image"
            )

        logger.info(f"OCR extracted {len(ocr_text)} characters with {confidence*100:.1f}% confidence")

        # Extract product information
        product_data = extract_product_from_ocr(ocr_text, confidence)
        product_data["processed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # Convert to Product model
        product = Product(**product_data)

        logger.info(f"Extracted product: {product.name} (Brand: {product.brand})")

        return ImageExtractionResponse(
            success=True,
            products=[product],
            message=f"Successfully extracted product with {confidence*100:.0f}% OCR confidence"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image extraction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")
