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

    logger.info(f"Parsed {len(products)} produc
