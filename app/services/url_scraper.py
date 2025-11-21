"""
URL Scraper Service with Cloudflare bypass
Comprehensive product data extraction for e-commerce
"""
import logging
import re
from typing import List, Dict, Any, Optional
import cloudscraper
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

def scrape_sync(url: str) -> str:
    """Synchronous scrape using cloudscraper"""
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    response = scraper.get(url, timeout=30)
    response.raise_for_status()
    return response.text

async def scrape(url: str, category: str) -> List[Dict[str, Any]]:
    """Scrape comprehensive product data from URL"""
    try:
        logger.info(f"Scraping URL: {url}")
        
        import asyncio
        html = await asyncio.to_thread(scrape_sync, url)
        
        soup = BeautifulSoup(html, 'html.parser')
        full_text = soup.get_text(separator=' ', strip=True)
        
        product = {
            # Core identifiers
            "name": extract_product_name(soup, url),
            "brand": extract_brand(soup, full_text),
            "sku": extract_sku(soup, full_text),
            "ean": extract_ean(soup, full_text),
            "barcode": extract_barcode(soup, full_text),
            "mpn": extract_mpn(soup, full_text),  # Manufacturer Part Number
            "category": category,
            
            # Descriptions for brand_voice.py
            "descriptions": {
                "shortDescription": extract_short_description(soup),
                "metaDescription": extract_meta_description(soup),
                "longDescription": extract_long_description(soup)
            },
            
            # Features and benefits
            "features": extract_features(soup),
            "benefits": extract_benefits(soup, full_text),
            
            # Technical specifications
            "specifications": extract_specifications(soup, full_text),
            
            # Variants and options
            "variants": extract_variants(soup),
            "colours": extract_colours(soup, full_text),
            "sizes": extract_sizes(soup, full_text),
            "styles": extract_styles(soup, full_text),
            
            # Pricing
            "pricing": extract_pricing(soup, full_text),
            
            # Additional e-commerce data
            "warranty": extract_warranty(soup, full_text),
            "delivery": extract_delivery(soup, full_text),
            "images": extract_images(soup),
            
            # Raw content for brand_voice.py context
            "rawExtractedContent": full_text[:5000],
            "_source_url": url
        }
        
        return [product]
        
    except Exception as e:
        logger.error(f"URL scraping failed: {e}")
        if "403" in str(e) or "Cloudflare" in str(e) or "blocked" in str(e).lower():
            raise ValueError("This website has strong bot protection. Please copy the product details and use the Free Text tab.")
        raise ValueError(f"URL scraping failed: {str(e)}")


# =============================================================================
# CORE IDENTIFIERS
# =============================================================================

def extract_product_name(soup: BeautifulSoup, url: str) -> str:
    """Extract product name/title"""
    # Priority order of selectors
    selectors = [
        'h1.product-title', 'h1.product_title', 'h1.product-name',
        'h1[itemprop="name"]', '.product-title h1', '.product_title',
        '[data-testid="product-title"]', '.pdp-title', 'h1'
    ]
    for selector in selectors:
        elem = soup.select_one(selector)
        if elem:
            name = elem.get_text(strip=True)
            if name and len(name) > 2:
                return name
    
    # Try og:title
    og = soup.find('meta', property='og:title')
    if og and og.get('content'):
        return og['content'].strip()
    
    # Fallback to URL
    return url.split('/')[-1].replace('-', ' ').replace('_', ' ').title()

