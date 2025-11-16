📄 FILE 21: README.md (Complete Project Documentation)
# Universal Product Automation - Harts of Stur

Complete FastAPI backend for product automation, replacing Supabase Edge Functions with unified Python API.

## 🎯 Overview

This service provides 7 API endpoints for product data extraction, processing, and brand voice generation:

1. **PDF Extraction** - Extract products from supplier PDFs using AI
2. **Image OCR** - Extract product data from images using Google Cloud Vision
3. **SKU Search** - Search Harts of Stur website by SKU/barcode
4. **URL Scraping** - Scrape product details from web URLs
5. **Brand Voice Generation** - Generate Harts of Stur branded descriptions
6. **CSV Export** - Export products to CSV with HTML sanitization
7. **SEO Keywords** - Generate SEO-optimized meta descriptions

## 🏗️ Architecture

Universal Product Automation ├── FastAPI Backend (Python 3.11) │ ├── 7 API Routers (/api/*) │ ├── Docling Document Processing │ ├── OpenAI GPT-4 Integration │ └── Google Cloud Vision OCR ├── React Frontend (UniversalUploader.tsx) │ └── Connects to FastAPI endpoints └── Docker Deployment (Elestio) └── Single port (8080)


## 📋 Requirements

### Environment Variables

**Required:**
```bash
OPENAI_API_KEY=sk-proj-your-key-here
GOOGLE_APPLICATION_CREDENTIALS=/app/google-credentials.json
Optional (with defaults):

PORT=8080
HOST=0.0.0.0
LOG_LEVEL=info
MAX_FILE_SIZE_MB=50
ALLOWED_EXTENSIONS=pdf,docx,xlsx,pptx,html,txt
TEMP_DIR=/tmp/docling
ENABLE_OCR=true
CORS_ORIGINS=*
System Dependencies
Python 3.11+
Tesseract OCR
Poppler (PDF processing)
Docker & Docker Compose
🚀 Quick Start
Local Development
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY=sk-proj-your-key
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json

# Run the service
python -m app.main
Service runs on http://localhost:8080

Docker Deployment
# Build and run
docker-compose up --build

# Check logs
docker-compose logs -f docling-service

# Check health
curl http://localhost:8080/healthz
📚 API Documentation
Once running, visit:

Interactive API Docs: http://localhost:8080/docs
Alternative Docs: http://localhost:8080/redoc
🔌 API Endpoints
1. Extract PDF Products
POST /api/extract-pdf-products
Content-Type: multipart/form-data

file: [PDF file]
Response:

{
  "success": true,
  "data": {
    "products": [
      {
        "name": "Product Name",
        "brand": "Brand Name",
        "category": "Bakeware, Cookware",
        "sku": "SKU123",
        "description": "...",
        "specifications": {},
        "features": [],
        "confidence": 0.8
      }
    ]
  },
  "extracted_count": 5,
  "source": "Universal PDF Analysis"
}
2. Extract Image Products (OCR)
POST /api/extract-image-products
Content-Type: multipart/form-data

file: [Image file]
3. Search Product by SKU
POST /api/search-product-sku
Content-Type: application/json

{
  "sku": "SKU123"
}
4. Scrape Product URL
POST /api/scrape-product-url
Content-Type: application/json

{
  "url": "https://www.hartsofstur.com/products/..."
}
5. Generate Brand Voice
POST /api/generate-brand-voice
Content-Type: application/json

{
  "products": [
    {
      "name": "Product Name",
      "brand": "Brand",
      "category": "Bakeware, Cookware",
      "specifications": {}
    }
  ]
}
Response:

{
  "success": true,
  "products": [
    {
      "id": "uuid",
      "name": "Product Name",
      "brand": "Brand",
      "category": "Bakeware, Cookware",
      "descriptions": {
        "metaDescription": "150-160 char SEO description",
        "shortDescription": "<p>Bullet 1<br>Bullet 2<br>Bullet 3</p>",
        "longDescription": "<p>Meta...</p><p>Lifestyle...</p><p>Specs...</p>"
      }
    }
  ]
}
6. Export to CSV
POST /api/export-csv
Content-Type: application/json

{
  "products": [...]
}
Returns downloadable CSV file.

7. SEO Keywords
POST /api/seo-keywords
Content-Type: application/json

{
  "query": "stainless steel saucepan",
  "brand": "Harts of Stur",
  "market": "en-GB"
}
⚡ Performance & Timeouts
Long-Running Operations
PDF Processing can take 3-7 minutes for large files. To handle this:

Frontend: Use async/await with timeout handling
Backend: Increase timeout in docker-compose.yml
Alternative: Implement job queue (see Advanced section)
Timeout Configuration
docker-compose.yml:

environment:
  - REQUEST_TIMEOUT_SECONDS=600  # 10 minutes
Frontend (React):

const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), 600000); // 10 minutes

try {
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
    signal: controller.signal
  });
} catch (error) {
  if (error.name === 'AbortError') {
    console.log('Request timed out');
  }
} finally {
  clearTimeout(timeoutId);
}
🧪 Testing
See TESTING_GUIDE.md for complete testing sequence.

Quick test:

# Health check
curl http://localhost:8080/healthz

# Test PDF extraction
curl -X POST http://localhost:8080/api/extract-pdf-products \
  -F "file=@test.pdf"

# Test brand voice
curl -X POST http://localhost:8080/api/generate-brand-voice \
  -H "Content-Type: application/json" \
  -d '{
    "productData": {
      "name": "Stainless Steel Saucepan",
      "brand": "Le Creuset",
      "category": "Bakeware, Cookware"
    }
  }'
🎨 Frontend Integration
See REACT_INTEGRATION.md for updating React frontend.

Quick change:

// Change API base URL (ONE LINE CHANGE)
const API_BASE = 'https://your-elestio-domain.com/api';
// or for local testing:
const API_BASE = 'http://localhost:8080/api';
📁 Project Structure
docling-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── config.py            # Configuration
│   ├── models.py            # Pydantic models
│   ├── routers/             # API endpoints
│   │   ├── pdf.py          # PDF extraction
│   │   ├── image.py        # Image OCR
│   │   ├── sku.py          # SKU search
│   │   ├── url.py          # URL scraping
│   │   ├── brand_voice.py  # Brand voice generation
│   │   ├── export_csv.py   # CSV export
│   │   └── seo.py          # SEO keywords
│   ├── services/
│   │   └── document_processor.py  # Docling integration
│   └── utils/
│       └── text_processing.py     # Helper functions
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
🔧 Troubleshooting
ImportError: cannot import name 'X' from 'app.models'
Fix: Ensure app/models.py has all required models. See models.py for complete list.

SyntaxError in main.py
Fix: Ensure main.py is exactly 332 lines with correct indentation.

OpenAI API errors
Fix: Check OPENAI_API_KEY is set correctly:

docker-compose exec docling-service env | grep OPENAI
Google Vision API errors
Fix: Ensure credentials file is mounted:

volumes:
  - ./google-credentials.json:/app/google-credentials.json
environment:
  - GOOGLE_APPLICATION_CREDENTIALS=/app/google-credentials.json
PDF processing takes too long
Solutions:

Increase timeout (see Performance section)
Implement background job queue (Celery/Redis)
Use streaming responses
Process only first N pages
🚢 Deployment (Elestio)
# 1. SSH to Elestio
ssh root@your-elestio-instance.com

# 2. Navigate to app directory
cd /opt/app/docling-service

# 3. Pull latest from GitHub
git fetch origin
git reset --hard origin/main

# 4. Set environment variables (in Elestio dashboard)
OPENAI_API_KEY=sk-proj-...
GOOGLE_APPLICATION_CREDENTIALS=/app/google-credentials.json

# 5. Rebuild and restart
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 6. Check logs
docker-compose logs -f docling-service

# 7. Test
curl http://localhost:8080/healthz
📊 Monitoring
Check service status:

docker-compose ps
View logs:

docker-compose logs --tail=100 -f docling-service
Check resource usage:

docker stats docling-service
🔐 Security
Never commit API keys to git
Use environment variables for all secrets
Enable CORS only for trusted domains in production
Validate all file uploads
Sanitize HTML in CSV exports
📝 License
Proprietary - Harts of Stur / Ignite AI Solutions

🆘 Support
For issues or questions:

Check TESTING_GUIDE.md
Check REACT_INTEGRATION.md
Review logs: docker-compose logs
Check API docs: http://localhost:8080/docs
Version: 2.0.0
Last Updated: 2025-11-16
Python: 3.11+
FastAPI: 0.115.0


---

## 📄 **FILE 22: TESTING_GUIDE.md** (Complete Testing Sequence)

```markdown
# Testing Guide - Universal Product Automation

Complete testing sequence for all 7 API endpoints.

## 🎯 Pre-requisites

1. **Service Running:**
   ```bash
   docker-compose up -d
   curl http://localhost:8080/healthz
Environment Variables Set:

docker-compose exec docling-service env | grep -E "OPENAI|GOOGLE"
Test Files Prepared:

test-product.pdf - Sample product catalog PDF
test-product.jpg - Sample product image with text
Valid SKU from Harts website
Valid product URL from Harts website
📋 Testing Sequence
Test 1: Health Check ✓
Endpoint: GET /healthz

curl -X GET http://localhost:8080/healthz
Expected Response:

{
  "status": "healthy",
  "timestamp": "2025-11-16T...",
  "version": "1.0.0",
  "docling_available": true
}
✅ Pass Criteria: Status 200, status: "healthy", docling_available: true

Test 2: PDF Product Extraction 📄
Endpoint: POST /api/extract-pdf-products

Timeout: 3-7 minutes for large PDFs

curl -X POST http://localhost:8080/api/extract-pdf-products \
  -F "file=@test-product.pdf" \
  -o pdf-response.json
Expected Response:

{
  "success": true,
  "data": {
    "products": [
      {
        "name": "Stainless Steel Saucepan",
        "brand": "Le Creuset",
        "category": "Bakeware, Cookware",
        "sku": "ABC123",
        "description": "...",
        "specifications": {},
        "features": [],
        "colors": [],
        "materials": [],
        "confidence": 0.8,
        "_extraction_method": "universal-analysis"
      }
    ]
  },
  "extracted_count": 5,
  "source": "Universal PDF Analysis",
  "processing_summary": {
    "detected_format": "UNIVERSAL",
    "extraction_method": "universal-ai-analysis",
    "file_name": "test-product.pdf",
    "processing_time_seconds": 45.2
  }
}
✅ Pass Criteria:

success: true
extracted_count > 0
Products have name, brand, category
Valid category from allowed list
❌ Common Errors:

{
  "success": false,
  "processing_summary": {
    "error": "No readable text found in PDF"
  }
}
Fix: PDF may be scanned image - use OCR-enabled PDF or try image extraction

Test 3: Image OCR Extraction 🖼️
Endpoint: POST /api/extract-image-products

Timeout: 10-30 seconds

curl -X POST http://localhost:8080/api/extract-image-products \
  -F "file=@test-product.jpg" \
  -o image-response.json
Expected Response:

{
  "success": true,
  "products": [
    {
      "name": "Product Name from Image",
      "brand": "ZWILLING",
      "category": "Knives, Cutlery",
      "sku": "ABC123",
      "barcode": "5012345678901",
      "specifications": {},
      "ocrText": "Extracted text...",
      "ocrConfidence": "medium",
      "extraction_method": "google-vision-ocr",
      "confidence": 0.7
    }
  ]
}
✅ Pass Criteria:

success: true
products array has at least 1 product
ocrText contains extracted text
❌ Common Errors:

{
  "detail": "Google Vision API not configured"
}
Fix: Set GOOGLE_APPLICATION_CREDENTIALS environment variable

Test 4: SKU Search 🔍
Endpoint: POST /api/search-product-sku

Timeout: 5-15 seconds

curl -X POST http://localhost:8080/api/search-product-sku \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "12345"
  }' \
  -o sku-response.json
Expected Response (Found):

{
  "success": true,
  "products": [
    {
      "name": "Product Name",
      "brand": "LE CREUSET",
      "category": "Bakeware, Cookware",
      "sku": "12345",
      "description": "...",
      "source_url": "https://www.hartsofstur.com/search?q=12345",
      "extraction_method": "sku-search",
      "confidence": 0.8
    }
  ]
}
Expected Response (Not Found):

{
  "success": false,
  "products": []
}
✅ Pass Criteria:

Status 200 (even if not found)
If found: products array has 1 product with matching SKU
If not found: success: false, products: []
Test 5: URL Scraping 🌐
Endpoint: POST /api/scrape-product-url

Timeout: 5-20 seconds

curl -X POST http://localhost:8080/api/scrape-product-url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.hartsofstur.com/products/le-creuset-saucepan"
  }' \
  -o url-response.json
Expected Response:

{
  "success": true,
  "products": [
    {
      "name": "Le Creuset Saucepan",
      "brand": "LE CREUSET",
      "category": "Bakeware, Cookware",
      "sku": "extracted-from-url",
      "description": "Meta description from page",
      "specifications": {},
      "source_url": "https://www.hartsofstur.com/products/...",
      "extraction_method": "url-scraping",
      "confidence": 0.75
    }
  ]
}
✅ Pass Criteria:

success: true
Product name matches page title
source_url matches input URL
❌ Common Errors:

{
  "detail": "Request timed out"
}
Fix: URL may be unreachable or slow - check network

Test 6: Brand Voice Generation 🎨
Endpoint: POST /api/generate-brand-voice

Timeout: 10-60 seconds (depends on OpenAI API)

Test 6a: Single Product

curl -X POST http://localhost:8080/api/generate-brand-voice \
  -H "Content-Type: application/json" \
  -d '{
    "productData": {
      "name": "Stainless Steel Saucepan 20cm",
      "brand": "Le Creuset",
      "category": "Bakeware, Cookware",
      "specifications": {
        "material": "Stainless steel",
        "capacity": "2.5l",
        "dimensions": "20 x 15 x 10",
        "weight": "1.2kg"
      },
      "features": ["Triple layer base", "Riveted handles", "Dishwasher safe"]
    },
    "category": "Bakeware, Cookware"
  }' \
  -o brand-voice-response.json
Test 6b: Multiple Products

curl -X POST http://localhost:8080/api/generate-brand-voice \
  -H "Content-Type: application/json" \
  -d '{
    "products": [
      {
        "name": "Product 1",
        "brand": "Brand A",
        "category": "Electricals"
      },
      {
        "name": "Product 2",
        "brand": "Brand B",
        "category": "Knives, Cutlery"
      }
    ]
  }' \
  -o brand-voice-multi-response.json
Expected Response:

{
  "success": true,
  "products": [
    {
      "id": "uuid",
      "name": "Stainless Steel Saucepan 20cm",
      "brand": "Le Creuset",
      "category": "Bakeware, Cookware",
      "sku": "",
      "specifications": {
        "material": "Stainless steel",
        "capacity": "2.5l"
      },
      "features": ["Triple layer base", "Riveted handles"],
      "descriptions": {
        "metaDescription": "The Le Creuset Stainless Steel Saucepan 20cm provides reliable performance for everyday cooking. Stainless steel construction with triple layer base.",
        "shortDescription": "<p>Stainless steel construction<br>Triple layer base<br>Dishwasher safe</p>",
        "longDescription": "<p>The Le Creuset Stainless Steel Saucepan 20cm provides reliable performance for everyday cooking.</p><p>Stainless Steel Saucepan 20cm is designed for everyday use with clear, accurate details to help you choose with confidence.</p><p>Capacity: 2.5l.</p><p>Dimensions: 20(H) x 15(W) x 10(D) cm.</p><p>Weight: 1.2kg.</p>"
      }
    }
  ]
}
✅ Pass Criteria:

success: true
Each product has descriptions object
metaDescription: 150-160 characters, single sentence
shortDescription: <p>...<br>...<br>...</p> format, ≤150 chars
longDescription: Multiple <p> tags, ≤2000 chars
No retail terms (shop, buy, order, price)
UK English spelling
No "Since 1919" or heritage mentions
❌ Common Errors:

{
  "detail": "OpenAI API key not configured"
}
Fix: Set OPENAI_API_KEY environment variable

Test 7: CSV Export 📊
Endpoint: POST /api/export-csv

Timeout: 5-15 seconds

# First, generate brand voice descriptions
curl -X POST http://localhost:8080/api/generate-brand-voice \
  -H "Content-Type: application/json" \
  -d '{
    "productData": {
      "name": "Test Product",
      "brand": "Test Brand",
      "category": "General"
    }
  }' > products-for-csv.json

# Then export to CSV
curl -X POST http://localhost:8080/api/export-csv \
  -H "Content-Type: application/json" \
  -d @products-for-csv.json \
  -o export.csv
Expected Response:

HTTP 200
Content-Type: text/csv; charset=utf-8
Content-Disposition: attachment; filename=harts_products_export.csv
File downloads as CSV
CSV Structure:

sku,barcode,name,shortDescription,longDescription,metaDescription,weightGrams,weightHuman
SKU123,5012345678901,Product Name,"<p>Bullet 1<br>Bullet 2<br>Bullet 3</p>","<p>Long description...</p>",Meta description,1200,1.2kg
✅ Pass Criteria:

File downloads successfully
CSV has headers
Rows contain product data
HTML is sanitized (no <script>, <iframe>)
UTF-8 BOM present (Excel compatibility)
Test 8: SEO Keywords 🔎
Endpoint: POST /api/seo-keywords

Timeout: 5-30 seconds

curl -X POST http://localhost:8080/api/seo-keywords \
  -H "Content-Type: application/json" \
  -d '{
    "query": "stainless steel saucepan 20cm",
    "brand": "Harts of Stur",
    "market": "en-GB",
    "maxKeywords": 6
  }' \
  -o seo-response.json
Expected Response:

{
  "success": true,
  "keywords": [
    "stainless steel",
    "saucepan",
    "20cm",
    "cookware",
    "kitchen",
    "premium"
  ],
  "meta": {
    "description": "Discover premium stainless steel saucepan 20cm at Harts of Stur. Quality cookware for modern kitchens with reliable performance.",
    "query": "stainless steel saucepan 20cm",
    "brand": "Harts of Stur",
    "market": "en-GB"
  }
}
✅ Pass Criteria:

success: true
keywords array has 1-6 relevant keywords
meta.description is 150-160 characters
No banned keywords (shop, buy, price, etc.)
🔄 End-to-End Workflow Test
Complete workflow: PDF → Brand Voice → CSV Export

# 1. Extract products from PDF
curl -X POST http://localhost:8080/api/extract-pdf-products \
  -F "file=@test-product.pdf" \
  > step1-extracted.json

# 2. Generate brand voice descriptions
curl -X POST http://localhost:8080/api/generate-brand-voice \
  -H "Content-Type: application/json" \
  -d @step1-extracted.json \
  > step2-branded.json

# 3. Export to CSV
curl -X POST http://localhost:8080/api/export-csv \
  -H "Content-Type: application/json" \
  -d @step2-branded.json \
  -o final-export.csv

# 4. Verify CSV
head final-export.csv
wc -l final-export.csv
✅ Pass Criteria:

All 3 steps complete without errors
final-export.csv contains all products
Descriptions are properly formatted
⚡ Performance Benchmarks
| Endpoint | Expected Time | Max Timeout | |----------|--------------|-------------| | Health Check | <100ms | 5s | | PDF Extraction | 30s - 7min | 10min | | Image OCR | 5-30s | 1min | | SKU Search | 2-15s | 30s | | URL Scraping | 3-20s | 30s | | Brand Voice | 10-60s | 2min | | CSV Export | 1-15s | 30s | | SEO Keywords | 5-30s | 1min |

🐛 Troubleshooting Test Failures
PDF Extraction Returns Empty Products
Symptoms:

{
  "success": false,
  "processing_summary": {
    "error": "No products detected in extracted text"
  }
}
Fixes:

Check PDF has readable text (not scanned image)
Verify OPENAI_API_KEY is set
Check logs: docker-compose logs docling-service | grep "PDF"
Brand Voice Uses Fallback Templates
Symptoms: Descriptions look generic/templated

Fixes:

Verify OPENAI_API_KEY is valid
Check OpenAI API quota/limits
Review logs for OpenAI errors
Image OCR Fails
Symptoms:

{
  "detail": "Google Vision API not configured"
}
Fixes:

Set GOOGLE_APPLICATION_CREDENTIALS environment variable
Mount credentials file in docker-compose.yml
Verify credentials file is valid JSON
📊 Test Results Checklist

Health check returns healthy status

PDF extraction works with sample PDF

Image OCR extracts text from product image

SKU search finds products on Harts website

URL scraping extracts product details

Brand voice generates proper descriptions

CSV export creates valid downloadable file

SEO keywords generates relevant terms

End-to-end workflow completes successfully

All endpoints handle errors gracefully

Response times within acceptable limits
