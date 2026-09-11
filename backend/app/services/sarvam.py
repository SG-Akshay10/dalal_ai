from __future__ import annotations

import os
import json
import logging
import re
import httpx
from typing import Dict, Any, List, Type, TypeVar
from pydantic import BaseModel, ValidationError
from fastapi import HTTPException
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("sarvam_service")

SARVAM_API_KEY = os.getenv("SARVAM_API_KEY", "")
SARVAM_ENDPOINT = "https://api.sarvam.ai/v1/chat/completions"
MODEL_NAME = "sarvam-105b"
T = TypeVar("T", bound=BaseModel)


class SarvamStructuredOutputError(Exception):
    """Sarvam could not produce an output matching the requested schema."""

SYSTEM_PROMPT = """You are an expert Indian financial market news analyst.
Analyze the provided corporate filing or news item for a listed Indian company (NSE/BSE).
Classify its category, materiality score, directional sentiment, and write a concise 2-3 sentence max (30-50 words) plain-language summary of what happened and why it matters for stock investors.

CRITICAL INSTRUCTION: Respond ONLY with a single valid JSON object. Do NOT include any introductory text, reasoning monologue, chain-of-thought, or text outside the JSON.

Example output format:
{
  "category": "Quarterly Results",
  "materiality": "high",
  "sentiment": "positive",
  "summary": "Eternal Ltd reported a strong 45% YoY surge in Q1 net profit to Rs 850 crore. Operational margin expansion is likely to support positive stock price momentum."
}

Allowed Values:
- category: MUST be one of ["Quarterly Results", "Guidance Cut", "Regulatory/Legal", "Management Change", "Dividend/Bonus", "M&A", "Credit Rating", "Board Meeting", "General News"]
- materiality: MUST be one of ["high", "medium", "low"]
- sentiment: MUST be one of ["positive", "negative", "neutral", "unclear"]
- summary: MUST be a concise 2 to 3 sentence maximum summary explaining key facts and investor impact.
"""


def is_reasoning_monologue(text: str) -> bool:
    """Checks if text contains raw LLM chain-of-thought monologue or prompt echoes."""
    lowered = text.lower()
    patterns = [
        "the user wants",
        "let me parse",
        "detailed content:",
        "title/headline:",
        "company symbol:",
        "analyze the provided",
        "wait, this seems to be",
        "this is a live market report",
    ]
    return any(p in lowered for p in patterns)


def sanitize_summary(summary_text: str, title: str, symbol: str) -> str:
    """Sanitizes summary string to prevent internal reasoning leakages."""
    if not summary_text or is_reasoning_monologue(summary_text):
        return f"{title}. Market intelligence report concerning {symbol}."
    return summary_text.strip()


def classify_and_summarize(symbol: str, title: str, content: str = "") -> Dict[str, Any]:
    """
    Classifies filing/news item exclusively using Sarvam AI API (sarvam-105b).
    """
    api_key = os.getenv("SARVAM_API_KEY", "") or SARVAM_API_KEY
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail="SARVAM_API_KEY environment variable is not configured. Please set SARVAM_API_KEY in backend/.env to use Sarvam AI classification."
        )

    headers = {
        "api-subscription-key": api_key,
        "Content-Type": "application/json"
    }

    user_content = f"Company Symbol: {symbol}\nTitle/Headline: {title}\nDetailed Content: {content[:2000] if content else 'N/A'}"

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ],
        "max_tokens": 1024,
    }

    try:
        response = httpx.post(SARVAM_ENDPOINT, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise HTTPException(status_code=502, detail="Sarvam API returned empty choices.")

        message_obj = choices[0].get("message", {})
        content_raw = message_obj.get("content")

        if not content_raw:
            content_raw = message_obj.get("reasoning_content") or ""

        if not content_raw:
            logger.error(f"Sarvam API response message content is null/empty: {data}")
            raise HTTPException(
                status_code=502,
                detail="Sarvam AI response content was empty. Please check token budget or Sarvam API response structure."
            )

        clean_text = content_raw.replace("```json", "").replace("```", "").strip()

        parsed = None
        try:
            if "{" in clean_text and "}" in clean_text:
                start_idx = clean_text.find("{")
                end_idx = clean_text.rfind("}") + 1
                json_str = clean_text[start_idx:end_idx]
                parsed = json.loads(json_str)
            elif "{" in clean_text:
                start_idx = clean_text.find("{")
                decoder = json.JSONDecoder()
                parsed, _ = decoder.raw_decode(clean_text[start_idx:])
            else:
                parsed = json.loads(clean_text)
        except Exception:
            logger.warning("Sarvam returned non-JSON content; using neutral fallback.")
            return {
                "category": "General News",
                "materiality": "medium",
                "sentiment": "neutral",
                "summary": sanitize_summary("", title, symbol),
            }

        raw_summary = parsed.get("summary", "")
        final_summary = sanitize_summary(raw_summary, title, symbol)

        return {
            "category": parsed.get("category", "General News"),
            "materiality": str(parsed.get("materiality", "medium")).lower(),
            "sentiment": str(parsed.get("sentiment", "neutral")).lower(),
            "summary": final_summary
        }
    except Exception as e:
        logger.error(f"Sarvam API request failed: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=502,
            detail=f"Sarvam AI service error: {str(e)}"
        )


def summarize_portfolio_risk(stock_profiles: List[Dict[str, Any]], sector_profiles: List[Dict[str, Any]], diversification: Dict[str, Any]) -> str | None:
    """Return a concise portfolio-risk insight using the configured Sarvam client.

    The deterministic profiles remain the source of truth.  This optional
    enrichment deliberately returns ``None`` when Sarvam is unavailable so a
    missing API key or a transient LLM error never blocks analysis.
    """
    api_key = os.getenv("SARVAM_API_KEY", "") or SARVAM_API_KEY
    if not api_key:
        return None
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "You are an Indian portfolio risk analyst. Respond ONLY with JSON: {\"insight\": \"one concise, factual portfolio diversification observation\"}. Do not give buy/sell advice."},
            {"role": "user", "content": json.dumps({"stocks": stock_profiles, "sectors": sector_profiles, "diversification": diversification}, default=str)},
        ],
        "max_tokens": 250,
    }
    try:
        response = httpx.post(SARVAM_ENDPOINT, headers={"api-subscription-key": api_key, "Content-Type": "application/json"}, json=payload, timeout=30.0)
        response.raise_for_status()
        message = ((response.json().get("choices") or [{}])[0].get("message") or {})
        raw = message.get("content") or ""
        clean = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean[clean.find("{"):clean.rfind("}") + 1])
        insight = parsed.get("insight")
        return insight.strip() if isinstance(insight, str) and insight.strip() else None
    except Exception as exc:
        logger.warning("Sarvam portfolio insight unavailable: %s", exc)
        return None