def extract_brand(soup: BeautifulSoup, full_text: str) -> str:
    """Extract brand name"""
    # Schema.org
    brand_elem = soup.find(attrs={'itemprop': 'brand'})
    if brand_elem:
        name_elem = brand_elem.find(attrs={'itemprop': 'name'})
        if name_elem:
            return name_elem.get_text(strip=True)
        return brand_elem.get_text(strip=True)[:50]
    
    # Meta tags
    for prop in ['og:brand', 'product:brand']:
        meta = soup.find('meta', property=prop)
        if meta and meta.get('content'):
            return meta['content'].strip()
    
    # Common selectors
    selectors = ['.product-brand', '.brand', '.manufacturer', '[data-brand]']
    for selector in selectors:
        elem = soup.select_one(selector)
        if elem:
            return elem.get_text(strip=True)[:50]
    
    # Text pattern
    match = re.search(r'Brand:\s*([A-Za-z0-9\s&]+)', full_text)
    if match:
        return match.group(1).strip()[:50]
    
    return ""

def extract_sku(soup: BeautifulSoup, full_text: str) -> str:
    """Extract SKU code"""
    # Schema.org
    meta = soup.find('meta', attrs={'itemprop': 'sku'})
    if meta and meta.get('content'):
        return meta['content'].strip()
    
    elem = soup.find(attrs={'itemprop': 'sku'})
    if elem:
        return elem.get_text(strip=True)
    
    # Selectors
    selectors = ['.sku', '.product-sku', '[data-sku]', '.product_meta .sku']
    for selector in selectors:
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            # Clean up "SKU: ABC123" format
            match = re.search(r'([A-Z0-9][-A-Z0-9]+)', text)
            if match:
                return match.group(1)
    
    # Text patterns
    patterns = [
        r'SKU[:\s]+([A-Z0-9][-A-Z0-9]+)',
        r'Product Code[:\s]+([A-Z0-9][-A-Z0-9]+)',
        r'Item Code[:\s]+([A-Z0-9][-A-Z0-9]+)',
        r'Article[:\s]+([A-Z0-9][-A-Z0-9]+)',
        r'Model[:\s]+([A-Z0-9][-A-Z0-9]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return ""

def extract_ean(soup: BeautifulSoup, full_text: str) -> str:
    """Extract EAN/GTIN code"""
    # Schema.org GTIN
    for prop in ['gtin13', 'gtin', 'gtin14', 'gtin12']:
        meta = soup.find('meta', attrs={'itemprop': prop})
        if meta and meta.get('content'):
            return meta['content'].strip()
        elem = soup.find(attrs={'itemprop': prop})
        if elem:
            return elem.get_text(strip=True)
    
    # Text patterns
    patterns = [
        r'EAN[:\s]+(\d{13})',
        r'GTIN[:\s]+(\d{13,14})',
        r'EAN-13[:\s]+(\d{13})',
    ]
    for pattern in patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # Look for standalone 13-digit numbers (likely EAN)
    matches = re.findall(r'\b(\d{13})\b', full_text)
    for m in matches:
        if m.startswith(('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')):
            return m
    
    return ""

def extract_barcode(soup: BeautifulSoup, full_text: str) -> str:
    """Extract barcode (UPC/EAN)"""
    # Try EAN first
    ean = extract_ean(soup, full_text)
    if ean:
        return ean
    
    # UPC (12 digits)
    patterns = [
        r'UPC[:\s]+(\d{12})',
        r'Barcode[:\s]+(\d{8,14})',
    ]
    for pattern in patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return match.group(1)
    
    return ""

def extract_mpn(soup: BeautifulSoup, full_text: str) -> str:
    """Extract Manufacturer Part Number"""
    meta = soup.find('meta', attrs={'itemprop': 'mpn'})
    if meta and meta.get('content'):
        return meta['content'].strip()
    
    match = re.search(r'MPN[:\s]+([A-Z0-9][-A-Z0-9]+)', full_text, re.IGNORECASE)
    if match:
        return match.group(1)
    
    return ""


# =============================================================================
# DESCRIPTIONS
# =============================================================================

def extract_short_description(soup: BeautifulSoup) -> str:
    """Extract short/intro description"""
    selectors = [
        '.woocommerce-product-details__short-description',
        '.short-description', '.product-intro', '.product-summary',
        '[itemprop="description"]', '.product-short-desc'
    ]
    for selector in selectors:
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            if text:
                return text[:500]
    return ""

def extract_meta_description(soup: BeautifulSoup) -> str:
    """Extract meta description"""
    meta = soup.find('meta', attrs={'name': 'description'})
    if meta and meta.get('content'):
        return meta['content'][:160]
    
    og = soup.find('meta', property='og:description')
    if og and og.get('content'):
        return og['content'][:160]
    
    return extract_short_description(soup)[:160]

def extract_long_description(soup: BeautifulSoup) -> str:
    """Extract full product description"""
    selectors = [
        '.woocommerce-Tabs-panel--description', '#tab-description',
        '.product-description', '.description-content', '.product-details',
        '[data-testid="product-description"]', '.pdp-description'
    ]
    for selector in selectors:
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            if text and len(text) > 50:
                return text[:3000]
    
    # Try article or main content
    for tag in ['article', 'main']:
        elem = soup.find(tag)
        if elem:
            text = elem.get_text(strip=True)
            if len(text) > 200:
                return text[:3000]
    
    return ""


# =============================================================================
# FEATURES AND BENEFITS
# =============================================================================

def extract_features(soup: BeautifulSoup) -> List[str]:
    """Extract product features"""
    features = []
    
    # Common feature list selectors
    selectors = [
        '.features li', '.product-features li', '.feature-list li',
        '.woocommerce-product-details__short-description li',
        'ul.product-bullets li', '.key-features li', '.highlights li'
    ]
    
    for selector in selectors:
        items = soup.select(selector)
        for item in items[:15]:
            text = item.get_text(strip=True)
            if text and len(text) > 5 and text not in features:
                features.append(text)
    
    # Look for feature sections
    feature_headers = soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'features?|highlights?|key points?', re.I))
    for header in feature_headers:
        next_elem = header.find_next(['ul', 'ol'])
        if next_elem:
            for li in next_elem.find_all('li')[:10]:
                text = li.get_text(strip=True)
                if text and len(text) > 5 and text not in features:
                    features.append(text)
    
    return features[:15]

