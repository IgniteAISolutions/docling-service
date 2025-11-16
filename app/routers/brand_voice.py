"""
Brand Voice Generation Router
Generate Harts of Stur branded product descriptions using AI
Based on latest Supabase edge function with SEO optimization
"""
import logging
import time
import os
import re
import json
from typing import List, Dict, Any, Optional, Set
from fastapi import APIRouter, HTTPException
from openai import OpenAI
import requests

from ..models import BrandVoiceRequest, BrandVoiceResponse, ProcessedProduct, BrandVoiceDescriptions
from ..utils import generate_product_id
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Brand Voice"])

# Initialize OpenAI client
openai_client = None
if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# =========================================
# CONSTANTS & CONFIGURATION
# =========================================

ALLOWED_CATEGORIES = {
    "Bakeware, Cookware",
    "Dining, Drink, Living",
    "Electricals",
    "Food Prep & Tools",
    "Knives, Cutlery",
    "Clothing",
    "General"
}

CATEGORY_TEMPLATES = {
    "Clothing": {
        "lifestyle_weight": 100,
        "technical_weight": 0,
        "intro": "Elevate your kitchen style with",
        "features_intro": "Designed for comfort and practicality"
    },
    "Electricals": {
        "lifestyle_weight": 0,
        "technical_weight": 100,
        "intro": "Precision-engineered for modern kitchens",
        "features_intro": "Technical specifications"
    },
    "Bakeware, Cookware": {
        "lifestyle_weight": 50,
        "technical_weight": 50,
        "intro": "Trusted by home cooks and professionals",
        "features_intro": "Expertly crafted for exceptional results"
    },
    "Dining, Drink, Living": {
        "lifestyle_weight": 80,
        "technical_weight": 20,
        "intro": "Transform your dining experience with",
        "features_intro": "Elegant design meets everyday functionality"
    },
    "Knives, Cutlery": {
        "lifestyle_weight": 30,
        "technical_weight": 70,
        "intro": "Professional-grade cutlery for discerning cooks",
        "features_intro": "Precision-forged with superior craftsmanship"
    },
    "Food Prep & Tools": {
        "lifestyle_weight": 60,
        "technical_weight": 40,
        "intro": "Make food preparation effortless with",
        "features_intro": "Thoughtfully designed kitchen essentials"
    },
}

# Per-category spec allow-list
ALLOWED_SPECS_BY_CATEGORY = {
    "Knives, Cutlery": {"material", "bladeLength", "dimensions", "weight", "origin", "guarantee", "care"},
    "Electricals": {"capacity", "dimensions", "weight", "powerW", "programs", "origin", "guarantee", "care"},
    "Dining, Drink, Living": {"material", "capacity", "dimensions", "weight", "origin", "guarantee", "care"},
    "Bakeware, Cookware": {"material", "dimensions", "weight", "capacity", "origin", "guarantee", "care"},
    "Food Prep & Tools": {"material", "dimensions", "weight", "origin", "guarantee", "care"},
    "Clothing": {"material", "dimensions", "weight", "origin", "care"},
    "General": {"material", "dimensions", "weight", "capacity", "origin", "guarantee", "care"}
}

BANNED_KEYWORDS = {
    "shop", "shops", "shopping", "product", "products", "buy", "order", "orders",
    "price", "prices", "sale", "deals", "delivery", "ship", "shipping", "range",
    "style", "styles", "often", "comparable", "organic", "discover", "quality",
    "featuring", "feature", "features", "place", "mats", "unknown", "every"
}

