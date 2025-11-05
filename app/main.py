from typing import Any, Dict, List, Optional
import json
from app.models import ProductFields

def infer_product_fields(doc_json: Optional[dict], markdown: Optional[str]) -> Optional[ProductFields]:
    """
    Robust extractor that never throws.
    Accepts doc_json pages in any shape (dict, list, str).
    Falls back to markdown, then a crude summary slice.
    """
    if doc_json is None and not markdown:
        return None

    # Normalise doc_json into a dict if possible
    if isinstance(doc_json, dict):
        jj: Dict[str, Any] = doc_json
    elif isinstance(doc_json, str):
        try:
            jj = json.loads(doc_json)
        except Exception:
            jj = {}
    else:
        jj = {}

    pages = jj.get("pages", [])
    text_chunks: List[str] = []

    # Prefer markdown if present
    if isinstance(markdown, str) and markdown.strip():
        text_chunks.append(markdown)

    # Extract text from json pages
    for p in pages:
        # Case 1: page is dict
        if isinstance(p, dict):
            # blocks may hold text
            blocks = p.get("blocks")
            if isinstance(blocks, list):
                for b in blocks:
                    if isinstance(b, dict):
                        t = b.get("text")
                        if isinstance(t, str):
                            text_chunks.append(t)
                    elif isinstance(b, str):
                        text_chunks.append(b)

            # Some formats put text directly at page level
            page_text = p.get("text")
            if isinstance(page_text, str):
                text_chunks.append(page_text)

        # Case 2: page is list
        elif isinstance(p, list):
            for b in p:
                if isinstance(b, dict):
                    t = b.get("text")
                    if isinstance(t, str):
                        text_chunks.append(t)
                elif isinstance(b, str):
                    text_chunks.append(b)

        # Case 3: page is plain string
        elif isinstance(p, str):
            text_chunks.append(p)

    # Fallback: entire text blob field
    if not text_chunks and isinstance(jj.get("text"), str):
        text_chunks.append(jj["text"])

    blob = "\n".join(t for t in text_chunks if isinstance(t, str))

    # If upstream inference exists, respect it
    inferred_up = jj.get("inferred") if isinstance(jj.get("inferred"), dict) else None

    brand = inferred_up.get("brand_name") if inferred_up else None
    if not brand and inferred_up:
        brand = inferred_up.get("brand")

    sku = inferred_up.get("sku_code") if inferred_up else None
    if not sku and inferred_up:
        sku = inferred_up.get("sku") or inferred_up.get("SKU")

    product_type = inferred_up.get("product_type") if inferred_up else None

    description = inferred_up.get("description") if inferred_up else None
    if not description and inferred_up:
        description = inferred_up.get("summary")

    features = inferred_up.get("features") if inferred_up and isinstance(inferred_up.get("features"), list) else None
    tech_specs = inferred_up.get("tech_specifications") if inferred_up and isinstance(inferred_up.get("tech_specifications"), list) else None

    # If no description at all, fallback to first 500 chars of blob
    if not description and blob:
        description = blob.strip()[:500]

    return ProductFields(
        brand_name=brand or None,
        product_type=product_type or None,
        sku_code=sku or None,
        description=description or None,
        features=features or None,
        tech_specifications=tech_specs or None,
    )