def extract_benefits(soup: BeautifulSoup, full_text: str) -> List[str]:
    """Extract product benefits"""
    benefits = []
    
    # Look for benefits sections
    benefit_headers = soup.find_all(['h2', 'h3', 'h4'], string=re.compile(r'benefits?|why choose|advantages?', re.I))
    for header in benefit_headers:
        next_elem = header.find_next(['ul', 'ol', 'p'])
        if next_elem:
            if next_elem.name in ['ul', 'ol']:
                for li in next_elem.find_all('li')[:10]:
                    text = li.get_text(strip=True)
                    if text and len(text) > 5:
                        benefits.append(text)
            else:
                text = next_elem.get_text(strip=True)
                if text:
                    benefits.append(text)
    
    return benefits[:10]


# =============================================================================
# SPECIFICATIONS
# =============================================================================

def extract_specifications(soup: BeautifulSoup, full_text: str) -> Dict[str, Any]:
    """Extract comprehensive technical specifications"""
    specs = {}
    
    # Specification tables
    table_selectors = [
        '.woocommerce-product-attributes', 'table.shop_attributes',
        '.specifications table', '.specs table', '.product-specs table',
        '[data-testid="specifications"]', '.tech-specs table'
    ]
    
    for selector in table_selectors:
        tables = soup.select(selector)
        for table in tables:
            rows = table.select('tr')
            for row in rows:
                cells = row.select('td, th')
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    if key and value:
                        specs[key] = value
    
    # Definition lists
    for dl in soup.select('dl.specifications, dl.product-specs'):
        dts = dl.find_all('dt')
        dds = dl.find_all('dd')
        for dt, dd in zip(dts, dds):
            key = dt.get_text(strip=True).lower()
            value = dd.get_text(strip=True)
            if key and value:
                specs[key] = value
    
    # Extract common specs from text
    spec_patterns = {
        'dimensions': r'Dimensions?[:\s]+([0-9]+\s*[xX×]\s*[0-9]+(?:\s*[xX×]\s*[0-9]+)?(?:\s*(?:mm|cm|m|in|inches))?)',
        'weight': r'Weight[:\s]+([0-9.]+\s*(?:kg|g|lb|lbs|oz))',
        'power': r'Power[:\s]+([0-9]+\s*[Ww])',
        'wattage': r'Wattage[:\s]+([0-9]+\s*[Ww])',
        'voltage': r'Voltage[:\s]+([0-9]+\s*[Vv])',
        'capacity': r'Capacity[:\s]+([0-9.]+\s*(?:L|ml|litres?|liters?|cups?))',
        'material': r'Material[:\s]+([A-Za-z\s,]+)',
    }
    
    for spec_key, pattern in spec_patterns.items():
        if spec_key not in specs:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                specs[spec_key] = match.group(1).strip()
    
    return specs


