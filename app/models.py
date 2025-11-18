from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ExtractRequest(BaseModel):
    file_url: Optional[str] = None
    force_full_ocr: bool = False
    page_start: int = 1
    page_end: Optional[int] = None
    batch_size: int = 40
    per_batch_timeout_sec: int = 120
    return_markdown: bool = True
    return_json: bool = True
    category: Optional[str] = "Electricals"

class ProductFields(BaseModel):
    brand_name: Optional[str] = None
    product_type: Optional[str] = None
    sku_code: Optional[str] = None
    description: Optional[str] = None
    features: Optional[List[str]] = None
    tech_specifications: Optional[List[str]] = None

class ExtractResponse(BaseModel):
    pages_processed: int
    markdown: Optional[str] = None
    doc_json: Optional[dict] = None
    inferred: Optional[ProductFields] = None
    notes: Optional[List[str]] = None

class ProductDescription(BaseModel):
    shortDescription: str
    metaDescription: str
    longDescription: str

class Product(BaseModel):
    id: str
    name: str
    brand: str = ""
    sku: str = ""
    category: Optional[str] = None
    source: Optional[str] = None
    specifications: Optional[Dict[str, Any]] = None
    features: Optional[List[str]] = None
    descriptions: Optional[ProductDescription] = None
    price: Optional[str] = None

class ProcessingResponse(BaseModel):
    success: bool
    products: List[Product]
    message: Optional[str] = None
    pages_processed: Optional[int] = None
    markdown: Optional[str] = None
    inferred: Optional[dict] = None
    notes: Optional[List[str]] = None

class BrandVoiceRequest(BaseModel):
    products: List[Dict[str, Any]]
    category: str
    extractionHints: Optional[Dict[str, Any]] = None

class ParseCSVRequest(BaseModel):
    category: str

class ParseImageRequest(BaseModel):
    category: str

class SearchProductRequest(BaseModel):
    query: str
    category: str
    search_type: str = "sku"

class ScrapeURLRequest(BaseModel):
    url: str
    category: str

class ProcessTextRequest(BaseModel):
    text: str
    category: str
