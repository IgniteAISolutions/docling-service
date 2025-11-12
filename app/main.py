# app/main.py - OPTIMIZED VERSION WITH OCR + IMPROVED EXTRACTION
# Real optimization: Pre-warm models at startup (not per-request)
# This saves 20-40 seconds of initialization time
# OCR stays enabled for compressed/image PDFs
# IMPROVED: Better brand, SKU, and variant extraction

import os
import json
import asyncio
import httpx
import re
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from docling.document_converter import DocumentConverter, ConversionResult, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions

from app.models import ExtractRequest, ExtractResponse, ProductFields
from app.batching import make_ranges
from app.utils import fetch_to_tmp

# Configuration
API_KEY = os.getenv("DOCLING_API_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://gxbcqiqwwidoteusipgn.supabase.co")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd4YmNxaXF3d2lkb3RldXNpcGduIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTI5MDcxNzAsImV4cCI6MjA2ODQ4MzE3MH0.A2sqSV_8sAMQB9bcy0Oq5JTwuZ0nmniEn7EfGvbgZnk")

app = FastAPI(title="Docling Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "https://harts-product-automation.igniteaisolutions.co.uk", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ⚡ CRITICAL OPTIMIZATION: Pre-initialize converter with models at startup
print("[STARTUP] 🔄 Pre-warming Docling converter with OCR models...")
print("[STARTUP] This takes 30-60 seconds but only happens ONCE at startup...")

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = True  # ✅ OCR ENABLED for compressed/image PDFs
pipeline_options.do_table_structure = True
pipeline_options.images_scale = 2.0
pipeline_options.generate_page_images = False
pipeline_options.generate_picture_images = False

ocr_options = EasyOcrOptions()
ocr_options.lang = ["en"]

CONVERTER = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options,
            ocr_options=ocr_options
        )
    }
)
print("[STARTUP] ✅ Docling converter ready with PRE-LOADED OCR models")
print("[STARTUP] 🚀 Subsequent requests will be 20-40 seconds FASTER!")


def check_key(x_api_key: Optional[str]):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


@app.get("/healthz")
async def healthz():
    return {
        "status": "ok", 
        "converter_ready": CONVERTER is not None,
        "ocr_enabled": True,
        "models_preloaded": True
    }


