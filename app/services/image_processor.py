"""
Image Processor Service
OCR processing for product images using pytesseract
"""
import io
import logging
import re
from typing import List, Dict, Any
from PIL import Image
import pytesseract

from ..config import MAX_IMAGE_SIZE_MB, SUPPORTED_IMAGE_FORMATS

logger = logging.getLogger(__name__)


async def process(file_content: bytes, category: str, filename: str = "") -> List[Dict[str, Any]]:
    """
    Process image file and extract product data via OCR
    Args:
        file_content: Image file content as bytes
        category: Product category
        filename: Original filename
    Returns:
        List of product dictionaries
    Raises:
        ValueError: If image is invalid or too large
    """
    # Validate file size
    size_mb = len(file_content) / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        raise ValueError(f"Image too large: {size_mb:.2f}MB (max {MAX_IMAGE_SIZE_MB}MB)")

    # Validate file format
    if filename:
        ext = filename.lower().split('.')[-1]
        if f".{ext}" not in SUPPORTED_IMAGE_FORMATS:
            raise ValueError(f"Unsupported image format: {ext}")

    try:
        # Load image
        image = Image.open(io.BytesIO(file_content))

        # Perform OCR
        logger.info(f"Performing OCR on image: {filename or 'unknown'}")
        text = pytesseract.image_to_string(image)

        if not text or len(text.strip()) < 10:
            raise ValueError("No text extracted from image")

        logger.info(f"Extracted {len(text)} characters from image")

        # Parse text into product data
        products = parse_ocr_text(text, category)

        return products

    except Exception as e:
        logger.error(f"Failed to process image: {e}")
        raise ValueError(f"Image processing failed: {e}")


def parse_ocr_text(text: str, category: str) -> List[Dict[str, Any]]:
    """
    Parse OCR text into product data
    Args:
        text: Extracted OCR text
        category: Product category
    Returns:
        List of product dictionaries
    """
    # Clean up text
    text = text.strip()

    # Try to extract structured data
    product = {
        "name": extract_product_name(text),
        "category": category,
        "sku": extract_sku(text),
        "barcode": extract_barcode(text),
        "brand": extract_brand(text),
        "features": extract_features(text),
        "specifications": extract_specifications_from_text(text)
    }

    # Ensure we have at least a name
    if not product["name"]:
        # Use first line as name
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:
            product["name"] = lines[0][:100]  # Max 100 chars
        else:
            product["name"] = "Product from image"

    return [product]


def extract_product_name(text: str) -> str:
    """
    Extract product name from OCR text
    Args:
        text: OCR text
    Returns:
        Product name or empty string
    """
    # Look for common patterns
    patterns = [
        r'Product Name:\s*(.+?)(?:\n|$)',
        r'Name:\s*(.+?)(?:\n|$)',
        r'Title:\s*(.+?)(?:\n|$)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Fallback: use first substantial line
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    for line in lines:
        # Skip short lines and lines with only numbers
        if len(line) > 10 and not line.replace(' ', '').isdigit():
            return line[:100]  # Max 100 chars

    return ""


def extract_sku(text: str) -> str:
    """
    Extract SKU from OCR text
    Args:
        text: OCR text
    Returns:
        SKU or empty string
    """
    patterns = [
        r'SKU:\s*([A-Z0-9-]+)',
        r'Product Code:\s*([A-Z0-9-]+)',
        r'Item Code:\s*([A-Z0-9-]+)',
        r'Code:\s*([A-Z0-9-]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return ""


def extract_barcode(text: str) -> str:
    """
    Extract barcode/EAN from OCR text
    Args:
        text: OCR text
    Returns:
        Barcode or empty string
    """
    patterns = [
        r'EAN:\s*(\d{13})',
        r'Barcode:\s*(\d{8,14})',
        r'UPC:\s*(\d{12})',
        r'GTIN:\s*(\d{8,14})',
        r'\b(\d{13})\b',  # Standalone 13-digit number
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            barcode = match.group(1).strip()
            # Validate it's actually a barcode (8-14 digits)
            if 8 <= len(barcode) <= 14 and barcode.isdigit():
                return barcode

    return ""


def extract_brand(text: str) -> str:
    """
    Extract brand from OCR text
    Args:
        text: OCR text
    Returns:
        Brand or empty string
    """
    patterns = [
        r'Brand:\s*(.+?)(?:\n|$)',
        r'Manufacturer:\s*(.+?)(?:\n|$)',
        r'Make:\s*(.+?)(?:\n|$)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return ""


def extract_features(text: str) -> List[str]:
    """
    Extract features from OCR text
    Args:
        text: OCR text
    Returns:
        List of features
    """
    features = []

    # Look for bulleted lists
    bullet_patterns = [
        r'[•●○]\s*(.+?)(?:\n|$)',
        r'[-–—]\s*(.+?)(?:\n|$)',
        r'\*\s*(.+?)(?:\n|$)',
    ]

    for pattern in bullet_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            features.extend([m.strip() for m in matches if len(m.strip()) > 5])

    # Look for "Features:" section
    features_section = re.search(r'Features?:(.+?)(?:\n\n|$)', text, re.IGNORECASE | re.DOTALL)
    if features_section:
        section_text = features_section.group(1)
        # Extract lines
        lines = [line.strip() for line in section_text.split('\n') if line.strip()]
        features.extend([line for line in lines if len(line) > 5])

    # Deduplicate
    seen = set()
    unique_features = []
    for feature in features:
        if feature.lower() not in seen:
            seen.add(feature.lower())
            unique_features.append(feature)

    return unique_features[:10]  # Max 10 features


def extract_specifications_from_text(text: str) -> Dict[str, Any]:
    """
    Extract specifications from OCR text
    Args:
        text: OCR text
    Returns:
        Specifications dictionary
    """
    specs = {}

    # Common specification patterns
    spec_patterns = {
        'material': [
            r'Material:\s*(.+?)(?:\n|$)',
            r'Made from:\s*(.+?)(?:\n|$)',
        ],
        'dimensions': [
            r'Dimensions:\s*(.+?)(?:\n|$)',
            r'Size:\s*(.+?)(?:\n|$)',
            r'(\d+\.?\d*\s*x\s*\d+\.?\d*\s*x\s*\d+\.?\d*\s*cm)',
        ],
        'weight': [
            r'Weight:\s*(.+?)(?:\n|$)',
            r'(\d+\.?\d*\s*kg)',
            r'(\d+\.?\d*\s*g)',
        ],
        'capacity': [
            r'Capacity:\s*(.+?)(?:\n|$)',
            r'Volume:\s*(.+?)(?:\n|$)',
            r'(\d+\.?\d*\s*litre)',
            r'(\d+\.?\d*\s*ml)',
        ],
        'powerW': [
            r'Power:\s*(\d+)\s*W',
            r'Wattage:\s*(\d+)',
            r'(\d+)\s*watts?',
        ],
        'origin': [
            r'Made in:\s*(.+?)(?:\n|$)',
            r'Origin:\s*(.+?)(?:\n|$)',
            r'Country:\s*(.+?)(?:\n|$)',
        ],
        'guarantee': [
            r'Guarantee:\s*(.+?)(?:\n|$)',
            r'Warranty:\s*(.+?)(?:\n|$)',
            r'(\d+\s*year\s+guarantee)',
        ],
        'care': [
            r'Care:\s*(.+?)(?:\n|$)',
            r'Cleaning:\s*(.+?)(?:\n|$)',
        ],
    }

    for spec_key, patterns in spec_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                specs[spec_key] = match.group(1).strip()
                break

    return specs
