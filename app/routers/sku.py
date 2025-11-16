"""
SKU Search Router
Search for products by SKU or barcode on Harts of Stur website
"""
import logging
import time
import re
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
import requests
from bs4 import BeautifulSoup

from ..models import SKUSearchRequest, SKUSearchResponse, Product
from ..utils import categorize_product, generate_product_id
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["SKU Search"])


def is_barcode(sku: str) -> bool:
    """Check if SKU looks like a barcode (8-14 digits)"""
    clean = re.sub(r'[^\d]', '', sku)
    return len(clean) >= 8 and len(clean) <= 14 and clean.isdigit()


async def search_harts_website(sku: str) -> Optional[Dict[str, Any]]:
    """
    Search Harts of Stur website for product by SKU
    """
    try:
        # Try search URL first
        search_url = f"https://www.hartsofstur.com/search?q={sku}"
        logger.info(f"Searching: {search_url}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(search_url, headers=headers, timeout=10)

        if response.status_code == 200:
            html = response.text

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # Extract title
            title_tag = soup.find('title')
            title = title_tag.get_text() if title_tag else ""

            # Extract meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            description = meta_desc.get('content', '') if meta_desc else ""

            # Check if we found actual product info
            if title and ('product' in title.lower() or 'harts' in title.lower()):
                return {
                    "name": title.replace(' | Harts of Stur', '').strip(),
                    "description": description,
                    "sku": sku,
                    "source_url": search_url,
                    "found": True
                }

        # Try direct product URL
        direct_url = f"https://www.hartsofstur.com/products/{sku.lower()}"
        logger.info(f"Trying direct URL: {direct_url}")

        response = requests.get(direct_url, headers=headers, timeout=10)

        if response.status_code == 200:
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')

            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text()

                meta_desc = soup.find('meta', attrs={'name': 'description'})
                description = meta_desc.get('content', '') if meta_desc else ""

                return {
                    "name": title.replace(' | Harts of Stur', '').strip(),
                    "description": description,
                    "sku": sku,
                    "source_url": direct_url,
                    "found": True
                }

    except Exception as e:
        logger.warning(f"Web search failed: {e}")

    return None


@router.post("/search-product-sku", response_model=SKUSearchResponse)
async def search_product_sku(request: SKUSearchRequest):
    """
    Search for product by SKU or barcode

    Searches Harts of Stur website and external sources.
    If no results found, returns empty array (not a fallback product).

    Barcode detection: If SKU is 8-14 digits, treats as EAN/GTIN barcode.
    """
    sku = request.sku.strip()

    if not sku:
        raise HTTPException(status_code=400, detail="SKU is required")

    logger.info(f"Searching for SKU: {sku}")

    # Check if it's a barcode
    if is_barcode(sku):
        logger.info(f"Detected barcode format: {sku}")

    try:
        # Search Harts website
        result = await search_harts_website(sku)

        if result and result.get("found"):
            # Build product from search result
            category = categorize_product(f"{result.get('name', '')} {result.get('description', '')}")

            # Extract brand from name/description
            combined_text = f"{result.get('name', '')} {result.get('description', '')}"
            brand = ""
            brand_keywords = ['ZWILLING', 'LE CREUSET', 'SAGE', 'DUALIT', 'KITCHENAID']
            for keyword in brand_keywords:
                if keyword.lower() in combined_text.lower():
                    brand = keyword
                    break

            product_data = {
                "name": result.get("name", "Product"),
                "brand": brand or "Unknown",
                "category": category,
                "sku": sku,
                "barcode": sku if is_barcode(sku) else "",
                "description": result.get("description", ""),
                "source_url": result.get("source_url"),
                "extraction_method": "sku-search",
                "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "confidence": 0.8
            }

            product = Product(**product_data)

            logger.info(f"Found product: {product.name}")

            return SKUSearchResponse(
                success=True,
                products=[product]
            )

        # No results found
        logger.warning(f"No product found for SKU: {sku}")

        return SKUSearchResponse(
            success=False,
            products=[]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SKU search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"SKU search failed: {str(e)}")
