"""
PDF Processor Service
Uses Docling to extract products from PDF catalogues
"""
import os
import re
import logging
import tempfile
from typing import List, Dict, Any
from docling.document_converter import DocumentConverter

logger = logging.getLogger(__name__)

# Initialize converter once (singleton pattern for performance)
_converter = None

def get_converter():
    global _converter
    if _converter is None:
        _converter = DocumentConverter()
    return _converter

async def process(file_content: bytes, category: str) -> List[Dict[str, Any]]:
    """
    Extract products from PDF using Docling
    
    Args:
        file_content: PDF file bytes
        category: Product category
    
    Returns:
        List of product dicts
    """
    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name
    
    try:
        logger.info(f"Processing PDF: {tmp_path}")
        
        converter = get_converter()
        result = converter.convert(tmp_path)
        markdown = result.document.export_to_markdown()
        
        logger.info(f"Extracted {len(markdown)} chars of markdown")
        
        # Parse markdown to find individual products
        products = extract_products_from_markdown(markdown, category)
        
        if not products:
            # Fallback: return whole document as one product
            logger.warning("No individual products found, returning as single product")
            products = [{
                "name": "Product from PDF",
                "brand": "",
                "sku": "",
                "category": category,
                "rawExtractedContent": markdown[:5000],
                "features": extract_features(markdown),
                "specifications": extract_specifications(markdown),
                "descriptions": {
                    "shortDescription": "",
                    "metaDescription": "",
                    "longDescription": ""
                }
            }]
        
        logger.info(f"Extracted {len(products)} products from PDF")
        return products
        
    finally:
        os.unlink(tmp_path)


def extract_products_from_markdown(markdown: str, category: str) -> List[Dict[str, Any]]:
    """
    Parse markdown to identify individual products
    
    Looks for patterns like:
    - SKU codes (e.g., SES882BSS4GUK1)
    - Product headers
    - Product tables
    """
    products = []
    
    # Pattern 1: Find SKU codes (typically 8-15 alphanumeric chars)
    sku_pattern = r'\b([A-Z]{2,4}[0-9]{3,}[A-Z0-9]{2,})\b'
    skus_found = list(set(re.findall(sku_pattern, markdown)))
    
    # Pattern 2: Find product names (lines with brand + product type)
    product_name_pattern = r'^#+\s*(.+(?:Machine|Maker|Cooker|Blender|Mixer|Kettle|Toaster|Iron|Fryer|Oven|Grill|Pan|Pot|Set).*)$'
    names_found = re.findall(product_name_pattern, markdown, re.MULTILINE | re.IGNORECASE)
    
    # Pattern 3: Look for table rows with product data
    table_row_pattern = r'\|([^|]+)\|([^|]+)\|([^|]*)\|'
    table_matches = re.findall(table_row_pattern, markdown)
    
    # If we found SKUs, create products for each
    if skus_found:
        logger.info(f"Found {len(skus_found)} SKU codes")
        
        for sku in skus_found[:20]:  # Limit to 20 products
            # Try to find context around this SKU
            context = extract_context_around(markdown, sku, chars=500)
            name = extract_product_name(context) or f"Product {sku}"
            brand = extract_brand(context)
            
            products.append({
                "name": name,
                "brand": brand,
                "sku": sku,
                "category": category,
                "rawExtractedContent": context,
                "features": extract_features(context),
                "specifications": extract_specifications(context),
                "descriptions": {
                    "shortDescription": "",
                    "metaDescription": "",
                    "longDescription": ""
                }
            })
    
    # If we found product names but no SKUs
    elif names_found:
        logger.info(f"Found {len(names_found)} product names")
        
        for name in names_found[:20]:
            name = name.strip()
            context = extract_context_around(markdown, name, chars=500)
            
            products.append({
                "name": name,
                "brand": extract_brand(context),
                "sku": "",
                "category": category,
                "rawExtractedContent": context,
                "features": extract_features(context),
                "specifications": extract_specifications(context),
                "descriptions": {
                    "shortDescription": "",
                    "metaDescription": "",
                    "longDescription": ""
                }
            })
    
    return products