SYSTEM_PROMPT = """
Act like a senior UK e-commerce copy chief and prompt engineer. You specialise in turning product data into warm, trustworthy, benefit-led copy that helps shoppers choose with confidence. Produce compliant, high-quality HTML only.

OBJECTIVE
Return valid JSON with exactly two keys (no markdown, no comments):
{ "short_html": "<p>…</p>", "long_html": "<p>…</p><p>…</p>…" }

TONE & PRINCIPLES
• UK English only.
• Warm, knowledgeable, practical; benefit-first; transparent and reassuring.
• The business is a retailer/redistributor, not a manufacturer.
• Do NOT mention retailer location, "Dorset", "family-run", "Since 1919", or any in-house manufacturing.
• Truthful and product-data-grounded. Never invent specifications or claims.
• No em dashes.

INPUTS
You will receive one message with product JSON prefixed by "Product data:". Treat that JSON as the only source of truth.
It may include: name, brand, category, sku, range/collection, colour/pattern, style/finish, features[], benefits[], specifications{ material, dimensions, capacity, weight, programs/settings, powerW }, origin/madeIn, guarantee/warranty, isNonStick (boolean), care, usage, audience.

GUARDRAILS
• Output strictly valid JSON with only "short_html" and "long_html".
• Never include emojis, ALL CAPS hype, or retail terms (shop, buy, order, price, delivery, shipping).
• Do not echo placeholders, empty tags, or unknown values. If a spec is missing, omit that line entirely.
• Key features must not be repeated.
• Character limits (including HTML tags):
  – short_html: ≤150 characters
  – long_html: ≤2000 characters
• Use concise, plain language. UK spelling.

CATEGORY MATRIX (use provided product.category; if absent, use General)
Clothing — Lifestyle 100 : Technical 0 | Short bullets: material; fit/style; colour/pattern
Electricals — Lifestyle 0 : Technical 100 | Short bullets: three main product features
Bakeware, Cookware — Lifestyle 50 : Technical 50 | Short bullets: usage; coating/finish; one standout feature
Dining, Drink, Living — Lifestyle 80 : Technical 20 | Short bullets: material; style/finish; dimensions or capacity
Knives, Cutlery — Lifestyle 30 : Technical 70 | Short bullets: material/steel; key feature; guarantee
Food Prep & Tools — Lifestyle 60 : Technical 40 | Short bullets: key feature; usage; material
General — Lifestyle 50 : Technical 50 | Short bullets: what it is; who it's for; core benefit

HTML & CONTENT RULES
A) short_html
• Exactly one <p>…</p> containing three bullet fragments separated by <br>.
• Each fragment 2–8 words; capitalised; no trailing full stops.

B) long_html (ordered <p> blocks)
1) Meta description — one sentence, 150–160 characters; include product name or purpose; approachable, benefit-led; no retail terms; no em dashes.
2) Lifestyle/benefit paragraph(s) per category ratio. Reframe features as outcomes.
3) Technical paragraph — concise, factual: material/coating, construction, compatibility/usage, range fit, care. Electricals only: include programs/settings and powerW if present; mention auto switch-off only if present.
4) Spec lines (separate <p> tags) only if data is present and allowed for the category:
   • <p>Capacity: {CAP}.</p>
   • <p>Dimensions: {H}(H) x {W}(W) x {D}(D) cm.</p>
   • <p>Weight: {KG}kg.</p>
   • <p>Made in UK.</p> only if origin confirms UK.
   • <p>{Guarantee sentence}</p>:
     – If isNonStick === true, "10-year guarantee."
     – Else if guarantee/warranty text is present, echo once with full stop.
     – Else omit this line.
5) Optional care/compatibility closer — one short line only if certain (e.g., "Dishwasher safe.", "Oven safe to 260°C."). Do not guess.

C) Normalisation & Safety checks
• Trim whitespace; ensure balanced, ordered <p> tags.
• If length issues arise, shorten lifestyle text first, never the meta.
• Remove duplicate facts and promotional fluff.
• No pricing, shipping, stock, or service language.
• Parent/child variants: keep copy generic unless sizes/colours are provided.

QUALITY BAR
• Clear what it is, why it helps, and key specs.
• Numbers/units formatted exactly as required.
• Tone: warm, factual, UK spelling, no hype.
• Retailer-neutral; no location or family references.
""".strip()


# =========================================
# HELPER FUNCTIONS
# =========================================

def clamp(text: str, max_length: int) -> str:
    """Truncate text to max length"""
    if not text or len(text) <= max_length:
        return text
    return text[:max_length].strip()


def normalise_category(cat: str, fallback: str = "General") -> str:
    """Normalise category to allowed values"""
    if not cat:
        return fallback
    
    c = str(cat).strip()
    if c in ALLOWED_CATEGORIES:
        return c
    
    # Tolerant synonyms
    synonyms = {
        "bakeware": "Bakeware, Cookware",
        "cookware": "Bakeware, Cookware",
        "dining": "Dining, Drink, Living",
        "drink": "Dining, Drink, Living",
        "living": "Dining, Drink, Living",
        "electrical": "Electricals",
        "food prep": "Food Prep & Tools",
        "tools": "Food Prep & Tools",
        "knives": "Knives, Cutlery",
        "cutlery": "Knives, Cutlery",
        "clothes": "Clothing"
    }
    
    key = c.lower()
    for k, v in synonyms.items():
        if k in key:
            return v
    
    return fallback


