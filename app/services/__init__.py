"""
Service module exports with async wrappers
"""
import asyncio
from typing import List, Dict, Any

# Import service classes
from .csv_parser import CSVParser
from .image_processor import ImageProcessor
from .text_processor import TextProcessor
from .product_search import ProductSearch
from .url_scraper import URLScraper
from .brand_voice import BrandVoice

# Create singleton instances
_csv_parser = CSVParser()
_image_processor = ImageProcessor()
_text_processor = TextProcessor()
_product_search = ProductSearch()
_url_scraper = URLScraper()
_brand_voice = BrandVoice()


class CSVParserService:
    """Async wrapper for CSV parser"""
    
    async def process(self, file_content: bytes, category: str) -> List[Dict[str, Any]]:
        """Process CSV file"""
        # Run sync function in executor
        loop = asyncio.get_event_loop()
        products = await loop.run_in_executor(None, _csv_parser.parse_csv, file_content)
        
        # Ensure each product has category
        for product in products:
            product['category'] = category
        
        return products


class ImageProcessorService:
    """Async wrapper for image processor"""
    
    async def process(self, file_content: bytes, category: str, filename: str) -> List[Dict[str, Any]]:
        """Process image file"""
        # Run sync function in executor
        loop = asyncio.get_event_loop()
        product = await loop.run_in_executor(None, _image_processor.process_image, file_content, filename)
        
        # Ensure product has category
        product['category'] = category
        
        # Return as list
        return [product]


class TextProcessorService:
    """Async wrapper for text processor"""
    
    async def process(self, text: str, category: str) -> List[Dict[str, Any]]:
        """Process free-form text"""
        # Run sync function in executor
        loop = asyncio.get_event_loop()
        product = await loop.run_in_executor(None, _text_processor.process_text, text)
        
        # Ensure product has category
        product['category'] = category
        
        # Return as list
        return [product]


class ProductSearchService:
    """Async wrapper for product search"""
    
    async def search(self, query: str, category: str, search_type: str = "sku") -> List[Dict[str, Any]]:
        """Search for products by SKU/EAN"""
        # Run sync function in executor
        loop = asyncio.get_event_loop()
        products = await loop.run_in_executor(None, _product_search.search, query, search_type)
        
        # Ensure each product has category
        for product in products:
            product['category'] = category
        
        return products


class URLScraperService:
    """Async wrapper for URL scraper"""
    
    async def scrape(self, url: str, category: str) -> List[Dict[str, Any]]:
        """Scrape URL for product data"""
        # Run sync function in executor
        loop = asyncio.get_event_loop()
        products = await loop.run_in_executor(None, _url_scraper.scrape_url, url)
        
        # Ensure each product has category
        for product in products:
            product['category'] = category
        
        return products


class BrandVoiceService:
    """Async wrapper for brand voice"""
    
    async def generate(self, products: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
        """Generate brand voice descriptions"""
        # Run sync function in executor
        loop = asyncio.get_event_loop()
        enhanced = await loop.run_in_executor(None, _brand_voice.enhance_products, products, category)
        
        return enhanced


# Export service instances
csv_parser = CSVParserService()
image_processor = ImageProcessorService()
text_processor = TextProcessorService()
product_search = ProductSearchService()
url_scraper = URLScraperService()
brand_voice = BrandVoiceService()
