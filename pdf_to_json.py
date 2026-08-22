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
import re
import sys
from pathlib import Path
from typing import Any


def extract_text(file_path: Path) -> str:
    """Extract text from every page in a PDF."""
    from pypdf import PdfReader

    reader = PdfReader(str(file_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def parse_invoice(text: str) -> dict[str, Any]:
    """Convert common invoice labels and table rows into structured data."""
    invoice_number_match = re.search(
        r"^\s*(INV[-\s]+[A-Z0-9-]+|[0-9]+)\s*$",
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
        text = extract_text(file_path)
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

    output_json(
        {
            "success": True,
            "file_path": str(file_path),
            "generated_at": generated_at_text,
            "invoice": invoice,
            "text": text,
        },
        output_file,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())