def spec_allowed(category: str, key: str) -> bool:
    """Check if spec is allowed for category"""
    allowed = ALLOWED_SPECS_BY_CATEGORY.get(category, ALLOWED_SPECS_BY_CATEGORY["General"])
    return key in allowed


def format_dimensions(raw: str) -> Optional[str]:
    """Format dimensions as H(H) x W(W) x D(D) cm."""
    if not raw:
        return None
    
    # Extract numbers
    nums = re.findall(r'\d+(?:\.\d+)?', str(raw))
    if len(nums) >= 3:
        return f"{nums[0]}(H) x {nums[1]}(W) x {nums[2]}(D) cm."
    return None


def format_capacity(raw: str) -> Optional[str]:
    """Normalize ml/litre capacity"""
    if not raw:
        return None
    
    s = str(raw).lower().strip()
    
    # Already formatted
    if re.search(r'\d+\s*ml\.?$', s):
        return s.rstrip('.') + '.'
    if re.search(r'\d+(\.\d+)?\s*l\.?$', s):
        return s.rstrip('.') + '.'
    
    # Just number, assume ml
    if re.match(r'^\d+(\.\d+)?$', s):
        return f"{s}ml."
    
    return s.rstrip('.') + '.'


def guarantee_for(item: Dict[str, Any]) -> Optional[str]:
    """Generate guarantee line"""
    if item.get("isNonStick") is True:
        return "10-year guarantee."
    
    g = item.get("guarantee") or item.get("warranty")
    if not g:
        return None
    
    s = str(g).strip()
    return s if s.endswith('.') else f"{s}."


def made_in_line(item: Dict[str, Any]) -> Optional[str]:
    """Detect UK origin"""
    origin = str(item.get("madeIn", "") or item.get("origin", "")).upper()
    
    uk_indicators = ["UK", "UNITED KINGDOM", "ENGLAND", "SCOTLAND", "WALES", "NORTHERN IRELAND"]
    if any(ind in origin for ind in uk_indicators):
        return "Made in UK."
    
    return None


def finish_meta_single_sentence(meta: str) -> str:
    """Ensure meta is a single sentence ending with period"""
    s = re.sub(r'\s+', ' ', (meta or '')).strip()
    
    # If already single sentence, return
    if re.search(r'\.\s*$', s) and not re.search(r'[.!?].+\.\s*$', s):
        return s
    
    # Trim trailing conjunctions
    s = re.sub(r'(?:\s+(?:and|or|with|including|for|to|that|which|are|is|was|were)\s*)+$', '', s, flags=re.IGNORECASE)
    s = re.sub(r'[–—-]\s*$', '', s)
    s = re.sub(r'[,:;]\s*$', '', s)
    
    if not s.endswith('.'):
        s = f"{s}."
    
    return s


def clean_meta_description(text: str, max_len: int = 160) -> str:
    """Clean and clamp meta description"""
    if not text:
        return ""
    
    s = re.sub(r'\s+', ' ', text).strip()
    
    if len(s) > max_len:
        s = s[:max_len]
        # Try to end at sentence
        last_dot = s.rfind('.')
        if last_dot > 0 and last_dot >= len(s) - 25:
            s = s[:last_dot + 1]
    
    # Capitalize first char, ensure single trailing period
    if s:
        s = s[0].upper() + s[1:]
    s = re.sub(r'[.!?]*\s*$', '.', s)
    
    return s.strip()


def weave_brand_once(meta: str, brand: str, product_name: str) -> str:
    """Inject brand name once into meta if not present"""
    if not brand:
        return meta
    
    b = str(brand).strip()
    if not b:
        return meta
    
    # Already contains brand
    if re.search(rf'\b{re.escape(b)}\b', meta, re.IGNORECASE):
        return meta
    
    # Try to insert after product name
    if product_name and re.search(re.escape(product_name), meta, re.IGNORECASE):
        return re.sub(
            re.escape(product_name),
            lambda m: f"{m.group(0)} by {b}",
            meta,
            count=1,
            flags=re.IGNORECASE
        )
    
    # Insert before first period
    match = re.search(r'\.', meta)
    if match:
        idx = match.start()
        return clean_meta_description(meta[:idx] + f" by {b}" + meta[idx:])
    
    return f"{meta.rstrip('.')} by {b}."


