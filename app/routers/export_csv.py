"""
CSV Export Router
Export products to CSV with HTML sanitization
"""
import logging
import io
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import pandas as pd

from ..models import ExportCSVRequest
from ..utils import strip_brand_taglines, strip_provenance, sanitize_csv_content, normalize_paragraphs
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Export"])


def sanitize_description(text: str, prefer_p_tags: bool = True) -> str:
    """
    Sanitize HTML description for CSV export
    """
    if not text:
        return ""

    # Strip taglines and provenance
    text = strip_brand_taglines(text)
    text = strip_provenance(text)

    # Normalize HTML
    text = normalize_paragraphs(text, prefer_p_tags=prefer_p_tags)

    # Sanitize dangerous content
    text = sanitize_csv_content(text)

    return text


@router.post("/export-csv")
async def export_csv(request: ExportCSVRequest, http_request: Request):
    """
    Export products to CSV file

    Accepts products array with:
    - sku, barcode, name
    - descriptions (metaDescription, shortDescription, longDescription)
    - weightGrams, weightHuman
    - specifications (dynamic columns)

    Returns: CSV file with UTF-8 BOM for Excel compatibility

    Optional header: x-prefer-p-tags (true/false) to control HTML format
    """
    logger.info(f"Exporting {len(request.products)} products to CSV")

    try:
        if not request.products:
            raise HTTPException(status_code=400, detail="No products to export")

        # Check for prefer-p-tags header
        prefer_p_tags = http_request.headers.get("x-prefer-p-tags", "true").lower() == "true"

        # Collect all specification keys across products
        all_spec_keys = set()
        for product in request.products:
            specs = product.get("specifications", {})
            if isinstance(specs, dict):
                all_spec_keys.update(specs.keys())

        spec_keys = sorted(list(all_spec_keys))

        # Build rows
        rows = []

        for product in request.products:
            # Get descriptions
            descriptions = product.get("descriptions", {})

            short_desc = descriptions.get("shortDescription", "")
            long_desc = descriptions.get("longDescription", "")
            meta_desc = descriptions.get("metaDescription", "")

            # Sanitize descriptions
            short_desc = sanitize_description(short_desc, prefer_p_tags)
            long_desc = sanitize_description(long_desc, prefer_p_tags)

            # Build row
            row = {
                "sku": product.get("sku", ""),
                "barcode": product.get("barcode", ""),
                "name": product.get("name", ""),
                "shortDescription": short_desc,
                "longDescription": long_desc,
                "metaDescription": meta_desc,
                "weightGrams": product.get("weightGrams", ""),
                "weightHuman": product.get("weightHuman", ""),
            }

            # Add specification columns
            specs = product.get("specifications", {})
            for key in spec_keys:
                row[f"spec_{key}"] = specs.get(key, "") if isinstance(specs, dict) else ""

            rows.append(row)

        # Create DataFrame
        df = pd.DataFrame(rows)

        # Generate CSV with UTF-8 BOM
        output = io.StringIO()

        # Write BOM
        output.write('\ufeff')

        # Write CSV
        df.to_csv(output, index=False, encoding='utf-8')

        # Get CSV content
        csv_content = output.getvalue()

        logger.info(f"Generated CSV with {len(rows)} rows, {len(df.columns)} columns")

        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(csv_content.encode('utf-8')),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=harts_products_export.csv",
                "Access-Control-Expose-Headers": "Content-Disposition"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"CSV export error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"CSV export failed: {str(e)}")
