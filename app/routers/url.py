"""
URL Scraper Router
Scrape product details from web URLs
"""
import logging
import time
import re
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
import requests
from bs4 import BeautifulSoup

from ..models import URLScrapeRequest, URLScrapeResponse, Product
from ..utils import categorize_product, extract_specifications, generate_product_id
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["URL Scraping"])


async def scrape_product_url(url: str) -> Dict[str, Any]:
    """
    Scrape product information from URL
    """
    try:
        logger.info(f"Scraping URL: {url}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        html = response.text
        soup = BeautifulSoup(html, 'html.parser')

        # Extract title
        title = ""
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
            # Remove common suffixes
            title = re.sub(r'\s*[|•-]\s*(Harts of Stur|Buy Online).*$', '', title, flags=re.IGNORECASE)

        # Extract meta description
        description = ""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            description = meta_desc.get('content', '').strip()

        # Extract SKU from URL or page
        sku = ""

        # Try to extract from URL
        url_sku_match = re.search(r'/products?/([a-zA-Z0-9\-_]+)', url)
        if url_sku_match:
            sku = url_sku_match.group(1)

        # Try to extract from page content
        if not sku:
            sku_patterns = [
                r'(?:SKU|Item|Code)[:\s]*([A-Z0-9\-_.]+)',
                r'Product Code[:\s]*([A-Z0-9\-_.]+)'
            ]
            for pattern in sku_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    sku = match.group(1)
                    break

        # Extract brand
        brand = ""
        brand_keywords = ['ZWILLING', 'LE CREUSET', 'SAGE', 'DUALIT', 'KITCHENAID', 'KENWOOD']
        combined_text = f"{title} {description}".upper()

        for keyword in brand_keywords:
            if keyword in combined_text:
                brand = keyword
                break

        # Extract specifications from page content
        specs = extract_specifications(f"{title} {description}")

        # Categorize product
        category = categorize_product(f"{title} {description}")

        return {
            "name": title or "Product from URL",
            "brand": brand,
            "category": category,
            "sku": sku,
            "description": description,
            "specifications": specs,
            "source_url": url,
            "found": True
        }

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Request timed out")
    except requests.exceptions.RequestException as e:
        logger.error(f"Request failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {str(e)}")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")


@router.post("/scrape-product-url", response_model=URLScrapeResponse)
async def scrape_url(request: URLScrapeRequest):
    """
    Scrape product details from a web URL

    Primarily designed for Harts of Stur product pages but works with
    most standard e-commerce product pages.

    Extracts:
    - Product name (from title)
    - Brand (pattern matching)
    - Category (auto-classified)
    - SKU (from URL or page content)
    - Description (meta description)
    - Specifications (parsed from content)
    """
    url = request.url.strip()

    if not url:
        raise HTTPException(status_code=400, detail="URL is required")

    # Validate URL format
    if not re.match(r'^https?://', url, re.IGNORECASE):
        raise HTTPException(status_code=400, detail="URL must start with http:// or https://")

    logger.info(f"Scraping product URL: {url}")

    try:
        # Scrape the URL
        result = await scrape_product_url(url)

        if not result.get("found"):
            return URLScrapeResponse(
                success=False,
                products=[]
            )

        # Build product
        product_data = {
            "name": result.get("name", "Product"),
            "brand": result.get("brand", "Unknown"),
            "category": result.get("category", "General"),
            "sku": result.get("sku", ""),
            "barcode": "",
            "description": result.get("description", ""),
            "specifications": result.get("specifications", {}),
            "source_url": url,
            "extraction_method": "url-scraping",
            "processed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "confidence": 0.75
        }

        product = Product(**product_data)

        logger.info(f"Scraped product: {product.name}")

        return URLScrapeResponse(
            success=True,
            products=[product]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"URL scraping error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to scrape URL: {str(e)}")
