"""
URL Scraper Service
Scrapes product data from website URLs
"""
import logging
import re
from typing import List, Dict, Any
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup

from ..config import URL_SCRAPE_TIMEOUT, URL_USER_AGENT

logger = logging.getLogger(__name__)


async def scrape(url: str, category: str) -> List[Dict[str, Any]]:
    """
    Scrape product data from URL
    Args:
        url: URL to scrape
        category: Product category
    Returns:
        List of product dictionaries
    Raises:
        ValueError: If scraping fails
    """
    # Validate URL
    if not is_valid_url(url):
        raise ValueError(f"Invalid URL: {url}")

    logger.info(f"Scraping URL: {url}")

    try:
        # Fetch page
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers={"User-Agent": URL_USER_AGENT},
                timeout=URL_SCRAPE_TIMEOUT,
                follow_redirects=True
            )

            response.raise_for_status()
            html = response.text

        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')

        # Extract product data
        product = extract_product_from_html(soup, url, category)

        if not product.get("name"):
            raise ValueError("Could not extract product name from page")

        logger.info(f"Successfully scraped product: {product.get('name')}")

        return [product]

    except httpx.HTTPError as e:
        logger.error(f"HTTP error scraping {url}: {e}")
        raise ValueError(f"Failed to fetch URL: {e}")

    except Exception as e:
        logger.error(f"Error scraping {url}: {e}")
        raise ValueError(f"Scraping failed: {e}")


