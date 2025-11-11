# app/main.py - IMPROVED VERSION WITH VARIANT SKU EXTRACTION
# Better product extraction + Enhanced brand voice prompts + Full variant SKU codes
# Flow: React → Elestio → Supabase brand-voice → React

import os
import json
import asyncio
import httpx
import re
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from docling.document_converter import DocumentConverter, ConversionResult

from app.models import ExtractRequest, ExtractResponse, ProductFields
from app.batching import make_ranges
from app.utils import fetch_to_tmp

# Configuration
API_KEY = os.getenv("DOCLING_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://gxbcqiqwwidoteusipgn.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd4YmNxaXF3d2lkb3RldXNpcGduIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI5MDcxNzAsImV4cCI6MjA2ODQ4MzE3MH0.A2sqSV_8sAMQB9bcy0Oq5JTwuZ0nmniEn7EfGvbgZnk")

app = FastAPI(title="Docling Service", version="1.0.0")

# CORS middleware - allows React to call from browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def check_key(x_api_key: Optional[str]):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/convert")
async def convert_body(
    req: ExtractRequest,
    x_api_key_dash: Optional[str] = Header(default=None, alias="x-api-key"),
    x_api_key_under: Optional[str] = Header(default=None, alias="x_api_key", convert_underscores=False),
):
    """
    Complete PDF processing pipeline:
    1. Extract product data from PDF using Docling
    2. Call Supabase generate-brand-voice to enhance descriptions
    3. Return enhanced product(s) to React
    """
    x_api_key = x_api_key_dash or x_api_key_under
    check_key(x_api_key)

    if not req.file_url:
        raise HTTPException(status_code=400, detail="file_url is required")

    # Get category from request
    category = getattr(req, 'category', None) or "Electricals"

    tmp_path = await fetch_to_tmp(req.file_url)

    try:
        converter = DocumentConverter()

        # Convert PDF
        if not req.page_end:
            result: ConversionResult = converter.convert(tmp_path)
            md = result.document.export_to_markdown() if req.return_markdown else None
            jj = result.document.export_to_dict() if req.return_json else None
            pages_processed = len(result.document.pages)
        else:
            # Batched conversion
            page_ranges = make_ranges(req.page_start, req.page_end, req.batch_size)
            markdown_parts: List[str] = []
            merged_json: Dict[str, Any] = {"pages": []}
            total_pages = 0

            for a, b in page_ranges:
                async def run_batch():
                    sub = converter.convert({"path": tmp_path, "page_range": [a, b]})
                    md_b = sub.document.export_to_markdown() if req.return_markdown else None
                    jj_b = sub.document.export_to_dict() if req.return_json else None
                    return md_b, jj_b, len(sub.document.pages)

                md_b, jj_b, count = await asyncio.wait_for(
                    run_batch(), timeout=req.per_batch_timeout_sec
                )
                total_pages += count

                if md_b:
                    markdown_parts.append(md_b)
                if jj_b and isinstance(jj_b, dict) and "pages" in jj_b:
                    merged_json["pages"].extend(jj_b["pages"])

            md = "\n\n".join(markdown_parts) if markdown_parts else None
            jj = merged_json if merged_json.get("pages") else None
            pages_processed = total_pages

        # IMPROVED: Extract product fields with better logic
        inferred = infer_product_fields_improved(jj, md)

        # Build product object with extracted raw content
        product = {
            "id": os.urandom(16).hex(),
            "name": inferred.get("product_name") or "Extracted Product",
            "brand": inferred.get("brand_name", ""),
            "sku": inferred.get("sku_code", ""),
            "category": category,
            "source": "docling",
            "rawExtractedContent": md or inferred.get("description", ""),  # Pass full content to brand-voice
            "specifications": {
                "model": inferred.get("model_number", ""),
                "variants": inferred.get("variants", []),
                "prices": inferred.get("prices", {}),
                "dimensions": inferred.get("dimensions", ""),
                "weight": inferred.get("weight", ""),
                "power": inferred.get("power", ""),
                "pages_processed": pages_processed,
            },
            "features": inferred.get("features", []),
            "descriptions": {
                "shortDescription": inferred.get("summary", ""),
                "metaDescription": inferred.get("summary", "")[:160],
                "longDescription": md or inferred.get("description", ""),
            }
        }

        # Call Supabase brand-voice with improved product data
        try:
            enhanced_products = await call_brand_voice([product], category)
            return {
                "success": True,
                "products": enhanced_products,
                "pages_processed": pages_processed,
                "markdown": md,
                "inferred": inferred,
            }
        except Exception as e:
            print(f"[WARNING] Brand voice failed: {e}")
            # Return without brand voice if it fails
            return {
                "success": True,
                "products": [product],
                "pages_processed": pages_processed,
                "markdown": md,
                "inferred": inferred,
                "notes": ["brand_voice_unavailable"]
            }

    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass


