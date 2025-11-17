"""
Pydantic models for request/response validation
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ProductSpecifications(BaseModel):
    """Product specifications"""
    material: Optional[str] = None
    bladeLength: Optional[str] = None
    dimensions: Optional[str] = None
    weight: Optional[str] = None
    weightKg: Optional[float] = None
    capacity: Optional[str] = None
    powerW: Optional[int] = None
    programs: Optional[str] = None
    origin: Optional[str] = None
    madeIn: Optional[str] = None
    guarantee: Optional[str] = None
    warranty: Optional[str] = None
    care: Optional[str] = None


class ProductDescriptions(BaseModel):
    """Generated product descriptions"""
    shortDescription: str = ""
    metaDescription: str = ""
    longDescription: str = ""


class Product(BaseModel):
    """Core product model"""
    sku: Optional[str] = None
    barcode: Optional[str] = None
    name: str
    brand: Optional[str] = None
    category: str
    range: Optional[str] = None
    collection: Optional[str] = None
    colour: Optional[str] = None
    pattern: Optional[str] = None
    style: Optional[str] = None
    finish: Optional[str] = None
    features: List[str] = Field(default_factory=list)
    benefits: List[str] = Field(default_factory=list)
    specifications: Dict[str, Any] = Field(default_factory=dict)
    isNonStick: bool = False
    usage: Optional[str] = None
    audience: Optional[str] = None
    weightGrams: Optional[int] = None
    weightHuman: Optional[str] = None
    descriptions: Optional[ProductDescriptions] = None
    _seo_validation: Optional[Dict[str, Any]] = None


class ParseCSVRequest(BaseModel):
    """Request for CSV parsing"""
    category: str


class ParseImageRequest(BaseModel):
    """Request for image parsing"""
    category: str


class ProductSearchRequest(BaseModel):
    """Request for SKU/EAN product lookup"""
    query: str
    category: str
    search_type: str = Field(default="sku", description="Search type: sku or ean")


class URLScraperRequest(BaseModel):
    """Request for URL scraping"""
    url: str
    category: str


class TextProcessorRequest(BaseModel):
    """Request for free text processing"""
    text: str
    category: str


class ExportCSVRequest(BaseModel):
    """Request for CSV export"""
    products: List[Product]
    prefer_p_tags: bool = True


class SEOValidationResult(BaseModel):
    """SEO validation result"""
    original: str
    fixed: str
    issues: List[str] = Field(default_factory=list)
    keywords_present: List[str] = Field(default_factory=list)


class ProcessingResponse(BaseModel):
    """Standard processing response"""
    success: bool
    products: List[Product] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str = "1.0.0"
    openai_configured: bool