@app.post("/convert")
async def convert_body(
    req: ExtractRequest,
    x_api_key_dash: Optional[str] = Header(default=None, alias="x-api-key"),
    x_api_key_under: Optional[str] = Header(default=None, alias="x_api_key", convert_underscores=False),
):
    """Fast PDF processing with OCR and improved extraction"""
    import time
    start_time = time.time()
    
    x_api_key = x_api_key_dash or x_api_key_under
    check_key(x_api_key)

    if not req.file_url:
        raise HTTPException(status_code=400, detail="file_url is required")

    category = getattr(req, 'category', None) or "Electricals"

    print(f"[CONVERT] ⚡ Starting FAST conversion for: {req.file_url}")
    print(f"[CONVERT] Using PRE-LOADED converter (no model initialization delay)")
    
    tmp_path = await fetch_to_tmp(req.file_url)

    try:
        print("[CONVERT] Converting PDF with pre-loaded OCR...")
        convert_start = time.time()
        
        result: ConversionResult = CONVERTER.convert(tmp_path)
        
        convert_time = time.time() - convert_start
        print(f"[CONVERT] ✅ Conversion completed in {convert_time:.1f}s")
        
        md = result.document.export_to_markdown() if req.return_markdown else None
        jj = result.document.export_to_dict() if req.return_json else None
        pages_processed = len(result.document.pages)
        
        print(f"[CONVERT] ✅ Processed {pages_processed} pages")
        print(f"[CONVERT] 📊 Total time: {time.time() - start_time:.1f}s")

        # Extract product fields
        inferred = infer_product_fields_improved(jj, md)

        # Build product object
        product = {
            "id": os.urandom(16).hex(),
            "name": inferred.get("product_name") or "Extracted Product",
            "brand": inferred.get("brand_name", ""),
            "sku": inferred.get("sku_code", ""),
            "category": category,
            "source": "docling",
            "rawExtractedContent": md or inferred.get("description", ""),
            "specifications": {
                "model": inferred.get("model_number", ""),
                "variants": inferred.get("variants", []),
                "all_skus": inferred.get("all_skus", []),
                "prices": inferred.get("prices", {}),
                "dimensions": inferred.get("dimensions", ""),
                "weight": inferred.get("weight", ""),
                "power": inferred.get("power", ""),
                "pages_processed": pages_processed,
                "processing_time_seconds": round(time.time() - start_time, 1),
            },
            "features": inferred.get("features", []),
            "descriptions": {
                "shortDescription": inferred.get("summary", ""),
                "metaDescription": inferred.get("summary", "")[:160],
                "longDescription": md or inferred.get("description", ""),
            }
        }

        print(f"[CONVERT] 📦 Extracted: {inferred.get('product_name')} | Brand: {inferred.get('brand_name')} | SKUs: {len(inferred.get('all_skus', []))} | Variants: {len(inferred.get('variants', []))}")

        # Call brand-voice
        try:
            print("[CONVERT] 🎨 Calling brand voice...")
            enhanced_products = await call_brand_voice([product], category)
            print("[CONVERT] ✅ Brand voice complete")
            
            return {
                "success": True,
                "products": enhanced_products,
                "pages_processed": pages_processed,
                "processing_time_seconds": round(time.time() - start_time, 1),
                "markdown": md,
                "inferred": inferred,
            }
        except Exception as e:
            print(f"[WARNING] Brand voice failed: {e}")
            return {
                "success": True,
                "products": [product],
                "pages_processed": pages_processed,
                "processing_time_seconds": round(time.time() - start_time, 1),
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
    """Call Supabase generate-brand-voice edge function"""
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
                    "useRawContent": True,
                    "preserveProductName": True,
                    "preserveBrand": True,
                    "preserveSKU": True,
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
    """IMPROVED: Extract product fields with better logic for catalogues"""
    if doc_json is None and not markdown:
        return None

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

    # STEP 1: Extract Brand - IMPROVED
    print("[EXTRACT] Looking for brand...")
    for i, line in enumerate(lines[:20]):
        # First try raw line (with ## markers)
        line_raw = line.strip()
        
        # Check if it's a heading with brand name
        if line_raw.startswith("#"):
            # Remove all # symbols and whitespace
            line_clean = re.sub(r'^#+\s*', '', line_raw).strip()
            
            # Match ALL CAPS brand names like "ZWILLING" in headings
            if line_clean.isupper() and 3 < len(line_clean) < 30:
                # Check if it's JUST the brand (not a full product name)
                if ' ' not in line_clean or len(line_clean.split()) <= 2:
                    brand_name = line_clean
                    print(f"[EXTRACT] ✅ Found brand (heading): {brand_name}")
                    break
        
        # Also check non-heading lines
        line_clean = line_raw.replace("#", "").strip()
        if not line_clean or len(line_clean) < 2:
            continue
        
        # Match ALL CAPS brand names like "ZWILLING"
        if line_clean.isupper() and 3 < len(line_clean) < 30 and ' ' not in line_clean:
            brand_name = line_clean
            print(f"[EXTRACT] ✅ Found brand (all caps): {brand_name}")
            break
        
        # Match Title Case like "Sage Appliances"
        if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)?$', line_clean) and len(line_clean) < 30:
            if not brand_name:
                brand_name = line_clean
                print(f"[EXTRACT] ✅ Found brand (title case): {brand_name}")
                break

    # STEP 2: Extract Product Name
    print("[EXTRACT] Looking for product name...")
    for i, line in enumerate(lines[:80]):
        line_clean = line.strip().replace("#", "").strip()
        line_lower = line_clean.lower()
        
        if not line_clean or len(line_clean) < 5:
            continue
        
        if any(skip in line_lower for skip in ["technical", "specification", "dimension", "weight", "power", "sku", "ean"]):
            continue
        
        if line_clean.startswith(("•", "-", "*")) or re.match(r'^\d+\.', line_clean):
            continue
        
        product_indicators = [
            "grill", "machine", "maker", "pro", "plus", "espresso", 
            "coffee", "blender", "contact", "enfinigy", "barista",
            "toaster", "kettle", "mixer", "processor", "juicer"
        ]
        
        if any(indicator in line_lower for indicator in product_indicators):
            if 5 < len(line_clean) < 150:
                product_name = line_clean
                print(f"[EXTRACT] ✅ Found product name (indicator): {product_name}")
                break
        
        if line_clean.isupper() and 10 < len(line_clean) < 100:
            product_name = line_clean.title()
            print(f"[EXTRACT] ✅ Found product name (all caps): {product_name}")
            break
        
        if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)+$', line_clean) and 10 < len(line_clean) < 100:
            product_name = line_clean
            print(f"[EXTRACT] ✅ Found product name (title case): {product_name}")
            break

    if not product_name:
        print("[EXTRACT] ⚠️ No product name found, using fallback...")
        for line in lines[5:30]:
            line_clean = line.strip().replace("#", "").strip()
            if 15 < len(line_clean) < 150 and not line_clean.startswith(("•", "-", "*")):
                product_name = line_clean
                print(f"[EXTRACT] Using fallback: {product_name}")
                break

    # STEP 3: Extract Model Number
    model_pattern = r'\b[A-Z]{2,}[0-9]{2,}\b'
    for line in lines[:50]:
        matches = re.findall(model_pattern, line)
        if matches and not model_number:
            model_number = matches[0]
            print(f"[EXTRACT] Found model: {model_number}")
            break

    # STEP 4: Extract SKU Codes & Item Numbers - IMPROVED
    for line in lines:
        line_lower = line.lower()
        
        # Look for "Item number:" or "Item code:"
        if "item number" in line_lower or "item code" in line_lower:
            match = re.search(r'(?:item\s+(?:number|code))[\s:]+(\d+)', line, re.IGNORECASE)
            if match and match.group(1) not in sku_codes:
                sku_codes.append(match.group(1))
                print(f"[EXTRACT] Found item number: {match.group(1)}")
        
        # Look for EAN codes
        if "ean" in line_lower:
            match = re.search(r'ean[\s:]+(\d{13})', line, re.IGNORECASE)
            if match:
                ean_code = f"EAN-{match.group(1)}"
                if ean_code not in sku_codes:
                    sku_codes.append(ean_code)
                    print(f"[EXTRACT] Found EAN: {match.group(1)}")
        
        # Original pattern for formats like "SES882BSS4GUK1"
        matches = re.findall(r'\b[A-Z]{2,}[0-9]{3,}[A-Z0-9]{5,}\b', line)
        for match in matches:
            if match not in sku_codes:
                sku_codes.append(match)

    if sku_codes:
        print(f"[EXTRACT] Found {len(sku_codes)} SKU(s)")

    # STEP 5: Extract Variants/Colors - IMPROVED (skip fake variants)
    color_keywords = ["stainless", "steel", "black", "white", "truffle", "brushed", "chrome", "silver", "red", "blue"]
    for line in lines:
        line_lower = line.lower()
        
        # Skip if line doesn't contain color keywords
        if not any(color in line_lower for color in color_keywords):
            continue
        
        # Look for patterns like "Stainless Steel SST" or "Black Truffle BLK"
        variant_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+([A-Z]{3})\s+', line)
        if variant_match:
            variant_name = variant_match.group(1)
            variant_code = variant_match.group(2)
            if variant_name not in [v.get("name") for v in variants]:
                variant_sku = None
                for sku in sku_codes:
                    if variant_code in sku:
                        variant_sku = sku
                        break
                variants.append({
                    "name": variant_name,
                    "code": variant_code,
                    "sku": variant_sku
                })
    
    if variants:
        print(f"[EXTRACT] Found {len(variants)} variant(s)")

    # STEP 6: Extract Features
    for line in lines:
        line_clean = line.strip()
        if line_clean.startswith("•") or line_clean.startswith("-") or line_clean.startswith("*"):
            feature_text = line_clean.lstrip("•-*").strip()
            if 10 < len(feature_text) < 200:
                features.append(feature_text)

    # STEP 7: Generate summary
    for line in lines[:50]:
        line_clean = line.strip().replace("#", "").strip()
        if 30 < len(line_clean) < 200 and not line_clean.startswith(("•", "-", "*")):
            if not any(skip in line_clean.lower() for skip in ["product", "technical", "spec"]):
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
        "features": features[:10],
        "summary": summary,
        "description": all_text[:1000],
    }
