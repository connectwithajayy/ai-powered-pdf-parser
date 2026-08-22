#!/usr/bin/env python3
"""Extract structured invoice data from a PDF and write it as JSON.

Install:
    pip install pypdf

Usage:
    python pdf_to_json.py file/invoice.pdf --output invoice.json
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request

DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3.5-lightning:free"


def clean_extracted_text(text: str) -> str:
    """Trim noisy PDF text and keep the invoice-relevant content."""
    normalized = text.replace("\r", "\n")
    lines = []
    for line in normalized.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"Page\s*\d+", stripped, flags=re.IGNORECASE):
            continue
        if re.fullmatch(r"[-=]{3,}", stripped):
            continue
        lines.append(stripped)
    return "\n".join(lines)


def load_env_file(env_path: Path | None = None) -> dict[str, str]:
    """Load simple KEY=VALUE environment variables from a .env file."""
    target = env_path or Path(__file__).resolve().with_name(".env")
    values: dict[str, str] = {}

    if not target.is_file():
        return values

    for line in target.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")

    return values


def get_default_openrouter_model() -> str:
    """Return the default OpenRouter model from the environment or the LiquidAI default."""
    return os.getenv("OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL)


def get_openrouter_api_key() -> str | None:
    """Get the OpenRouter API key from the environment or a local .env file."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        return api_key
    return load_env_file().get("OPENROUTER_API_KEY")


def build_chat_request(text: str, model: str | None = None) -> dict[str, Any]:
    """Build a compact prompt that sends extracted PDF text to the model for invoice JSON."""
    cleaned_text = clean_extracted_text(text)
    return {
        "model": model or get_default_openrouter_model(),
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are extracting invoice data from text. Return valid JSON only. "
                    "Use keys: invoice_number, date, vendor, products, subtotal, tax, total. "
                    "If a value is missing, use null."
                ),
            },
            {"role": "user", "content": cleaned_text[:12000]},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }


def call_openrouter_chat_json(text: str, model: str | None = None) -> dict[str, Any]:
    """Call OpenRouter chat completions and parse the model's JSON output."""
    api_key = get_openrouter_api_key()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Add it to .env or your environment.")

    model_name = model or get_default_openrouter_model()
    payload = json.dumps(build_chat_request(text, model_name)).encode("utf-8")

    request_obj = request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://localhost",
            "X-Title": "AI InvoiceLens",
        },
        method="POST",
    )

    try:
        with request.urlopen(request_obj, timeout=60) as response:
            payload_data = json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter API error: {error_body}") from exc
    except Exception as exc:  # pragma: no cover - network failure path
        raise RuntimeError(f"OpenRouter chat request failed: {exc}") from exc

    choices = payload_data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenRouter did not return any chat completion choices.")

    message = choices[0].get("message") or {}
    content = message.get("content")
    if not content:
        raise RuntimeError("OpenRouter returned an empty chat completion response.")

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"OpenRouter returned non-JSON content: {content}") from exc

    return {"model": model_name, "json": parsed}


def extract_text(file_path: Path) -> str:
    """Extract text from every page in a PDF."""
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_invoice(text: str) -> dict[str, Any]:
    """Convert common invoice labels and table rows into structured data."""
    invoice_number_match = re.search(
        r"^\s*(?:Invoice\s*(?:#|No\.?|Number\s*)?)\s*(INV[-\s]+[A-Z0-9-]+|[A-Z0-9-]+)\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    date_match = re.search(
        r"^\s*Date:\s*(.+?)\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    item_pattern = re.compile(
        r"^\s*\d+\s+(.+?)\s+(\d+)\s+\$([\d,]+(?:\.\d{2})?)\s*$",
        flags=re.MULTILINE,
    )

    products = [
        {
            "item": match.group(1).strip(),
            "quantity": int(match.group(2)),
            "price": float(match.group(3).replace(",", "")),
        }
        for match in item_pattern.finditer(text)
    ]

    def amount(label: str) -> float | None:
        match = re.search(
            rf"^\s*{label}:\s*\$([\d,]+(?:\.\d{{2}})?)\s*$",
            text,
            flags=re.IGNORECASE | re.MULTILINE,
        )
        return float(match.group(1).replace(",", "")) if match else None

    return {
        "invoice_number": invoice_number_match.group(1)
        if invoice_number_match
        else None,
        "date": date_match.group(1).strip() if date_match else None,
        "products": products,
        "subtotal": amount("Subtotal"),
        "tax": amount(r"Tax \(0%\)"),
        "total": amount("Total Amount"),
    }


def output_json(payload: dict[str, Any], output_file: Path | None) -> None:
    """Print and optionally save formatted JSON."""
    serialized = json.dumps(payload, ensure_ascii=True, indent=2)
    print(serialized)
    if output_file:
        output_file.write_text(serialized + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract structured invoice data from a PDF."
    )
    parser.add_argument("file_path", type=Path, help="Path to the PDF file")
    parser.add_argument(
        "--output", type=Path, help="Optional path for saving the JSON response"
    )
    parser.add_argument(
        "--use-ai",
        action="store_true",
        help="Use the configured OpenRouter embedding model to generate an embedding for the extracted text.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="OpenRouter model to use for embeddings. Defaults to the LiquidAI LFM2.5 embedding model.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    file_path = args.file_path
    generated_at = datetime.now().astimezone()
    timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
    output_file = args.output or Path("output") / f"{file_path.stem}_{timestamp}.json"
    generated_at_text = generated_at.isoformat(timespec="seconds")

    output_file.parent.mkdir(parents=True, exist_ok=True)

    if not file_path.is_file():
        output_json(
            {
                "success": False,
                "file_path": str(file_path),
                "generated_at": generated_at_text,
                "error": f"PDF file not found: {file_path}",
            },
            output_file,
        )
        return 1

    try:
        raw_text = extract_text(file_path)
        text = clean_extracted_text(raw_text)
        invoice = parse_invoice(text)
    except Exception as error:
        output_json(
            {
                "success": False,
                "file_path": str(file_path),
                "generated_at": generated_at_text,
                "error": str(error),
            },
            output_file,
        )
        return 1

    ai_payload = None
    if args.use_ai:
        try:
            ai_payload = call_openrouter_chat_json(text, args.model)
        except Exception as error:
            ai_payload = {"success": False, "error": str(error)}

    output_json(
        {
            "success": True,
            "file_path": str(file_path),
            "generated_at": generated_at_text,
            "invoice": invoice,
            "text": text,
            "ai_invoice": ai_payload,
        },
        output_file,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())