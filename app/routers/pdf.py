"""
PDF Product Extraction Router
Universal PDF product extraction using AI-powered text analysis
"""
import time
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, File, UploadFile, HTTPException
from openai import OpenAI
import os

from ..models import PDFExtractionResponse, Product
from ..utils import categorize_product, generate_product_id
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["PDF Extraction"])

# Initialize OpenAI client
openai_client = None
if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def extract_pdf_text(pdf_bytes: bytes) -> str:
    """
    Extract text from PDF using multiple methods with fallback
    """
    logger.info(f"Starting PDF text extraction ({len(pdf_bytes)} bytes)")

    # Method 1: Try pypdf
    try:
        import pypdf
        from io import BytesIO

        logger.info("Attempting extraction with pypdf...")
        pdf_file = BytesIO(pdf_bytes)
        pdf_reader = pypdf.PdfReader(pdf_file)

        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n\n"

        if text and len(text.strip()) > 50:
            logger.info(f"pypdf succeeded: {len(text)} characters")
            return text.strip()
    except Exception as e:
        logger.warning(f"pypdf failed: {e}")

    # Method 2: Try pdfplumber
    try:
        import pdfplumber
        from io import BytesIO

        logger.info("Attempting extraction with pdfplumber...")
        pdf_file = BytesIO(pdf_bytes)

        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages[:10]:  # Limit to first 10 pages
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n\n"

        if text and len(text.strip()) > 50:
            logger.info(f"pdfplumber succeeded: {len(text)} characters")
            return text.strip()
    except Exception as e:
        logger.warning(f"pdfplumber failed: {e}")

    # Method 3: Binary text extraction (last resort)
    try:
        logger.info("Attempting binary text extraction...")
        text_data = pdf_bytes.decode('utf-8', errors='ignore')

        # Extract readable text using regex
        import re
        readable_chunks = re.findall(r'[\x20-\x7E\s]{15,}', text_data)

        if readable_chunks:
            extracted_text = ' '.join(readable_chunks)
            extracted_text = re.sub(r'\s+', ' ', extracted_text).strip()

            if len(extracted_text) > 100:
                logger.info(f"Binary extraction succeeded: {len(extracted_text)} characters")
                return extracted_text
    except Exception as e:
        logger.warning(f"Binary extraction failed: {e}")

    logger.error("All PDF text extraction methods failed")
    return ""


async def detect_products_in_text(text: str) -> List[Dict[str, Any]]:
    """
    Use OpenAI to detect products in extracted text
    """
    logger.info(f"Starting product detection ({len(text)} characters)")

    if not text or len(text) < 50:
        logger.warning("Insufficient text for product detection")
        return []

    if not openai_client:
        logger.error("OpenAI client not initialized - missing API key")
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        logger.info("Using OpenAI GPT-4o for product extraction...")

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert at extracting product information from ANY supplier catalog or document.

CRITICAL INSTRUCTIONS:
1. Extract ONLY products that are clearly mentioned in the provided text
2. Do NOT invent or assume products that aren't explicitly described
3. Work with ANY product type: cookware, electronics, food, cosmetics, etc.
4. Determine the actual brand from the text content
5. If no clear products are found, return an empty products array
6. Return ONLY valid JSON - no markdown formatting"""
                },
                {
                    "role": "user",
                    "content": f"""Extract ALL products mentioned in this text. Return ONLY valid JSON in this exact format:

{{
  "products": [
    {{
      "name": "Actual product name from text",
      "brand": "Actual brand from text or Unknown",
      "category": "Specific category from: Bakeware, Cookware, Electricals, Food & Drink, Health & Beauty, Home & Garden, or General",
      "description": "Product description from text",
      "sku": "Product code if mentioned or null",
      "price": "Price if mentioned or null",
      "features": ["feature1", "feature2"],
      "specifications": {{"key": "value"}},
      "colors": ["color1", "color2"],
      "materials": ["material1", "material2"]
    }}
  ]
}}

CATEGORY GUIDELINES:
- Bakeware, Cookware: pots, pans, skillets, ovens, baking equipment
- Electricals: appliances, electronics, machines with power ratings
- Food & Drink: edible products, beverages, ingredients
- Health & Beauty: cosmetics, skincare, wellness products
- Home & Garden: furniture, decor, gardening, cleaning
- General: if unclear or doesn't fit other categories