def is_valid_url(url: str) -> bool:
    """
    Validate URL format
    Args:
        url: URL to validate
    Returns:
        True if URL is valid
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False
        
@app.post("/api/scrape-url", response_model=ProcessingResponse)
async def scrape_url_endpoint(request: ScrapeURLRequest):
    """
    Scrape product data from URL
    """
    try:
        from app.services import url_scraper
        
        # Scrape URL
        products = await url_scraper.scrape(request.url, request.category)
        
        # Generate brand voice
        from app.services import brand_voice
        enhanced = await brand_voice.generate(products, request.category)
        
        return ProcessingResponse(
            success=True,
            products=enhanced,
            message=f"Scraped {len(enhanced)} product(s) from URL"
        )
    except Exception as e:
        logger.error(f"URL scraping failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def extract_product_from_html(soup: BeautifulSoup, url: str, category: str) -> Dict[str, Any]:
    """
    Extract product data from HTML soup
    Args:
        soup: BeautifulSoup object
        url: Source URL
        category: Product category
    Returns:
        Product dictionary
    """
    product = {
        "name": extract_product_name_from_html(soup),
        "category": category,
        "sku": extract_sku_from_html(soup),
        "barcode": extract_barcode_from_html(soup),
        "brand": extract_brand_from_html(soup),
        "features": extract_features_from_html(soup),
        "specifications": extract_specifications_from_html(soup),
        "_source_url": url
    }

    return product


def extract_product_name_from_html(soup: BeautifulSoup) -> str:
    """Extract product name from HTML"""

    # Try Open Graph meta tag
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        return og_title['content'].strip()

    # Try meta title
    title_tag = soup.find('title')
    if title_tag and title_tag.string:
        # Clean up title (remove site name, etc.)
        title = title_tag.string.strip()
        # Remove common separators and site names
        title = re.split(r'\s*[|\-–—]\s*', title)[0]
        return title.strip()

    # Try h1 tag
    h1 = soup.find('h1')
    if h1:
        return h1.get_text().strip()

    # Try product name patterns
    name_selectors = [
        {'class': re.compile(r'product[_-]?name', re.I)},
        {'class': re.compile(r'product[_-]?title', re.I)},
        {'itemprop': 'name'},
    ]

    for selector in name_selectors:
        element = soup.find(attrs=selector)
        if element:
            return element.get_text().strip()

    return ""


def extract_sku_from_html(soup: BeautifulSoup) -> str:
    """Extract SKU from HTML"""

    # Try meta tags
    sku_meta = soup.find('meta', attrs={'itemprop': 'sku'})
    if sku_meta and sku_meta.get('content'):
        return sku_meta['content'].strip()

    # Try text patterns
    patterns = [
        r'SKU:\s*([A-Z0-9-]+)',
        r'Product Code:\s*([A-Z0-9-]+)',
        r'Item Code:\s*([A-Z0-9-]+)',
    ]

    text = soup.get_text()
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Try class/id patterns
    sku_selectors = [
        {'class': re.compile(r'sku', re.I)},
        {'id': re.compile(r'sku', re.I)},
    ]

    for selector in sku_selectors:
        element = soup.find(attrs=selector)
        if element:
            text = element.get_text().strip()
            # Extract alphanumeric code
            match = re.search(r'([A-Z0-9-]+)', text)
            if match:
                return match.group(1)

    return ""


def extract_barcode_from_html(soup: BeautifulSoup) -> str:
    """Extract barcode/EAN from HTML"""

    # Try meta tags
    gtin_meta = soup.find('meta', attrs={'itemprop': 'gtin13'})
    if gtin_meta and gtin_meta.get('content'):
        return gtin_meta['content'].strip()

    # Try text patterns
    patterns = [
        r'EAN:\s*(\d{13})',
        r'Barcode:\s*(\d{8,14})',
        r'UPC:\s*(\d{12})',
        r'GTIN:\s*(\d{8,14})',
    ]

    text = soup.get_text()
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return ""


def extract_brand_from_html(soup: BeautifulSoup) -> str:
    """Extract brand from HTML"""

    # Try meta tags
    brand_meta = soup.find('meta', attrs={'itemprop': 'brand'})
    if brand_meta and brand_meta.get('content'):
        return brand_meta['content'].strip()

    og_brand = soup.find('meta', property='og:brand')
    if og_brand and og_brand.get('content'):
        return og_brand['content'].strip()

    # Try class/id patterns
    brand_selectors = [
        {'class': re.compile(r'brand', re.I)},
        {'itemprop': 'brand'},
    ]

    for selector in brand_selectors:
        element = soup.find(attrs=selector)
        if element:
            # Check for nested name tag
            name_tag = element.find(attrs={'itemprop': 'name'})
            if name_tag:
                return name_tag.get_text().strip()
            return element.get_text().strip()

    return ""


def extract_features_from_html(soup: BeautifulSoup) -> List[str]:
    """Extract features from HTML"""
    features = []

    # Look for feature lists
    feature_selectors = [
        {'class': re.compile(r'features?', re.I)},
        {'id': re.compile(r'features?', re.I)},
    ]

    for selector in feature_selectors:
        container = soup.find(attrs=selector)
        if container:
            # Find list items
            items = container.find_all(['li', 'p'])
            for item in items:
                text = item.get_text().strip()
                if text and len(text) > 5:
                    features.append(text)

    # Look for bullet points with feature indicators
    all_li = soup.find_all('li')
    for li in all_li:
        text = li.get_text().strip()
        # Check if it looks like a feature
        if any(word in text.lower() for word in ['feature', 'include', 'with']):
            if text not in features and len(text) > 5:
                features.append(text)

    # Deduplicate and limit
    return features[:10]


def extract_specifications_from_html(soup: BeautifulSoup) -> Dict[str, Any]:
    """Extract specifications from HTML"""
    specs = {}

    # Look for specification tables
    spec_tables = soup.find_all('table', attrs={'class': re.compile(r'spec', re.I)})

    for table in spec_tables:
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all(['th', 'td'])
            if len(cells) >= 2:
                key = cells[0].get_text().strip().lower()
                value = cells[1].get_text().strip()

                # Map to standard spec keys
                if 'material' in key:
                    specs['material'] = value
                elif 'dimension' in key or 'size' in key:
                    specs['dimensions'] = value
                elif 'weight' in key:
                    specs['weight'] = value
                elif 'capacity' in key or 'volume' in key:
                    specs['capacity'] = value
                elif 'power' in key or 'watt' in key:
                    specs['powerW'] = value
                elif 'origin' in key or 'made in' in key:
                    specs['origin'] = value
                elif 'guarantee' in key or 'warranty' in key:
                    specs['guarantee'] = value
                elif 'care' in key or 'cleaning' in key:
                    specs['care'] = value

    # Look for specification lists
    spec_selectors = [
        {'class': re.compile(r'spec', re.I)},
        {'id': re.compile(r'spec', re.I)},
    ]

    for selector in spec_selectors:
        container = soup.find(attrs=selector)
        if container:
            # Try to find key-value pairs
            dt_dd = container.find_all(['dt', 'dd'])
            for i in range(0, len(dt_dd) - 1, 2):
                if dt_dd[i].name == 'dt' and i + 1 < len(dt_dd):
                    key = dt_dd[i].get_text().strip().lower()
                    value = dt_dd[i + 1].get_text().strip()

                    if 'material' in key:
                        specs['material'] = value
                    elif 'dimension' in key or 'size' in key:
                        specs['dimensions'] = value
                    elif 'weight' in key:
                        specs['weight'] = value

    return specs
