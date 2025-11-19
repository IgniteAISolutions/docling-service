"""
Configuration, constants, and category-specific rules
Ported from Supabase TypeScript
"""

# OpenAI Configuration
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_MAX_RETRIES = 3
OPENAI_TIMEOUT = 120

# Categories
ALLOWED_CATEGORIES = {
    "Bakeware, Cookware",
    "Dining, Drink, Living",
    "Electricals",
    "Food Prep & Tools",
    "Knives, Cutlery",
    "Clothing",
    "Seasonal"
}

# Category-specific lifestyle:technical ratios
CATEGORY_MATRIX = {
    "Clothing": {"lifestyle": 100, "technical": 0},
    "Electricals": {"lifestyle": 0, "technical": 100},
    "Bakeware, Cookware": {"lifestyle": 50, "technical": 50},
    "Dining, Drink, Living": {"lifestyle": 80, "technical": 20},
    "Knives, Cutlery": {"lifestyle": 30, "technical": 70},
    "Food Prep & Tools": {"lifestyle": 60, "technical": 40},
    "Seasonal": {"lifestyle": 50, "technical": 50}
}

# Spec allow-lists per category
ALLOWED_SPECS = {
    "Knives, Cutlery": {"material", "bladeLength", "dimensions", "weight", "origin", "guarantee", "care"},
    "Electricals": {"capacity", "dimensions", "weight", "powerW", "programs", "origin", "guarantee", "care"},
    "Dining, Drink, Living": {"material", "capacity", "dimensions", "weight", "origin", "guarantee", "care"},
    "Bakeware, Cookware": {"material", "dimensions", "weight", "capacity", "origin", "guarantee", "care"},
    "Food Prep & Tools": {"material", "dimensions", "weight", "origin", "guarantee", "care"},
    "Clothing": {"material", "dimensions", "weight", "origin", "care"},
    "Seasonal": {"material", "dimensions", "weight", "capacity", "origin", "guarantee", "care"},
    "General": {"material", "dimensions", "weight", "capacity", "origin", "guarantee", "care"}  # Default fallback
}

# Forbidden phrases (must be stripped from all outputs)
FORBIDDEN_PHRASES = [
    "Harts of Stur",
    "Since 1919",
    "Since 1990",
    "Dorset",
    "family-run",
    "family run",
    "imported from"
]

# Banned SEO keywords
BANNED_SEO_KEYWORDS = {
    "shop", "shops", "shopping",
    "buy", "order", "orders", "price", "prices", "sale", "every"
}