def smart_inject_keywords(meta: str, keywords: List[str], max_len: int = 160) -> str:
    """Inject keywords into meta description"""
    base = re.sub(r'[.!?]\s*$', '', meta.strip())
    
    # Get unique keywords
    unique_kws = []
    seen = set()
    for kw in (keywords or []):
        if kw and kw.lower() not in seen:
            unique_kws.append(kw)
            seen.add(kw.lower())
    
    miss = unique_kws[:2]
    if not miss:
        return clean_meta_description(base + ".", max_len)
    
    # Try adding both
    out = f"{base} with {miss[0]}"
    if len(miss) > 1:
        out += f" and {miss[1]}"
    out += "."
    
    # If too long, try just first keyword
    if len(out) > max_len:
        out = f"{base} with {miss[0]}."
    
    # If still too long, skip keywords
    if len(out) > max_len:
        out = base + "."
    
    return clean_meta_description(out, max_len)


def build_short_html(fragments: List[str], max_len: int = 150) -> str:
    """Build short HTML with 3 bullet points"""
    # Clean fragments
    tidy = []
    for s in fragments:
        if not s:
            continue
        s = re.sub(r'[.]+$', '', str(s)).strip()
        s = ' '.join(s.split()[:8])  # Max 8 words
        if s:
            s = s[0].upper() + s[1:] if len(s) > 1 else s.upper()
            tidy.append(s)
    
    # Ensure 3 fragments
    while len(tidy) < 3:
        tidy.append("More details")
    
    result = f"<p>{tidy[0]}<br>{tidy[1]}<br>{tidy[2]}</p>"
    
    # Trim last fragment if too long
    words = tidy[2].split()
    while len(result) > max_len and len(words) > 2:
        words.pop()
        tidy[2] = ' '.join(words)
        result = f"<p>{tidy[0]}<br>{tidy[1]}<br>{tidy[2]}</p>"
    
    return clamp(result, max_len)


def coerce_short_html(short_html: str, category: str) -> str:
    """Validate and coerce short HTML"""
    text = (short_html or '').strip()
    
    # Check structure
    ok_structure = (
        text.startswith('<p>') and 
        text.endswith('</p>') and 
        text.count('<br>') >= 2
    )
    len_ok = len(text) <= 150
    
    if ok_structure and len_ok:
        return text
    
    # Rebuild from scratch
    plain = re.sub(r'<\/?p>', '', text)
    plain = re.sub(r'<br\s*\/?>', ' • ', plain)
    plain = re.sub(r'\s+', ' ', plain).strip()
    
    pool = [s.strip() for s in plain.split('•') if s.strip()]
    
    defaults = ["Clear benefit", "Key feature", "Everyday use"]
    frags = pool[:3] if len(pool) >= 3 else defaults
    
    return build_short_html(frags, 150)


def coerce_long_html(long_html: str, product_name: str, category: str) -> str:
    """Validate and coerce long HTML"""
    html = (long_html or '').strip()
    
    if not html:
        meta = clean_meta_description(
            finish_meta_single_sentence(f"The {product_name} provides reliable performance for everyday use."),
            160
        )
        return f"<p>{meta}</p><p>{product_name} is designed for everyday use with clear, accurate details to help you choose with confidence.</p>"
    
    # Ensure first paragraph is single-sentence meta
    p_match = re.search(r'<p>(.*?)<\/p>', html)
    meta = p_match.group(1) if p_match else ""
    meta = clean_meta_description(
        finish_meta_single_sentence(meta or f"The {product_name} provides reliable performance for everyday use."),
        160
    )
    
    html = re.sub(r'<p>.*?<\/p>', f'<p>{meta}</p>', html, count=1)
    
    # Strip banned retail terms from meta only
    banned_pattern = r'\b(shop|buy|order|price|delivery|shipping)\b'
    html = re.sub(
        r'^<p>[\s\S]*?<\/p>',
        lambda m: re.sub(banned_pattern, '', m.group(0), flags=re.IGNORECASE).replace('  ', ' ').replace(' .', '.'),
        html
    )
    
    return clamp(html, 2000)


def parse_json_from_model(content: str) -> Dict[str, Any]:
    """Extract JSON from model response, handling code fences"""
    body = (content or '').strip()
    
    # Handle ```json ... ``` or ``` ... ``` fences
    fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', body, re.IGNORECASE)
    if fence_match:
        body = fence_match.group(1).strip()
    
    return json.loads(body)


# =========================================
# OPENAI GENERATION
# =========================================