async def call_brand_voice(products: List[dict], category: str) -> List[dict]:
    """Call Supabase generate-brand-voice edge function with enhanced context"""
    brand_voice_url = f"{SUPABASE_URL}/functions/v1/generate-brand-voice"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            brand_voice_url,
            headers={
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                "apikey": SUPABASE_ANON_KEY,
                "Content-Type": "application/json",
            },
            json={
                "products": products,
                "category": category,
                "extractionHints": {
                    "useRawContent": True,  # Tell brand-voice to use rawExtractedContent
                    "preserveProductName": True,  # Don't change the extracted product name
                    "preserveBrand": True,  # Don't change the extracted brand
                    "preserveSKU": True,  # Don't change the extracted SKU
                }
            }
        )
        
        if not response.is_success:
            raise Exception(f"Brand voice failed: {response.status_code}")
        
        result = response.json()
        if not result.get("success"):
            raise Exception(result.get("error", "Unknown error"))
        
        return result.get("products", products)


def infer_product_fields_improved(doc_json: Optional[dict], markdown: Optional[str]) -> Optional[dict]:
    """
    IMPROVED: Extract product fields with better logic
    - Identifies actual product names (not markdown headers)
    - Extracts brand from logos/headers
    - Finds all SKU codes and variants with full SKU codes
    - Extracts specs, prices, dimensions
    """
    if doc_json is None and not markdown:
        return None

    # Get full text
    all_text = ""
    if isinstance(markdown, str) and markdown.strip():
        all_text = markdown
    
    if not all_text:
        return {
            "product_name": None,
            "brand_name": None,
            "sku_code": None,
            "description": None,
            "features": [],
        }

    lines = all_text.split("\n")
    
    # Initialize extraction results
    product_name = None
    brand_name = None
    model_number = None
    sku_codes = []
    variants = []
    prices = {}
    features = []
    dimensions = None
    weight = None
    power = None
    summary = None

    # STEP 1: Extract Brand (usually in header or logo alt text)
    for i, line in enumerate(lines[:10]):
        # Skip empty lines and markdown syntax
        line_clean = line.strip().replace("#", "").strip()
        if not line_clean or len(line_clean) < 2:
            continue
        
        # Common brand patterns
        if re.match(r'^[A-Z][a-z]+$', line_clean) or re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', line_clean):
            if not brand_name and len(line_clean) < 30:
                brand_name = line_clean
                break

    # STEP 2: Extract Product Name (usually after brand, before "PRODUCT" or specs)
    for i, line in enumerate(lines[:30]):
        line_clean = line.strip().replace("#", "").strip()
        line_lower = line_clean.lower()
        
        # Skip obvious non-product-name lines
        if not line_clean or "product technical" in line_lower or "spec" in line_lower:
            continue
        if line_clean.startswith("•") or line_clean.startswith("-"):
            continue
        if re.match(r'^\d', line_clean):  # Starts with number
            continue
            
        # Product names often contain "the", trademark symbols, or descriptive words
        if any(indicator in line_lower for indicator in ["the ", "™", "®", "barista", "espresso", "machine", "coffee"]):
            if not product_name and 5 < len(line_clean) < 100:
                product_name = line_clean
                break

    # STEP 3: Extract Model Number (usually near product name or in SKU section)
    model_pattern = r'\b[A-Z]{2,}[0-9]{2,}\b'  # e.g., SES882
    for line in lines[:50]:
        matches = re.findall(model_pattern, line)
        if matches and not model_number:
            model_number = matches[0]
            break

    # STEP 4: Extract SKU Codes (usually in tables with patterns like SES882BSS4GUK1)
    sku_pattern = r'\b[A-Z]{2,}[0-9]{3,}[A-Z0-9]{5,}\b'  # e.g., SES882BSS4GUK1
    for line in lines:
        matches = re.findall(sku_pattern, line)
        for match in matches:
            if match not in sku_codes:
                sku_codes.append(match)

    # STEP 5: Extract Variants/Colors with FULL SKU codes (ENHANCED)
    # Look for table rows with pattern: | Color Name | Code | SKU | ... |
    for line in lines:
        # Match table format: | Brushed Stainless Steel | BSS | SES882BSS4GUK1 | ...
        table_match = re.search(r'\|\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\|\s*([A-Z]{3})\s*\|\s*([A-Z0-9]{10,})\s*\|', line)
        if table_match:
            variant_name = table_match.group(1).strip()
            variant_code = table_match.group(2).strip()
            variant_sku = table_match.group(3).strip()
            
            # Avoid duplicates
            if variant_name not in [v.get("name") for v in variants]:
                variants.append({
                    "name": variant_name,
                    "code": variant_code,
                    "sku": variant_sku  # Full SKU for this variant
                })
                print(f"[VARIANT] Extracted: {variant_name} ({variant_code}) - {variant_sku}")
        
        # Fallback: Also try non-table format for other PDFs
        # Pattern: "Brushed Stainless Steel    BSS    SES882BSS4GUK1"
        elif len(line) < 150:
            line_lower = line.lower()
            color_keywords = ["stainless steel", "black", "white", "brushed", "truffle", "nougat", "salt", "almond", "sea salt"]
            for color in color_keywords:
                if color in line_lower:
                    variant_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+([A-Z]{3})\s+([A-Z0-9]{10,})', line)
                    if variant_match:
                        variant_name = variant_match.group(1).strip()
                        variant_code = variant_match.group(2).strip()
                        variant_sku = variant_match.group(3).strip()
                        if variant_name not in [v.get("name") for v in variants]:
                            variants.append({
                                "name": variant_name,
                                "code": variant_code,
                                "sku": variant_sku
                            })
                            print(f"[VARIANT] Extracted: {variant_name} ({variant_code}) - {variant_sku}")
                    break

    # STEP 6: Extract Prices
    price_pattern = r'(GBP|EUR|USD|\$|£|€)\s*[£$€]?\s*(\d{1,5}(?:[.,]\d{2})?)'
    for line in lines[:50]:
        matches = re.findall(price_pattern, line)
        for currency, amount in matches:
            amount_clean = amount.replace(",", "")
            if currency not in prices:
                prices[currency] = amount_clean

    # STEP 7: Extract Dimensions
    dimension_pattern = r'(\d{2,4}\s*x\s*\d{2,4}\s*x\s*\d{2,4})\s*mm'
    for line in lines:
        match = re.search(dimension_pattern, line)
        if match and not dimensions:
            dimensions = match.group(1) + " mm"
            break

    # STEP 8: Extract Weight
    weight_pattern = r'(\d+\.?\d*)\s*kg'
    for line in lines:
        if "product weight" in line.lower():
            match = re.search(weight_pattern, line)
            if match:
                weight = match.group(0)
                break

    # STEP 9: Extract Power
    power_pattern = r'(\d{3,4})-?(\d{3,4})W'
    for line in lines:
        match = re.search(power_pattern, line)
        if match and not power:
            power = f"{match.group(1)}-{match.group(2)}W"
            break

    # STEP 10: Extract Features (lines starting with bullets or containing key feature words)
    feature_keywords = ["preset", "setting", "cup", "extraction", "grind", "milk", "filter", "cleaning"]
    for line in lines:
        line_clean = line.strip()
        if line_clean.startswith("•") or line_clean.startswith("-"):
            feature_text = line_clean.lstrip("•-").strip()
            if 10 < len(feature_text) < 200:
                features.append(feature_text)
        else:
            for keyword in feature_keywords:
                if keyword in line.lower() and 20 < len(line_clean) < 200:
                    if line_clean not in features:
                        features.append(line_clean)

    # STEP 11: Generate summary (first meaningful sentence)
    for line in lines[:50]:
        line_clean = line.strip().replace("#", "").strip()
        if 30 < len(line_clean) < 200 and not line_clean.startswith("•"):
            if not any(skip in line_clean.lower() for skip in ["product", "technical", "spec", "dimension"]):
                summary = line_clean
                break

    return {
        "product_name": product_name,
        "brand_name": brand_name,
        "model_number": model_number,
        "sku_code": sku_codes[0] if sku_codes else None,
        "all_skus": sku_codes,
        "variants": variants,
        "prices": prices,
        "dimensions": dimensions,
        "weight": weight,
        "power": power,
        "features": features[:10],  # Limit to top 10 features
        "summary": summary,
        "description": all_text[:1000],  # First 1000 chars for context
    }