# System prompt (EXACT port from Supabase)
SYSTEM_PROMPT = """Act like a senior UK e-commerce copy chief and prompt engineer. You specialise in turning product data into warm, trustworthy, benefit-led copy that helps shoppers choose with confidence. Produce compliant, high-quality HTML only.
OBJECTIVE
Return valid JSON with exactly two keys (no markdown, no comments):
{ "short_html": "<p>…</p>", "long_html": "<p>…</p><p>…</p>…" }
TONE & PRINCIPLES
- UK English only.
- Warm, knowledgeable, practical; benefit-first; transparent and reassuring.
- The business is a retailer/redistributor, not a manufacturer.
- Do NOT mention retailer location, "Dorset", "family-run", "Since 1919", or any in-house manufacturing.
- Truthful and product-data-grounded. Never invent specifications or claims.
- No em dashes.
INPUTS
You will receive one message with product JSON prefixed by "Product data:". Treat that JSON as the only source of truth.
It may include: name, brand, category, sku, range/collection, colour/pattern, style/finish, features[], benefits[], specifications{ material, dimensions, capacity, weightKg, programs/settings, powerW }, origin/madeIn, guarantee/warranty, isNonStick (boolean), care, usage, audience.
GUARDRAILS
- Output strictly valid JSON with only "short_html" and "long_html".
- Never include emojis, ALL CAPS hype, or retail terms (shop, buy, order, price, delivery, shipping).
- Do not echo placeholders, empty tags, or unknown values. If a spec is missing, omit that line entirely.
- Key features must not be repeated.
- Character limits (including HTML tags):
  – short_html: ≤150 characters
  – long_html: ≤2000 characters
- Use concise, plain language. UK spelling.
CATEGORY MATRIX (use provided product.category;
Clothing — Lifestyle 100 : Technical 0 | Short bullets: material; fit/style; colour/pattern
Electricals — Lifestyle 0 : Technical 100 | Short bullets: three main product features
Bakeware, Cookware — Lifestyle 50 : Technical 50 | Short bullets: usage; coating/finish; one standout feature
Dining, Drink, Living — Lifestyle 80 : Technical 20 | Short bullets: material; style/finish; dimensions or capacity
Knives, Cutlery — Lifestyle 30 : Technical 70 | Short bullets: material/steel; key feature; guarantee
Food Prep & Tools — Lifestyle 60 : Technical 40 | Short bullets: key feature; usage; material
Seasonal — Lifestyle 50 : Technical 50 | Short bullets: what it is, festive theme; who it's for; core season, Christmas, halloween
HTML & CONTENT RULES
A) short_html
- Exactly one <p>…</p> containing three bullet fragments separated by <br>.
- Each fragment 2–8 words; capitalised; no trailing full stops.
B) long_html (ordered <p> blocks)
1) Meta description — one sentence, 150–160 characters; include product name or purpose; approachable, benefit-led; no retail terms; no em dashes.
2) Lifestyle/benefit paragraph(s) per category ratio. Reframe features as outcomes.
3) Technical paragraph — concise, factual: material/coating, construction, compatibility/usage, range fit, care. Electricals only: include programs/settings and powerW if present; mention auto switch-off only if present. Include a more detailed brief if possible with technical specifications being essential,
Example of a Coffee Machine (Electricals) output: Discover the new L'OR Barista Sublime coffee machine with volume personalisation. Brew two single espressos at once or a double espresso in one cup with the exclusive L'OR barista double shot system. Up to 19 bars of pressure for perfect espresso.
L'OR Barista coffee machine is designed to work with the exclusive L'OR Barista double shot capsules and L'OR Espresso single shot capsules.
Enjoy ristretto for two or double espresso just for you.
Savour the taste of true espresso. L'OR Barista System brews coffee at high pressure to ensure true espresso quality.
•	Can be used with coffee pods only.
•	Coffee options include: ristretto, lungo, and Espresso.
•	No hot water option.
•	No hot chocolate option.
•	Compatible with Nespresso Original Capsules.
•	Recyclable pods.
•	19 bar pump pressure.
•	Water capacity 0.8 litre.
•	Transparent removable water tank.
•	Adjustable cup stand for any size mug.
•	Maximum Cup Stand Dimensions 10 (cm).
•	Removable drip tray.
•	Auto shut-off after 1 minute.
•	Descale warning feature.
•	Manual cleaning & descaling.
•	Dishwasher safe parts for effortless cleaning.
•	Box contents: Coffee Machine.
General information
•	Model number: LM9012/60.
•	Size H27.6, W15.7, D40.2cm.
•	Power output 1450 watts.
•	Manufacturer's 2 year guarantee.
•	EAN: 8720389016646.
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
- Trim whitespace; ensure balanced, ordered <p> tags.
- If length issues arise, shorten lifestyle text first, never the meta.
- Remove duplicate facts and promotional fluff.
- No pricing, shipping, stock, or service language.
- Parent/child variants: keep copy generic unless sizes/colours are provided.
QUALITY BAR
- Clear what it is, why it helps, and key specs.
- Numbers/units formatted exactly as required.
- Tone: warm, factual, UK spelling, no hype.
- Retailer-neutral; no location or family references.
"""

<<<<<<< HEAD
config = Config()

# Product categories
ALLOWED_CATEGORIES = {
    'Clothing',
    'Electricals',
    'Bakeware, Cookware',
    'Dining, Drink, Living',
    'Knives, Cutlery',
    'Food Prep & Tools'
}
=======
# SEO Configuration
SEO_META_MIN_LENGTH = 150
SEO_META_MAX_LENGTH = 160
SEO_META_IDEAL_LENGTH = 155

# CSV Export Configuration
CSV_BOM = "\ufeff"
CSV_DEFAULT_HEADERS = [
    "sku", "barcode", "name",
    "shortDescription", "longDescription", "metaDescription",
    "weightGrams", "weightHuman"
]

# Image Processing
MAX_IMAGE_SIZE_MB = 10
SUPPORTED_IMAGE_FORMATS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

# URL Scraping
URL_SCRAPE_TIMEOUT = 30
URL_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Text Processing
TEXT_MIN_LENGTH = 10
TEXT_MAX_LENGTH = 10000
>>>>>>> 4bb5e0a365344f8e9c6e11a885d4182157a1eec0
