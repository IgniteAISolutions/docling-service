"""
Brand Voice Generation Service
OpenAI GPT-4o-mini with retry logic and full Supabase prompt parity
"""
import os
import json
import logging
import asyncio
import re
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI, APIError, OpenAIError

from ..config import (
    OPENAI_MODEL,
    OPENAI_MAX_RETRIES,
    OPENAI_TIMEOUT,
    SYSTEM_PROMPT,
    ALLOWED_SPECS
)
from ..utils.sanitizers import strip_forbidden_phrases, sanitize_html

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client: Optional[AsyncOpenAI] = None


def initialize_client():
    """Initialize OpenAI client with API key"""
    global client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY not set - brand voice generation will fail")
        return False
    client = AsyncOpenAI(api_key=api_key)
    return True


async def generate(products: List[Dict[str, Any]], category: str) -> List[Dict[str, Any]]:
    """
    Generate brand voice descriptions for products with retry logic
    Args:
        products: List of normalized product dicts
        category: Product category
    Returns:
        List of products with enhanced descriptions
    """
    # Ensure client is initialized
    if client is None:
        initialize_client()

    enhanced_products = []

    for idx, product in enumerate(products):
        try:
            logger.info(f"Processing product {idx + 1}/{len(products)}: {product.get('name', 'Unknown')}")
            enhanced = await generate_single_product(product, category)
            enhanced_products.append(enhanced)
        except Exception as e:
            logger.error(f"Failed to process {product.get('name', 'Unknown')}: {e}")
            # Return product with error marker
            product["descriptions"] = {
                "shortDescription": "<p>Processing error</p>",
                "metaDescription": "Product description generation failed.",
                "longDescription": "<p>Unable to generate description.</p>"
            }
            product["_generation_error"] = str(e)
            enhanced_products.append(product)

    return enhanced_products


async def generate_single_product(product: Dict[str, Any], category: str) -> Dict[str, Any]:
    """
    Generate description for single product with 3 retries
    Args:
        product: Normalized product dict
        category: Product category
    Returns:
        Product with descriptions added
    Raises:
        Exception: After 3 failed retries
    """
    if client is None:
        raise Exception("OpenAI client not initialized - check OPENAI_API_KEY")

    # Filter specs to only allowed ones for this category
    filtered_specs = filter_specifications(product.get("specifications", {}), category)
    product["specifications"] = filtered_specs

    # Build prompt
    prompt = build_prompt(product, category)

    # Try OpenAI with retries
    last_error = None
    for attempt in range(1, OPENAI_MAX_RETRIES + 1):
        try:
            logger.debug(f"OpenAI attempt {attempt}/{OPENAI_MAX_RETRIES} for {product.get('name')}")

    response = await client.chat.completions.create(
        model=OPENAI_MODEL,  # ← Uses the env var
        messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
                ],
                temperature=0.4,
                max_tokens=1200,
                timeout=float(OPENAI_TIMEOUT)
            )

            content = response.choices[0].message.content

            if not content:
                raise Exception("OpenAI returned empty response")

            # Parse response
            descriptions = parse_openai_response(content)

            # Sanitize output
            descriptions = sanitize_descriptions(descriptions, product.get("name", ""))

            # Update product
            product["descriptions"] = descriptions
            logger.info(f"Successfully generated descriptions for {product.get('name')}")
            return product

        except OpenAIError as e:
            last_error = e
            logger.warning(f"OpenAI attempt {attempt}/{OPENAI_MAX_RETRIES} failed: {e}")

            if attempt < OPENAI_MAX_RETRIES:
                # Exponential backoff
                wait_time = 2 ** attempt
                logger.info(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)
            else:
                # Final attempt failed
                raise Exception(f"OpenAI failed after {OPENAI_MAX_RETRIES} retries: {last_error}")

        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error in attempt {attempt}: {e}")

            if attempt < OPENAI_MAX_RETRIES:
                wait_time = 2 ** attempt
                await asyncio.sleep(wait_time)
            else:
                raise Exception(f"Generation failed after {OPENAI_MAX_RETRIES} retries: {last_error}")

    # Should not reach here, but just in case
    raise Exception(f"Generation failed: {last_error}")