async def generate_with_openai(product: Dict[str, Any], category: str, serp_keywords: List[str] = None, serp_meta_seed: str = "") -> Optional[Dict[str, str]]:
    """Generate descriptions using OpenAI GPT-4"""
    if not openai_client:
        logger.warning("OpenAI client not initialized")
        return None
    
    try:
        product_name = product.get("name", "product")
        
        # Build SERP hints if provided
        serp_hints = ""
        if serp_keywords or serp_meta_seed:
            serp_hints = f"\nSERP_HINTS:\n{json.dumps({'keywords': serp_keywords or [], 'meta_seed': serp_meta_seed or ''})}"
        
        user_content = f"Product data:\n{json.dumps(product, indent=2)}{serp_hints}"
        
        logger.info(f"Generating brand voice for: {product_name}")
        
        response = openai_client.chat.completions.create(
            model="gpt-4",  # Use gpt-4 (gpt-4.1 not available in standard API)
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            max_tokens=1200,
            temperature=0.4
        )
        
        content = response.choices[0].message.content
        if not content:
            return None
        
        # Parse JSON
        try:
            parsed = parse_json_from_model(content)
            return {
                "short_html": parsed.get("short_html", ""),
                "long_html": parsed.get("long_html", "")
            }
        except Exception as e:
            logger.warning(f"Failed to parse OpenAI response: {e}")
            return None
    
    except Exception as e:
        logger.error(f"OpenAI generation failed: {e}")
        return None


# =========================================
# FALLBACK GENERATION
# =========================================

def generate_fallback_descriptions(product: Dict[str, Any], category: str) -> Dict[str, str]:
    """Generate template-based descriptions as fallback"""
    product_name = product.get("name", "Product")
    brand = product.get("brand", "")
    specs = product.get("specifications", {})
    
    # Build short HTML fragments based on category
    frags = []
    
    if category == "Knives, Cutlery":
        if specs.get("material"):
            frags.append(str(specs["material"]))
        if re.search(r'\b\d{2}\s?cm\b', product_name, re.IGNORECASE):
            match = re.search(r'\b(\d{2}\s?cm)\b', product_name, re.IGNORECASE)
            if match:
                frags.append(f"{match.group(1)} blade")
        if product.get("guarantee") or product.get("warranty"):
            frags.append("Includes guarantee")
    
    elif category == "Electricals":
        if specs.get("powerW"):
            frags.append(f"{specs['powerW']}W power")
        if specs.get("capacity"):
            frags.append(f"{specs['capacity']} capacity")
        frags.append("Core features")
    
    elif category == "Dining, Drink, Living":
        if specs.get("material"):
            frags.append(str(specs["material"]))
        if specs.get("capacity"):
            cap = format_capacity(specs["capacity"])
            if cap:
                frags.append(cap.rstrip('.'))
        frags.append("Everyday use")
    
    else:
        if specs.get("material"):
            frags.append(str(specs["material"]))
        frags.append("Everyday use")
        frags.append("Practical details")
    
    short_html = build_short_html(frags[:3])
    
    # Build long HTML
    meta = f"The {product_name} provides reliable performance for everyday use."
    meta = finish_meta_single_sentence(meta)
    meta = clean_meta_description(meta, 160)
    
    # Technical spec lines
    tech_specs = []
    
    if spec_allowed(category, "weight") and specs.get("weight"):
        tech_specs.append(f"<p>Weight: {specs['weight']}.</p>")
    
    if spec_allowed(category, "capacity") and specs.get("capacity"):
        cap = format_capacity(specs["capacity"])
        if cap:
            tech_specs.append(f"<p>Capacity: {cap}</p>")
    
    if spec_allowed(category, "dimensions") and specs.get("dimensions"):
        dims = format_dimensions(specs["dimensions"])
        if dims:
            tech_specs.append(f"<p>Dimensions: {dims}</p>")
    
    if spec_allowed(category, "powerW") and specs.get("powerW"):
        tech_specs.append(f"<p>Power: {specs['powerW']}W.</p>")
    
    made_in = made_in_line(product)
    if spec_allowed(category, "origin") and made_in:
        tech_specs.append(f"<p>{made_in}</p>")
    
    guarantee = guarantee_for(product)
    if spec_allowed(category, "guarantee") and guarantee:
        tech_specs.append(f"<p>{guarantee}</p>")
    
    if spec_allowed(category, "care") and product.get("care"):
        care_line = str(product["care"]).strip()
        if care_line:
            tech_specs.append(f"<p>{care_line}</p>")
    
    long_html = (
        f"<p>{meta}</p>"
        f"<p>{product_name} is designed for everyday use with clear, accurate details to help you choose with confidence.</p>"
        + "".join(tech_specs)
    )
    
    return {
        "short_html": short_html,
        "long_html": clamp(long_html, 2000)
    }


