"""
URL Scraper Service
Scrape product information from URLs
"""
import logging
from typing import List, Dict, Any
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Browser-like headers to avoid 403 errors
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-GB,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
}

async def scrape(url: str, category: str) -> List[Dict[str, Any]]:
    """
    Scrape product data from URL
    """
    try:
        logger.info(f"Scraping URL: {url}")
        
        async with httpx.AsyncClient(
            timeout=30.0,
            headers=HEADERS,
            follow_redirects=True
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract product info
        product = {
            "name": extract_product_name(soup, url),
            "brand": extract_brand(soup),
            "sku": extract_sku(soup),
            "category": category,
            "descriptions": {
                "shortDescription": extract_short_description(soup),
                "metaDescription": extract_meta_description(soup),
                "longDescription": extract_long_description(soup)
            },
            "features": extract_features(soup),
            "specifications": extract_specifications(soup)
        }
        
        return [product]
        
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            raise ValueError(f"Access denied by website. The site {url} is blocking automated requests. Please try copying the product information manually.")
        raise ValueError(f"Failed to fetch URL: {e.response.status_code}")
    except Exception as e:
        logger.error(f"URL scraping failed: {e}")
        raise ValueError(f"URL scraping failed: {str(e)}")

def extract_product_name(soup: BeautifulSoup, url: str) -> str:
    # Try common selectors
    selectors = ['h1.product-title', 'h1.product-name', 'h1[itemprop="name"]', 'h1']
    for selector in selectors:
        elem = soup.select_one(selector)
        if elem:
            return elem.get_text(strip=True)
    return url.split('/')[-1].replace('-', ' ').title()

def extract_brand(soup: BeautifulSoup) -> str:
    selectors = ['.product-brand', '[itemprop="brand"]', '.brand']
    for selector in selectors:
        elem = soup.select_one(selector)
        if elem:
            return elem.get_text(strip=True)
    return ""

def extract_sku(soup: BeautifulSoup) -> str:
    selectors = ['.product-sku', '[itemprop="sku"]', '.sku']
    for selector in selectors:
        elem = soup.select_one(selector)
        if elem:
            return elem.get_text(strip=True)
    return ""

def extract_short_description(soup: BeautifulSoup) -> str:
    selectors = ['.short-description', '.product-intro', '[itemprop="description"]']
    for selector in selectors:
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            return text[:200]
    return ""

def extract_meta_description(soup: BeautifulSoup) -> str:
    meta = soup.find('meta', attrs={'name': 'description'})
    if meta and meta.get('content'):
        return meta['content'][:160]
    return extract_short_description(soup)[:160]

def extract_long_description(soup: BeautifulSoup) -> str:
    selectors = ['.product-description', '.description', '[itemprop="description"]']
    for selector in selectors:
        elem = soup.select_one(selector)
        if elem:
            return elem.get_text(strip=True)
    return ""

def extract_features(soup: BeautifulSoup) -> List[str]:
    features = []
    feature_lists = soup.select('.features li, .product-features li')
    for li in feature_lists[:10]:
        text = li.get_text(strip=True)
        if text:
            features.append(text)
    return features

def extract_specifications(soup: BeautifulSoup) -> Dict[str, Any]:
    specs = {}
    spec_tables = soup.select('.specifications table, .specs table')
    for table in spec_tables:
        rows = table.select('tr')
        for row in rows:
            cells = row.select('td, th')
            if len(cells) == 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                specs[key] = value
    return specs


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