def extract_context_around(text: str, search_term: str, chars: int = 500) -> str:
    """Extract text around a search term"""
    idx = text.find(search_term)
    if idx == -1:
        return ""
    
    start = max(0, idx - chars // 2)
    end = min(len(text), idx + len(search_term) + chars // 2)
    
    return text[start:end]


def extract_product_name(context: str) -> str:
    """Try to extract product name from context"""
    # Look for header patterns
    header_match = re.search(r'^#+\s*(.+)$', context, re.MULTILINE)
    if header_match:
        name = header_match.group(1).strip()
        if len(name) > 10 and len(name) < 100:
            return name
    
    # Look for bold text that might be product name
    bold_match = re.search(r'\*\*([^*]+)\*\*', context)
    if bold_match:
        name = bold_match.group(1).strip()
        if len(name) > 10 and len(name) < 100:
            return name
    
    return ""


def extract_brand(context: str) -> str:
    """Try to extract brand from context"""
    # Common appliance brands
    brands = [
        "Sage", "Breville", "KitchenAid", "Kenwood", "Smeg", "Dualit",
        "Cuisinart", "Magimix", "Russell Hobbs", "Morphy Richards",
        "De'Longhi", "Nespresso", "Bosch", "Siemens", "Miele",
        "Le Creuset", "Tramontina", "Zwilling", "Wusthof", "CASO"
    ]
    
    context_lower = context.lower()
    for brand in brands:
        if brand.lower() in context_lower:
            return brand
    
    return ""


def extract_features(context: str) -> List[str]:
    """Extract feature bullet points"""
    features = []
    
    # Look for bullet points
    bullet_pattern = r'[•\-\*]\s*(.+)'
    matches = re.findall(bullet_pattern, context)
    
    for match in matches[:10]:
        feature = match.strip()
        if 10 < len(feature) < 200:
            features.append(feature)
    
    return features


def extract_specifications(context: str) -> Dict[str, Any]:
    """Extract specifications from context"""
    specs = {}
    
    # Dimensions pattern
    dim_match = re.search(r'(\d+)\s*x\s*(\d+)\s*x\s*(\d+)\s*(?:mm|cm)', context, re.IGNORECASE)
    if dim_match:
        specs["dimensions"] = f"{dim_match.group(1)} x {dim_match.group(2)} x {dim_match.group(3)}"
    
    # Weight pattern
    weight_match = re.search(r'(\d+\.?\d*)\s*kg', context, re.IGNORECASE)
    if weight_match:
        specs["weight"] = f"{weight_match.group(1)}kg"
    
    # Power pattern
    power_match = re.search(r'(\d{3,4})\s*[Ww](?:att)?', context)
    if power_match:
        specs["powerW"] = int(power_match.group(1))
    
    # Capacity pattern
    capacity_match = re.search(r'(\d+\.?\d*)\s*(?:L|litre|liter)', context, re.IGNORECASE)
    if capacity_match:
        specs["capacity"] = f"{capacity_match.group(1)}L"
    
    return specs
EOF

# Add import to services __init__.py
echo "from . import pdf_processor" >> /opt/app/docling-service/app/services/__init__.py

# Update main.py to use the new service
python3 << 'PYEOF'
import re

with open('/opt/app/docling-service/app/main.py', 'r') as f:
    content = f.read()

# Update imports to include pdf_processor
old_import = "from app.services import csv_parser, image_processor, text_processor, product_search, url_scraper, brand_voice"
new_import = "from app.services import csv_parser, image_processor, text_processor, product_search, url_scraper, brand_voice, pdf_processor"

if old_import in content:
    content = content.replace(old_import, new_import)

# Replace the extract-pdf-products endpoint
old_endpoint = '''@app.post("/api/extract-pdf-products")
async def extract_pdf_products_endpoint(
    file: UploadFile = File(...),
    category: str = Form(default="Electricals"),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """Extract products from PDF using Docling"""
    check_key(x_api_key)
    
    try:
        if category not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        
        logger.info(f"📄 Processing PDF for category: {category}")
        
        # Save uploaded file temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            from docling.document_converter import DocumentConverter
            
            converter = DocumentConverter()
            result = converter.convert(tmp_path)
            markdown = result.document.export_to_markdown()
            
            # Extract product info from markdown
            products = [{
                "name": "Product from PDF",
                "brand": "",
                "sku": "",
                "category": category,
                "rawExtractedContent": markdown,
                "descriptions": {
                    "shortDescription": markdown[:200],
                    "metaDescription": markdown[:160],
                    "longDescription": markdown
                }
            }]
            
            # Generate brand voice
            if brand_voice:
                products = await brand_voice.generate(products, category)
            
            return ProcessingResponse(success=True, products=products)
            
        finally:
            import os
            os.unlink(tmp_path)'''

new_endpoint = '''@app.post("/api/extract-pdf-products")
async def extract_pdf_products_endpoint(
    file: UploadFile = File(...),
    category: str = Form(default="Electricals"),
    x_api_key: Optional[str] = Header(default=None, alias="x-api-key"),
):
    """Extract products from PDF using Docling"""
    check_key(x_api_key)
    
    try:
        if category not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid category")
        
        logger.info(f"📄 Processing PDF for category: {category}")
        
        if not pdf_processor:
            raise HTTPException(status_code=503, detail="PDF processor not available")
        
        file_content = await file.read()
        products = await pdf_processor.process(file_content, category)
        
        logger.info(f"✅ Extracted {len(products)} products from PDF")
        
        return ProcessingResponse(success=True, products=products)'''

if old_endpoint in content:
    content = content.replace(old_endpoint, new_endpoint)
    print("✅ Updated extract-pdf-products endpoint")
else:
    print("⚠️ Could not find old endpoint to replace")

with open('/opt/app/docling-service/app/main.py', 'w') as f:
    f.write(content)