# =========================================
# MAIN ENDPOINT
# =========================================

@router.post("/generate-brand-voice", response_model=BrandVoiceResponse)
async def generate_brand_voice(request: BrandVoiceRequest):
    """
    Generate Harts of Stur branded product descriptions

    Latest version with:
    - SEO keyword optimization
    - Per-category spec filtering
    - UK English, retailer-neutral tone
    - No heritage mentions ("Since 1919", etc.)
    - Smart meta description optimization
    
    Accepts either:
    - Array of products in `products` field
    - Single product in `productData` field with `category`

    Returns: Products with generated descriptions (metaDescription, shortDescription, longDescription)
    """
    logger.info("Generating brand voice descriptions")
    
    try:
        # Determine products to process
        products_to_process = []
        
        if request.products:
            products_to_process = request.products
            logger.info(f"Processing {len(request.products)} products")
        elif request.productData:
            products_to_process = [request.productData]
            logger.info(f"Processing single product: {request.productData.get('name', 'Unknown')}")
        else:
            raise HTTPException(status_code=400, detail="No products provided")
        
        # Normalize categories
        top_cat = normalise_category(request.category or "General", "General")
        products_to_process = [
            {**p, "category": normalise_category(p.get("category"), top_cat)}
            for p in products_to_process
        ]
        
        processed_products = []
        
        for idx, product in enumerate(products_to_process):
            try:
                product_name = product.get("name", "product")
                product_category = normalise_category(product.get("category"), top_cat)
                
                logger.info(f"Product {idx + 1}: {product_name} (Category: {product_category})")
                
                # Get SERP keywords if available (simplified - no external call for now)
                serp_keywords = product.get("serp_keywords", [])
                serp_meta_seed = product.get("serp_meta_seed", "")
                
                # Try OpenAI first
                descriptions = await generate_with_openai(product, product_category, serp_keywords, serp_meta_seed)
                
                # Fallback if OpenAI fails
                if not descriptions or not descriptions.get("short_html") or not descriptions.get("long_html"):
                    logger.info(f"Using fallback generation for product {idx + 1}")
                    descriptions = generate_fallback_descriptions(product, product_category)
                
                # Validate and coerce
                short_html = coerce_short_html(descriptions.get("short_html", ""), product_category)
                long_html = coerce_long_html(descriptions.get("long_html", ""), product_name, product_category)
                
                # Extract meta from first paragraph
                meta_match = re.search(r'<p>(.*?)<\/p>', long_html)
                meta_description = meta_match.group(1) if meta_match else f"The {product_name} is designed for everyday home use."
                meta_description = finish_meta_single_sentence(meta_description)
                meta_description = clean_meta_description(meta_description, 160)
                
                # Build processed product
                product_id = product.get("id") or generate_product_id()
                
                processed = ProcessedProduct(
                    id=product_id,
                    sku=product.get("sku", ""),
                    barcode=product.get("barcode", ""),
                    name=product_name,
                    brand=product.get("brand", "Unknown"),
                    category=product_category,
                    specifications=product.get("specifications", {}),
                    features=product.get("features", []),
                    descriptions=BrandVoiceDescriptions(
                        metaDescription=clamp(meta_description, 160),
                        shortDescription=clamp(short_html, 150),
                        longDescription=clamp(long_html, 2000)
                    ),
                    weight_grams=product.get("weight_grams"),
                    weight_human=product.get("weight_human", "")
                )
                
                processed_products.append(processed)
                logger.info(f"Successfully processed: {product_name}")
            
            except Exception as product_error:
                logger.error(f"Error processing product {product.get('name', 'unknown')}: {product_error}")
                # Continue with error placeholder
                processed_products.append(ProcessedProduct(
                    id=f"product-error-{int(time.time())}",
                    name=product.get("name", "Unknown Product"),
                    brand=product.get("brand", ""),
                    category=normalise_category(product.get("category"), "General"),
                    sku=product.get("sku", ""),
                    specifications=product.get("specifications", {}),
                    features=[],
                    descriptions=BrandVoiceDescriptions(
                        metaDescription="Product description generation failed.",
                        shortDescription="<p>Processing error occurred</p>",
                        longDescription="<p>Product description generation failed.</p>"
                    )
                ))
        
        logger.info(f"Successfully generated descriptions for {len(processed_products)} products")
        
        return BrandVoiceResponse(
            success=True,
            products=processed_products
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Brand voice generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Brand voice generation failed: {str(e)}")
