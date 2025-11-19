"""
CSV Parser Service
Extracts product data from CSV files
"""
import csv
import io
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


async def process(file_content: bytes, category: str) -> List[Dict[str, Any]]:
    """
    Process CSV file and extract product data
    Args:
        file_content: CSV file content as bytes
        category: Product category
    Returns:
        List of product dictionaries
    Raises:
        ValueError: If CSV is invalid or empty
    """
    try:
        # Decode content
        text_content = file_content.decode('utf-8-sig')  # Handle BOM
    except UnicodeDecodeError:
        try:
            text_content = file_content.decode('latin-1')  # Fallback encoding
        except UnicodeDecodeError:
            raise ValueError("Unable to decode CSV file - invalid encoding")

    # DEBUG: Log first 500 chars of CSV
    logger.info(f"CSV Content (first 500 chars): {text_content[:500]}")

    # Parse CSV
    reader = csv.DictReader(io.StringIO(text_content))

    # DEBUG: Log headers
    logger.info(f"CSV Headers: {reader.fieldnames}")

    products = []
    row_num = 0

    for row in reader:
        row_num += 1
        
        # DEBUG: Log first 3 rows
        if row_num <= 3:
            logger.info(f"Row {row_num}: {row}")

        try:
            product = parse_csv_row(row, category)
            if product:
                products.append(product)
            else:
                logger.warning(f"Row {row_num} produced no product (name field missing or invalid)")
        except Exception as e:
            logger.warning(f"Failed to parse row {row_num}: {e}")
            continue

    if not products:
        raise ValueError(f"No valid products found in CSV. Processed {row_num} rows with headers: {reader.fieldnames}")

    logger.info(f"Parsed {len(products)} products from CSV")

    return products


def parse_csv_row(row: Dict[str, str], category: str) -> Dict[str, Any]:
    """
    Parse a single CSV row into product dictionary
    Args:
        row: CSV row as dictionary
        category: Product category
    Returns:
        Product dictionary or None if row is invalid
    """
    # Get product name (required)
    name = (
        row.get('name') or
        row.get('Name') or
        row.get('product_name') or
        row.get('Product Name') or
        row.get('Product Title') or
        row.get('title') or
        row.get('Title') or
        row.get('Description') or
        row.get('description') or
        row.get('Short Description') or
        row.get('short_description') or
        row.get('Code')  # Also try Code field
    )

    if not name or not name.strip():
        return None

    # Build product dict
    product = {
        "name": name.strip(),
        "category": category,
        "sku": extract_csv_field(row, ['sku', 'SKU', 'product_code', 'item_code']),
        "barcode": extract_csv_field(row, ['barcode', 'ean', 'EAN', 'upc', 'gtin', 'Barcode']),
        "brand": extract_csv_field(row, ['brand', 'Brand', 'manufacturer']),
        "range": extract_csv_field(row, ['range', 'Range', 'collection', 'series']),
        "collection": extract_csv_field(row, ['collection', 'Collection']),
        "colour": extract_csv_field(row, ['colour', 'color', 'Colour', 'Color']),
        "pattern": extract_csv_field(row, ['pattern', 'Pattern', 'design']),
        "style": extract_csv_field(row, ['style', 'Style', 'type']),
        "finish": extract_csv_field(row, ['finish', 'Finish', 'surface']),
    }

    # Parse features (could be pipe-separated or semicolon-separated)
    features_str = extract_csv_field(row, ['features', 'Features', 'key_features'])
    if features_str:
        product["features"] = parse_list_field(features_str)
    else:
        product["features"] = []

    # Parse benefits
    benefits_str = extract_csv_field(row, ['benefits', 'Benefits', 'advantages'])
    if benefits_str:
        product["benefits"] = parse_list_field(benefits_str)
    else:
        product["benefits"] = []

    # Parse specifications
    product["specifications"] = extract_specifications_from_row(row)

    # Parse usage
    product["usage"] = extract_csv_field(row, ['usage', 'Usage', 'use', 'application'])

    # Parse audience
    product["audience"] = extract_csv_field(row, ['audience', 'Audience', 'target', 'for'])

    return product


def extract_csv_field(row: Dict[str, str], keys: List[str]) -> str:
    """
    Extract field from CSV row using multiple possible keys
    Args:
        row: CSV row dictionary
        keys: List of possible key names
    Returns:
        Field value or empty string
    """
    for key in keys:
        if key in row and row[key]:
            value = row[key].strip()
            if value and value.lower() not in ['n/a', 'none', 'null', '']:
                return value
    return ""


def parse_list_field(value: str) -> List[str]:
    """
    Parse list field from string (pipe or semicolon separated)
    Args:
        value: String value to parse
    Returns:
        List of strings
    """
    if not value:
        return []

    # Try pipe separator first
    if '|' in value:
        return [item.strip() for item in value.split('|') if item.strip()]

    # Try semicolon separator
    if ';' in value:
        return [item.strip() for item in value.split(';') if item.strip()]

    # Try comma separator (only if string is long enough to likely be a list)
    if ',' in value and len(value) > 50:
        return [item.strip() for item in value.split(',') if item.strip()]

    # Single item
    return [value.strip()] if value.strip() else []


def extract_specifications_from_row(row: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract specifications from CSV row
    Args:
        row: CSV row dictionary
    Returns:
        Specifications dictionary
    """
    specs = {}

    # Common specification fields
    spec_fields = {
        'material': ['material', 'Material', 'materials'],
        'bladeLength': ['blade_length', 'bladeLength', 'Blade Length'],
        'dimensions': ['dimensions', 'Dimensions', 'size', 'Size'],
        'weight': ['weight', 'Weight'],
        'weightKg': ['weight_kg', 'weightKg', 'Weight (kg)'],
        'capacity': ['capacity', 'Capacity', 'volume'],
        'powerW': ['power', 'Power', 'power_w', 'wattage'],
        'programs': ['programs', 'Programs', 'settings', 'modes'],
        'origin': ['origin', 'Origin', 'made_in', 'country'],
        'madeIn': ['made_in', 'Made In', 'madeIn'],
        'guarantee': ['guarantee', 'Guarantee', 'warranty'],
        'warranty': ['warranty', 'Warranty'],
        'care': ['care', 'Care', 'care_instructions']
    }

    for spec_key, possible_keys in spec_fields.items():
        value = extract_csv_field(row, possible_keys)
        if value:
            specs[spec_key] = value

    return specs
