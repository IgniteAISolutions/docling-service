# app/main.py - COMPLETE REPLACEMENT
# Copy this ENTIRE file to replace your current main.py
# Flow: React → Elestio → Supabase brand-voice → React

import os
import json
import asyncio
import httpx
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

        # Infer product fields from extracted data
        inferred = infer_product_fields(jj, md)

        # Build product object
        product = {
            "id": os.urandom(16).hex(),
            "name": (inferred.get("product_type") or inferred.get("brand_name") or "Extracted Product") if inferred else "Extracted Product",
            "brand": inferred.get("brand_name", "") if inferred else "",
            "sku": inferred.get("sku_code", "") if inferred else "",
            "category": category,
            "source": "docling",
            "specifications": {
                "product_type": inferred.get("product_type", "") if inferred else "",
                "pages_processed": pages_processed,
            },
            "features": inferred.get("features", []) if inferred else [],
            "descriptions": {
                "shortDescription": (inferred.get("description", "") or "")[:280] if inferred else "",
                "metaDescription": (inferred.get("description", "") or "")[:160] if inferred else "",
                "longDescription": md or (inferred.get("description", "") if inferred else ""),
            }
        }

        # Call Supabase brand-voice to enhance descriptions
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
            json={"products": products, "category": category}
        )
        
        if not response.is_success:
            raise Exception(f"Brand voice failed: {response.status_code}")
        
        result = response.json()
        if not result.get("success"):
            raise Exception(result.get("error", "Unknown error"))
        
        return result.get("products", products)


def infer_product_fields(doc_json: Optional[dict], markdown: Optional[str]) -> Optional[dict]:
    """Extract product fields from document"""
    if doc_json is None and not markdown:
        return None

    # Normalize JSON
    if isinstance(doc_json, dict):
        jj = doc_json
    elif isinstance(doc_json, str):
        try:
            jj = json.loads(doc_json)
        except Exception:
            jj = {}
    else:
        jj = {}

    pages = jj.get("pages", []) if isinstance(jj, dict) else []
    text_chunks: List[str] = []

    if isinstance(markdown, str) and markdown.strip():
        text_chunks.append(markdown)

    # Extract text from pages
    for p in pages:
        if isinstance(p, dict):
            blocks = p.get("blocks")
            if isinstance(blocks, list):
                for b in blocks:
                    if isinstance(b, dict):
                        t = b.get("text")
                        if isinstance(t, str):
                            text_chunks.append(t)
                    elif isinstance(b, str):
                        text_chunks.append(b)
        elif isinstance(p, str):
            text_chunks.append(p)

    all_text = " ".join(text_chunks)[:2000] if text_chunks else ""

    # Basic field extraction
    product_type = None
    brand_name = None
    sku_code = None
    description = all_text[:500] if all_text else None

    lines = all_text.split("\n")
    for line in lines[:50]:
        line_lower = line.lower()
        if any(kw in line_lower for kw in ["model", "product", "item"]):
            if not product_type and len(line) < 100:
                product_type = line.strip()
        if any(kw in line_lower for kw in ["brand", "manufacturer"]):
            if not brand_name and len(line) < 50:
                brand_name = line.strip()
        if any(kw in line_lower for kw in ["sku", "code", "ref"]):
            if not sku_code and len(line) < 50:
                sku_code = line.strip()

    return {
        "product_type": product_type,
        "brand_name": brand_name,
        "sku_code": sku_code,
        "description": description,
        "features": [],
    }
