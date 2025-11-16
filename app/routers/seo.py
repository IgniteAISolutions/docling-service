"""
SEO Keywords Router
Generate SEO-optimized meta descriptions using search intent analysis
"""
import logging
import os
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI

from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["SEO"])

# Initialize OpenAI client
openai_client = None
if os.getenv("OPENAI_API_KEY"):
    openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class SEOKeywordsRequest(BaseModel):
    """Request for SEO keywords"""
    query: str
    brand: str = "Harts of Stur"
    market: str = "en-GB"
    maxKeywords: int = 6


class SEOKeywordsResponse(BaseModel):
    """Response from SEO keywords"""
    success: bool
    keywords: list[str] = []
    meta: dict = {}


async def generate_seo_meta(query: str, brand: str, market: str) -> Optional[dict]:
    """
    Generate SEO-optimized meta description using OpenAI
    """
    if not openai_client:
        logger.warning("OpenAI client not initialized")
        return None

    try:
        logger.info(f"Generating SEO meta for: {query}")

        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are an SEO expert for {brand}, a premium British homeware retailer.

Market: {market}
Task: Generate SEO-optimized content for search intent.

Guidelines:
- Focus on search intent and user queries
- Include relevant keywords naturally
- Meta description: 150-160 characters
- Include brand name
- Focus on benefits and features
- Use British English spelling"""
                },
                {
                    "role": "user",
                    "content": f"""Generate SEO-optimized meta description for:

Query: {query}
Brand: {brand}

Return JSON in this format:
{{
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6"],
  "description": "150-160 character meta description optimized for search"
}}"""
                }
            ],
            max_tokens=500,
            temperature=0.3
        )

        content = response.choices[0].message.content

        if not content:
            return None

        # Parse JSON response
        import json
        import re

        # Clean markdown code blocks
        clean_content = content.strip()
        clean_content = re.sub(r'^```json\s*', '', clean_content)
        clean_content = re.sub(r'^```\s*', '', clean_content)
        clean_content = re.sub(r'\s*```$', '', clean_content)

        # Extract JSON
        json_match = re.search(r'\{[\s\S]*\}', clean_content)
        if json_match:
            json_str = json_match.group(0)
            result = json.loads(json_str)

            return {
                "keywords": result.get("keywords", [])[:6],
                "description": result.get("description", "")[:160]
            }

    except Exception as e:
        logger.error(f"SEO generation failed: {e}")

    return None


@router.post("/seo-keywords", response_model=SEOKeywordsResponse)
async def seo_keywords(request: SEOKeywordsRequest):
    """
    Generate SEO keywords and meta description

    Uses AI to analyze search intent and generate optimized content.

    Returns:
    - keywords: Array of relevant search keywords
    - meta.description: SEO-optimized meta description (150-160 chars)
    """
    query = request.query.strip()

    if not query:
        raise HTTPException(status_code=400, detail="Query is required")

    logger.info(f"SEO keywords request for: {query}")

    try:
        # Generate SEO content
        result = await generate_seo_meta(query, request.brand, request.market)

        if not result:
            # Fallback
            return SEOKeywordsResponse(
                success=False,
                keywords=[],
                meta={}
            )

        logger.info(f"Generated {len(result.get('keywords', []))} keywords")

        return SEOKeywordsResponse(
            success=True,
            keywords=result.get("keywords", []),
            meta={
                "description": result.get("description", ""),
                "query": query,
                "brand": request.brand,
                "market": request.market
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"SEO keywords error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"SEO keywords generation failed: {str(e)}")