def filter_specifications(specs: Dict[str, Any], category: str) -> Dict[str, Any]:
    """
    Filter specs to only allowed keys for category
    Args:
        specs: Product specifications dict
        category: Product category
    Returns:
        Filtered specifications dict
    """
    # Get allowed specs for this category (with fallback to General)
    allowed = ALLOWED_SPECS.get(category, ALLOWED_SPECS.get("General", set()))

    # Filter to only allowed specs
    filtered = {k: v for k, v in specs.items() if k in allowed}

    logger.debug(f"Filtered specs for {category}: kept {len(filtered)}/{len(specs)} specs")

    return filtered


def build_prompt(product: Dict[str, Any], category: str) -> str:
    """
    Build OpenAI prompt from product data
    Args:
        product: Product dict
        category: Product category
    Returns:
        Formatted prompt string
    """
    # Create clean product data for prompt
    prompt_data = {
        "name": product.get("name", ""),
        "category": category,
    }

    # Add optional fields if present
    optional_fields = [
        "sku", "brand", "range", "collection", "colour", "pattern",
        "style", "finish", "usage", "audience"
    ]

    for field in optional_fields:
        if product.get(field):
            prompt_data[field] = product[field]

    # Add lists if present
    if product.get("features"):
        prompt_data["features"] = product["features"]

    if product.get("benefits"):
        prompt_data["benefits"] = product["benefits"]

    # Add specifications (already filtered)
    if product.get("specifications"):
        prompt_data["specifications"] = product["specifications"]

    # Add special flags
    if product.get("isNonStick"):
        prompt_data["isNonStick"] = True

    # Build prompt
    return f"Product data:\n{json.dumps(prompt_data, indent=2)}"


def parse_openai_response(content: str) -> Dict[str, str]:
    """
    Parse OpenAI JSON response, handling markdown fences
    Args:
        content: Raw OpenAI response content
    Returns:
        Dict with shortDescription, metaDescription, longDescription
    Raises:
        Exception: If parsing fails
    """
    try:
        # Strip markdown code blocks
        content = content.strip()

        # Remove markdown json fences if present
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]

        if content.endswith("```"):
            content = content[:-3]

        content = content.strip()

        # Parse JSON
        data = json.loads(content)

        # Extract descriptions
        short_html = data.get("short_html", "")
        long_html = data.get("long_html", "")

        if not short_html or not long_html:
            raise Exception("Missing short_html or long_html in response")

        # Extract meta description from first paragraph of long_html
        meta = extract_meta_from_long_html(long_html)

        return {
            "shortDescription": short_html,
            "metaDescription": meta,
            "longDescription": long_html
        }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OpenAI JSON: {e}\nContent: {content}")
        raise Exception(f"Invalid JSON from OpenAI: {e}")

    except Exception as e:
        logger.error(f"Failed to parse OpenAI response: {e}")
        raise


def extract_meta_from_long_html(long_html: str) -> str:
    """
    Extract first paragraph as meta description
    Args:
        long_html: Long description HTML
    Returns:
        Meta description string (150-160 chars)
    """
    # Extract first <p> tag content
    match = re.search(r'<p>(.*?)</p>', long_html, re.DOTALL)

    if match:
        meta = match.group(1).strip()

        # Remove any inner HTML tags
        meta = re.sub(r'<[^>]+>', '', meta)

        # Clamp to 160 chars
        if len(meta) > 160:
            # Try to cut at sentence boundary
            if '.' in meta[:160]:
                last_period = meta[:160].rfind('.')
                meta = meta[:last_period + 1]
            else:
                meta = meta[:157] + "..."

        return meta

    # Fallback: extract plain text from start
    plain = re.sub(r'<[^>]+>', '', long_html)
    plain = plain.strip()

    if len(plain) > 160:
        plain = plain[:157] + "..."

    return plain


def sanitize_descriptions(descriptions: Dict[str, str], product_name: str) -> Dict[str, str]:
    """
    Remove forbidden phrases and validate
    Args:
        descriptions: Dict with description fields
        product_name: Product name for logging
    Returns:
        Sanitized descriptions dict
    """
    for key in ["shortDescription", "metaDescription", "longDescription"]:
        if key in descriptions:
            # Strip forbidden phrases
            descriptions[key] = strip_forbidden_phrases(descriptions[key])

            # Sanitize HTML
            descriptions[key] = sanitize_html(descriptions[key])

    # Validate lengths
    if len(descriptions.get("shortDescription", "")) > 150:
        logger.warning(f"Short description too long for {product_name}: {len(descriptions['shortDescription'])} chars")

    if len(descriptions.get("longDescription", "")) > 2000:
        logger.warning(f"Long description too long for {product_name}: {len(descriptions['longDescription'])} chars")

    return descriptions


# Initialize client on module import
initialize_client()
