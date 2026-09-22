"""Minimal Sarvam AI connection check.

Run from the backend directory with: python llm.py
"""

import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")

API_KEY = os.getenv("SARVAM_API_KEY")
ENDPOINT = "https://api.sarvam.ai/v1/chat/completions"


def main() -> int:
    if not API_KEY:
        print("SARVAM_API_KEY is missing. Add it to backend/.env.", file=sys.stderr)
        return 1

    payload = {
        "model": "sarvam-105b",
        "messages": [{"role": "user", "content": "What is AI?"}],
        "max_tokens": 200,
    }
    headers = {"api-subscription-key": API_KEY, "Content-Type": "application/json"}

    try:
        response = httpx.post(ENDPOINT, headers=headers, json=payload, timeout=30.0)
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as error:
        print(f"Sarvam API connection test failed: {error}", file=sys.stderr)
        return 1

    print(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