# =============================================================================
# VARIANTS AND OPTIONS
# =============================================================================

def extract_variants(soup: BeautifulSoup) -> List[Dict[str, str]]:
    """Extract product variants"""
    variants = []
    
    # Look for variant selectors
    selectors = soup.select('select.variation, select[name*="attribute"], .variant-selector select')
    for select in selectors:
        variant_name = select.get('name', '').replace('attribute_', '').replace('_', ' ')
        options = []
        for option in select.find_all('option'):
            value = option.get_text(strip=True)
            if value and value.lower() not in ['choose an option', 'select', '']:
                options.append(value)
        if options:
            variants.append({'name': variant_name, 'options': options})
    
    # Look for swatch options
    swatches = soup.select('.swatch-wrapper, .variant-swatch, [data-variant]')
    for swatch in swatches:
        value = swatch.get('data-value') or swatch.get('title') or swatch.get_text(strip=True)
        if value:
            variants.append({'type': 'swatch', 'value': value})
    
    return variants[:20]

def extract_colours(soup: BeautifulSoup, full_text: str) -> List[str]:
    """Extract available colours"""
    colours = []
    
    # Common colour words
    colour_words = [
        'black', 'white', 'silver', 'grey', 'gray', 'red', 'blue', 'green',
        'gold', 'rose gold', 'bronze', 'copper', 'cream', 'beige', 'brown',
        'navy', 'pink', 'purple', 'orange', 'yellow', 'stainless steel',
        'brushed steel', 'chrome', 'matte black', 'gloss white'
    ]
    
    # Look for colour selectors
    colour_selects = soup.select('select[name*="color"], select[name*="colour"], .colour-selector select')
    for select in colour_selects:
        for option in select.find_all('option'):
            text = option.get_text(strip=True).lower()
            if text and text not in ['choose', 'select', '']:
                colours.append(option.get_text(strip=True))
    
    # Check text for colour mentions
    if not colours:
        text_lower = full_text.lower()
        for colour in colour_words:
            if colour in text_lower:
                colours.append(colour.title())
    
    return list(set(colours))[:10]

def extract_sizes(soup: BeautifulSoup, full_text: str) -> List[str]:
    """Extract available sizes"""
    sizes = []
    
    # Size selectors
    size_selects = soup.select('select[name*="size"], .size-selector select')
    for select in size_selects:
        for option in select.find_all('option'):
            text = option.get_text(strip=True)
            if text and text.lower() not in ['choose', 'select', '']:
                sizes.append(text)
    
    # Text patterns
    size_pattern = r'Sizes?[:\s]+([A-Za-z0-9,\s]+(?:cm|mm|L|ml|inch)?)'
    match = re.search(size_pattern, full_text, re.IGNORECASE)
    if match:
        sizes.extend([s.strip() for s in match.group(1).split(',')])
    
    return list(set(sizes))[:10]