TEXT TO ANALYZE:
{text[:4000]}"""
                }
            ],
            max_tokens=2000,
            temperature=0.1
        )

        content = response.choices[0].message.content
        if not content:
            logger.warning("No response from OpenAI")
            return []

        logger.info("OpenAI response received")

        # Parse JSON response
        import json
        import re

        clean_content = content.strip()
        clean_content = re.sub(r'^```json\s*', '', clean_content)
        clean_content = re.sub(r'^```\s*', '', clean_content)
        clean_content = re.sub(r'\s*```$', '', clean_content)

        json_match = re.search(r'\{[\s\S]*\}', clean_content)
        json_str = json_match.group(0) if json_match else clean_content

        extracted_data = json.loads(json_str)

        if not extracted_data.get('products') or not isinstance(extracted_data['products'], list):
            logger.warning("Invalid response structure from OpenAI")
            return []

        logger.info(f"Detected {len(extracted_data['products'])} products")

        for idx, product in enumerate(extracted_data['products']):
            logger.info(f"Product {idx + 1}: {product.get('name')} (Brand: {product.get('brand', 'Unknown')})")

        return extracted_data['products']

    except Exception as e:
        logger.error(f"Product detection failed: {e}")
        return []


def format_products_for_frontend(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Format products for frontend consumption
    """
    formatted = []

    for idx, product in enumerate(products):
        formatted_product = {
            "SKU": product.get("sku") or f"AUTO-{int(time.time())}-{idx + 1}",
            "Barcode": "",
            "Description": product.get("name", f"Product {idx + 1}"),
            "WEIGHT KG": "",
            "SHORT DES": "",  # To be filled by brand voice generator
            "LONG DES": "",   # To be filled by brand voice generator

            # Raw extracted data
            "name": product.get("name", f"Product {idx + 1}"),
            "rawName": product.get("name", f"Product {idx + 1}"),
            "extracted_description": product.get("description", ""),
            "specifications": product.get("specifications", {}),
            "category": product.get("category", "General"),
            "brand": product.get("brand", "Unknown"),
            "features": product.get("features", []),
            "colors": product.get("colors", []),
            "materials": product.get("materials", []),
            "price": product.get("price"),

            # Metadata
            "_extraction_method": "universal-analysis",
            "_processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "confidence": 0.8
        }

        formatted.append(formatted_product)

    return formatted


@router.post("/extract-pdf-products", response_model=PDFExtractionResponse)
async def extract_pdf_products(file: UploadFile = File(...)):
    """
    Extract products from PDF using universal AI analysis

    Supports any product type and brand. Extracts:
    - Product names
    - Brands
    - Categories
    - Descriptions
    - Specifications
    - Features
    - Colors, materials
    - Prices

    Returns structured product data ready for brand voice generation.
    """
    start_time = time.time()
    logger.info(f"Processing PDF: {file.filename}")

    try:
        # Validate file type
        if not file.content_type == "application/pdf" and not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be a PDF")

        # Read PDF bytes
        pdf_bytes = await file.read()

        logger.info(f"PDF size: {len(pdf_bytes)} bytes")

        # Validate file size (50MB max)
        max_size = 50 * 1024 * 1024
        if len(pdf_bytes) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {len(pdf_bytes) / 1024 / 1024:.2f}MB. Maximum: 50MB"
            )

        # Extract text
        extracted_text = await extract_pdf_text(pdf_bytes)

        if not extracted_text or len(extracted_text) < 50:
            return PDFExtractionResponse(
                success=False,
                data={"products": []},
                extracted_count=0,
                source="Universal PDF Analysis",
                processing_summary={
                    "error": "No readable text found in PDF",
                    "pdf_size_bytes": len(pdf_bytes),
                    "file_name": file.filename
                }
            )

        # Detect products using AI
        products = await detect_products_in_text(extracted_text)

        if not products:
            return PDFExtractionResponse(
                success=False,
                data={"products": []},
                extracted_count=0,
                source="Universal PDF Analysis",
                processing_summary={
                    "error": "No products detected in extracted text",
                    "text_length": len(extracted_text),
                    "file_name": file.filename
                }
            )

        # Format for frontend
        formatted_products = format_products_for_frontend(products)

        processing_time = time.time() - start_time

        logger.info(f"Successfully extracted {len(formatted_products)} products in {processing_time:.2f}s")

        return PDFExtractionResponse(
            success=True,
            data={"products": formatted_products},
            extracted_count=len(formatted_products),
            source="Universal PDF Analysis",
            processing_summary={
                "detected_format": "UNIVERSAL",
                "extraction_method": "universal-ai-analysis",
                "file_name": file.filename,
                "file_size_bytes": len(pdf_bytes),
                "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "processing_time_seconds": round(processing_time, 2)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF extraction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")