def structured_completion(system_prompt: str, user_payload: Dict[str, Any], output_model: Type[T], correction: str | None = None, max_tokens: int = 1800) -> T:
    """Use the existing Sarvam HTTP client for Pydantic-validated JSON output."""
    api_key = os.getenv("SARVAM_API_KEY", "") or SARVAM_API_KEY
    if not api_key:
        raise SarvamStructuredOutputError("SARVAM_API_KEY is not configured")
    schema = output_model.model_json_schema()
    instructions = f"{system_prompt}\nReturn ONLY a valid JSON object matching this schema: {json.dumps(schema)}"
    if correction:
        instructions += f"\nCorrect the prior output using this validation feedback: {correction}"
    try:
        # The portfolio schemas are materially larger than news summaries and
        # sarvam-105b can take longer than one minute to return valid JSON.
        response = httpx.post(SARVAM_ENDPOINT, headers={"api-subscription-key": api_key, "Content-Type": "application/json"}, json={"model": MODEL_NAME, "messages": [{"role": "system", "content": instructions}, {"role": "user", "content": json.dumps(user_payload, default=str)}], "max_tokens": max_tokens}, timeout=180.0)
        response.raise_for_status()
        message = ((response.json().get("choices") or [{}])[0].get("message") or {})
        # Sarvam can return structured output in reasoning_content for some
        # models/request shapes; its news client already handles this form.
        raw = (message.get("content") or message.get("reasoning_content") or "").replace("```json", "").replace("```", "").strip()
        # Some model responses use the JSON-schema token `boolean` in place
        # of a value. If the caller supplied the concrete flag, safely repair
        # that one known placeholder before Pydantic validation.
        if "detailed_mode" in user_payload:
            raw = re.sub(r'("detailed_mode"\s*:\s*)boolean\b', rf'\1{str(bool(user_payload["detailed_mode"])).lower()}', raw)
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end < start:
            raise ValueError("response did not contain JSON")
        return output_model.model_validate_json(raw[start:end + 1])
    except (httpx.HTTPError, ValueError, ValidationError) as exc:
        raise SarvamStructuredOutputError(str(exc)) from exc


def text_completion(system_prompt: str, user_payload: Dict[str, Any], max_tokens: int = 2200) -> str:
    """Use the existing Sarvam client for narrative output when JSON is unreliable."""
    api_key = os.getenv("SARVAM_API_KEY", "") or SARVAM_API_KEY
    if not api_key:
        raise SarvamStructuredOutputError("SARVAM_API_KEY is not configured")
    try:
        response = httpx.post(SARVAM_ENDPOINT, headers={"api-subscription-key": api_key, "Content-Type": "application/json"}, json={"model": MODEL_NAME, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(user_payload, default=str)}], "max_tokens": max_tokens}, timeout=180.0)
        response.raise_for_status()
        message = ((response.json().get("choices") or [{}])[0].get("message") or {})
        text = (message.get("content") or message.get("reasoning_content") or "").strip()
        if not text:
            raise ValueError("Sarvam returned empty narrative")
        return text.replace("```", "").strip()
    except (httpx.HTTPError, ValueError) as exc:
        raise SarvamStructuredOutputError(str(exc)) from exc
