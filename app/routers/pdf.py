"""
PDF Product Extraction Router
Uses docling-PDF repository for document processing
"""
import logging
import time
import os
from typing import List, Dict, Any
from fastapi import APIRouter, File, UploadFile, HTTPException
from openai import OpenAI

# Import from docling-PDF submodule
from docling.document_converter import DocumentConverter, ConversionResult

from ..models import PDFExtractionResponse, Product
from ..utils import categorize_product, generate_product_id
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["PDF Extraction"])

# Initialize Docling converter (pre-warm for faster processing)
docling_converter = DocumentConverter()

# Initialize OpenAI client
openai_client = None
if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def extract_pdf_with_docling(pdf_path: str) -> tuple[str, int]:
    """
    Extract text from PDF using Docling
    Returns: (markdown_text, page_count)
    """
    logger.info(f"Processing PDF with Docling: {pdf_path}")
    
    try:
        # Convert PDF to markdown using Docling
        result: ConversionResult = docling_converter.convert(pdf_path)
        
        # Export to markdown
        markdown = result.document.export_to_markdown()
        page_count = len(result.document.pages)
        
        logger.info(f"Docling extracted {len(markdown)} characters from {page_count} pages")
        
        return markdown, page_count
    
    except Exception as e:
        logger.error(f"Docling extraction failed: {e}")
        raise


async def detect_products_with_ai(text: str) -> List[Dict[str, Any]]:
    """
    Use OpenAI to detect products in extracted text
    """
    logger.info(f"Starting AI product detection ({len(text)} characters)")

    if not text or len(text) < 50:
        logger.warning("Insufficient text for product detection")
        return []

    if not openai_client:
        logger.error("OpenAI client not initialized - missing API key")
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    try:
        logger.info("Using OpenAI GPT-4o-mini for product extraction...")

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Cost-effective model
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert at extracting product information from supplier catalogs.

CRITICAL INSTRUCTIONS:
1. Extract ONLY products clearly mentioned in the text
2. Do NOT invent products
3. Work with ANY product type: cookware, electronics, food, cosmetics, etc.
4. Determine the brand from text content
5. Return ONLY valid JSON - no markdown formatting"""
                },
                {
                    "role": "user",
                    "content": f"""Extract ALL products from this text. Return ONLY valid JSON:

{{
  "products": [
    {{
      "name": "Actual product name from text",
      "brand": "Actual brand from text or Unknown",
      "category": "One of: Bakeware, Cookware / Electricals / Food & Drink / Health & Beauty / Home & Garden / General",
      "description": "Product description",
      "sku": "Product code if mentioned or null",
      "price": "Price if mentioned or null",
      "features": ["feature1", "feature2"],
      "specifications": {{"key": "value"}},
      "colors": ["color1"],
      "materials": ["material1"]
    }}
  ]
}}

TEXT TO ANALYZE:
{text[:4000]}"""
                }
            ],
            max_tokens=2000,
            temperature=0.1
        )

        content = response.choices[0].message.content
        if not content:
            return []

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

        if not extracted_data.get('products'):
            return []

        logger.info(f"Detected {len(extracted_data['products'])} products")
        return extracted_data['products']

    except Exception as e:
        logger.error(f"AI product detection failed: {e}")
        return []


@router.post("/extract-pdf-products", response_model=PDFExtractionResponse)
async def extract_pdf_products(file: UploadFile = File(...)):
    """
    Extract products from PDF using Docling + AI
    
    Uses docling-PDF repository for accurate document conversion,
    then AI for intelligent product extraction.
    
    Supports any product type and brand.
    """
    start_time = time.time()
    logger.info(f"Processing PDF: {file.filename}")
    
    temp_path = None

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

        # Save to temporary file for Docling
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
            tmp.write(pdf_bytes)
            temp_path = tmp.name

        # Extract with Docling
        markdown_text, page_count = await extract_pdf_with_docling(temp_path)

        if not markdown_text or len(markdown_text) < 50:
            return PDFExtractionResponse(
                success=False,
                data={"products": []},
                extracted_count=0,
                source="Docling PDF Processing",
                processing_summary={
                    "error": "No readable text found in PDF",
                    "pages_processed": page_count,
                    "file_name": file.filename
                }
            )

        # Detect products using AI
        products = await detect_products_with_ai(markdown_text)

        if not products:
            return PDFExtractionResponse(
                success=False,
                data={"products": []},
                extracted_count=0,
                source="Docling PDF Processing",
                processing_summary={
                    "error": "No products detected",
                    "text_length": len(markdown_text),
                    "pages_processed": page_count,
                    "file_name": file.filename
                }
            )

        # Format products
        formatted_products = []
        for idx, product in enumerate(products):
            formatted_products.append({
                "SKU": product.get("sku") or f"AUTO-{int(time.time())}-{idx + 1}",
                "Barcode": "",
                "Description": product.get("name", f"Product {idx + 1}"),
                "WEIGHT KG": "",
                "SHORT DES": "",
                "LONG DES": "",
                "name": product.get("name", f"Product {idx + 1}"),
                "brand": product.get("brand", "Unknown"),
                "category": product.get("category", "General"),
                "specifications": product.get("specifications", {}),
                "features": product.get("features", []),
                "colors": product.get("colors", []),
                "materials": product.get("materials", []),
                "price": product.get("price"),
                "_extraction_method": "docling-ai-analysis",
                "_processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "confidence": 0.85
            })

        processing_time = time.time() - start_time

        logger.info(f"Extracted {len(formatted_products)} products in {processing_time:.2f}s")

        return PDFExtractionResponse(
            success=True,
            data={"products": formatted_products},
            extracted_count=len(formatted_products),
            source="Docling PDF Processing",
            processing_summary={
                "detected_format": "DOCLING",
                "extraction_method": "docling-ai-analysis",
                "file_name": file.filename,
                "pages_processed": page_count,
                "processing_time_seconds": round(processing_time, 2)
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PDF extraction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to process PDF: {str(e)}")
    
    finally:
        # Cleanup temp file
        if temp_path:
            try:
                os.unlink(temp_path)
            except:
                pass