def extract_styles(soup: BeautifulSoup, full_text: str) -> List[str]:
    """Extract available styles"""
    styles = []
    
    style_selects = soup.select('select[name*="style"], .style-selector select')
    for select in style_selects:
        for option in select.find_all('option'):
            text = option.get_text(strip=True)
            if text and text.lower() not in ['choose', 'select', '']:
                styles.append(text)
    
    return styles[:10]


# =============================================================================
# PRICING
# =============================================================================

def extract_pricing(soup: BeautifulSoup, full_text: str) -> Dict[str, Any]:
    """Extract pricing information"""
    pricing = {}
    
    # Schema.org price
    price_elem = soup.find(attrs={'itemprop': 'price'})
    if price_elem:
        pricing['price'] = price_elem.get('content') or price_elem.get_text(strip=True)
    
    currency_elem = soup.find(attrs={'itemprop': 'priceCurrency'})
    if currency_elem:
        pricing['currency'] = currency_elem.get('content') or currency_elem.get_text(strip=True)
    
    # Common price selectors
    price_selectors = ['.price', '.product-price', '[data-price]', '.current-price', '.sale-price']
    for selector in price_selectors:
        elem = soup.select_one(selector)
        if elem and 'price' not in pricing:
            text = elem.get_text(strip=True)
            # Extract price with currency
            match = re.search(r'[£$€][\d,]+\.?\d*', text)
            if match:
                pricing['price'] = match.group(0)
    
    # RRP/Was price
    rrp_selectors = ['.was-price', '.rrp', '.original-price', '.regular-price']
    for selector in rrp_selectors:
        elem = soup.select_one(selector)
        if elem:
            text = elem.get_text(strip=True)
            match = re.search(r'[£$€][\d,]+\.?\d*', text)
            if match:
                pricing['rrp'] = match.group(0)
    
    return pricing


# =============================================================================
# ADDITIONAL E-COMMERCE DATA
# =============================================================================

def extract_warranty(soup: BeautifulSoup, full_text: str) -> str:
    """Extract warranty information"""
    # Look for warranty sections
    warranty_patterns = [
        r'(\d+\s*years?\s*(?:warranty|guarantee))',
        r'(warranty[:\s]+\d+\s*years?)',
        r'(guarantee[:\s]+\d+\s*years?)',
        r'(\d+\s*years?\s*manufacturer.s?\s*warranty)',
    ]
    
    for pattern in warranty_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    
    # Check for warranty in specs tables
    for elem in soup.select('td, th, dt, dd'):
        text = elem.get_text(strip=True).lower()
        if 'warranty' in text or 'guarantee' in text:
            return elem.get_text(strip=True)
    
    return ""

def extract_delivery(soup: BeautifulSoup, full_text: str) -> str:
    """Extract delivery information"""
    delivery_selectors = ['.delivery-info', '.shipping-info', '[data-delivery]']
    for selector in delivery_selectors:
        elem = soup.select_one(selector)
        if elem:
            return elem.get_text(strip=True)[:200]
    
    # Text patterns
    delivery_patterns = [
        r'(free delivery[^.]*)',
        r'(delivery[:\s]+[^.]+)',
        r'(ships? in[^.]+)',
    ]
    for pattern in delivery_patterns:
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            return match.group(1).strip()[:200]
    
    return ""

def extract_images(soup: BeautifulSoup) -> List[str]:
    """Extract product image URLs"""
    images = []
    
    # Product gallery images
    gallery_selectors = [
        '.product-gallery img', '.woocommerce-product-gallery img',
        '[data-product-image]', '.product-images img', '.pdp-image img'
    ]
    
    for selector in gallery_selectors:
        for img in soup.select(selector)[:10]:
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            if src and src not in images and not src.endswith('.svg'):
                images.append(src)
    
    # og:image
    og_img = soup.find('meta', property='og:image')
    if og_img and og_img.get('content'):
        images.insert(0, og_img['content'])
    
    return images[:10]
