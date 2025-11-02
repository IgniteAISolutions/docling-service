import os
import asyncio
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Header, HTTPException
from docling.document_converter import DocumentConverter, ConversionResult
from app.models import ExtractRequest, ExtractResponse, ProductFields
from app.batching import make_ranges
from app.utils import fetch_to_tmp

API_KEY = os.getenv("DOCLING_API_KEY", "")
ALLOWED_CALLERS = os.getenv("ALLOWLIST_CIDRS", "")  # optional, enforce at proxy or firewall

app = FastAPI(title="Docling Service", version="1.0.0")

def check_key(x_api_key: Optional[str]):
    if not API_KEY:
        return
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.post("/convert", response_model=ExtractResponse)
async def convert_body(
    req: ExtractRequest,
    x_api_key: Optional[str] = Header(default=None, convert_underscores=False),
):
    check_key(x_api_key)

    if not req.file_url:
        raise HTTPException(status_code=400, detail="file_url is required")

    tmp_path = await fetch_to_tmp(req.file_url)

    try:
        converter = DocumentConverter()

        # Single-pass convert if small or batch disabled
        if not req.page_end:
            result: ConversionResult = converter.convert(tmp_path)
            md = result.document.export_to_markdown() if req.return_markdown else None
            jj = result.document.export_to_dict() if req.return_json else None

            inferred = infer_product_fields(jj, md)
            return ExtractResponse(
                pages_processed=len(result.document.pages),
                markdown=md,
                doc_json=jj,
                inferred=inferred,
                notes=["single pass"],
            )

        # Batch path
        page_ranges = make_ranges(req.page_start, req.page_end, req.batch_size)
        markdown_parts = []
        merged_json = {"pages": []}
        total_pages = 0
        for a, b in page_ranges:
            # Per-batch timeout guard
            async def run_batch():
                sub = converter.convert({"path": tmp_path, "page_range": [a, b]})
                md = sub.document.export_to_markdown() if req.return_markdown else None
                jj = sub.document.export_to_dict() if req.return_json else None
                return md, jj, len(sub.document.pages)

            md, jj, count = await asyncio.wait_for(
                run_batch(), timeout=req.per_batch_timeout_sec
            )

            total_pages += count
            if md:
                markdown_parts.append(md)
            if jj and "pages" in jj:
                merged_json["pages"].extend(jj["pages"])

        md_all = "\n\n".join(markdown_parts) if markdown_parts else None
        inferred = infer_product_fields(merged_json if merged_json["pages"] else None, md_all)
        return ExtractResponse(
            pages_processed=total_pages,
            markdown=md_all,
            doc_json=merged_json if merged_json["pages"] else None,
            inferred=inferred,
            notes=[f"batched into {len(page_ranges)} ranges"],
        )
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass

def infer_product_fields(doc_json: Optional[dict], markdown: Optional[str]) -> Optional[ProductFields]:
    """
    Lightweight rule-based pass you can enhance later.
    - Prefer JSON blocks with headings like 'Features' or 'Technical Specifications'
    - Fallback to regex on Markdown
    """
    if not doc_json and not markdown:
        return None

    import re

    brand = None
    ptype = None
    sku = None
    desc = None
    features = []
    tech_specs = []

    text_blob = ""
    if markdown:
        text_blob += markdown + "\n"
    if doc_json:
        # Concatenate text from blocks
        for p in doc_json.get("pages", []):
            for b in p.get("blocks", []):
                if isinstance(b, dict):
                    txt = b.get("text") or ""
                    text_blob += txt + "\n"

    # Very simple heuristics you can refine
    sku_match = re.search(r"\b(SKU|Code|Product Code)\s*[:\-]\s*([A-Za-z0-9\-\._]+)", text_blob, re.IGNORECASE)
    if sku_match:
        sku = sku_match.group(2).strip()

    brand_match = re.search(r"\bBrand\s*[:\-]\s*([A-Za-z0-9 &\.\-]+)", text_blob, re.IGNORECASE)
    if brand_match:
        brand = brand_match.group(1).strip()

    # Product type by headings like "Product Type: X"
    ptype_match = re.search(r"\b(Product\s*Type)\s*[:\-]\s*([A-Za-z0-9 &\.\-]+)", text_blob, re.IGNORECASE)
    if ptype_match:
        ptype = ptype_match.group(2).strip()

    # Description - take first paragraph under "Description"
    desc_match = re.search(r"Description\s*[:\-]\s*(.+?)(?:\n\n|\Z)", text_blob, re.IGNORECASE | re.DOTALL)
    if desc_match:
        desc = desc_match.group(1).strip()

    # Features - bullet points under Features
    feats_section = re.search(r"Features\s*[:\-]?\s*(.+?)(?:\n[A-Z][^\n]{0,40}\n|\Z)", text_blob, re.IGNORECASE | re.DOTALL)
    if feats_section:
        for line in feats_section.group(1).splitlines():
            if line.strip().startswith(("-", "•", "*")):
                features.append(line.strip().lstrip("-•* ").strip())

    # Tech specs - similar
    specs_section = re.search(r"(Tech(nical)?\s*Spec(ifications)?|Specifications)\s*[:\-]?\s*(.+?)(?:\n[A-Z][^\n]{0,40}\n|\Z)",
                              text_blob, re.IGNORECASE | re.DOTALL)
    if specs_section:
        for line in specs_section.group(0).splitlines():
            if ":" in line and len(line) < 120:
                tech_specs.append(line.strip())

    return ProductFields(
        brand_name=brand,
        product_type=ptype,
        sku_code=sku,
        description=desc,
        features=features or None,
        tech_specifications=tech_specs or None,
    )
