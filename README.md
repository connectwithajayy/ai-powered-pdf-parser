# AI InvoiceLens: PDF to Text to JSON Invoice Parser

**AI InvoiceLens** extracts invoice text from a PDF, cleans the extracted content,
and sends the relevant text to an AI model through OpenRouter to return clean,
structured JSON.

This project uses a two-step workflow:

1. PDF to text using `pypdf`
2. Text to JSON using a model prompt and JSON response format

> ## **AI Model: `nvidia/nemotron-3.5-lightning:free`**

## Approach

**Active model:** `nvidia/nemotron-3.5-lightning:free`

The current workflow is intentionally designed to keep token usage low:

- Read the PDF with `pypdf`
- Extract page text
- Clean noisy lines like page numbers and repeated separators
- Reduce the text to the relevant invoice data
- Send the formatted text to the OpenRouter model
- Ask the model to return valid JSON only

This reduces the amount of text sent to the model and makes the output more
reliable for invoice parsing.

## Requirements

- Python 3.10 or newer
- `pypdf`
- A valid OpenRouter API key
- A model that is allowed for your OpenRouter account

Scanned or image-only PDFs may need OCR first before text extraction is useful.

## Installation

Open PowerShell or a terminal in this project folder and run:

```bash
pip install pypdf
```

Create a `.env` file in the project folder:

```dotenv
OPENROUTER_API_KEY=your_openrouter_api_key_here
OPENROUTER_MODEL=nvidia/nemotron-3.5-lightning:free  # AI model
```

Never commit `.env` or share the key publicly. The `.gitignore` file already
excludes `.env` from Git.

## Convert a PDF

Save the PDF inside the `file` folder, then run:

```bash
python pdf_to_json.py file/invoice.pdf --output invoice.json
```

The `--output` option is optional. Without it, the tool creates an `output`
folder and saves a timestamped file there, such as
`output/invoice_20260822_140601.json`. It also prints the JSON in the terminal:

```bash
python pdf_to_json.py file/invoice.pdf
```

To include the AI JSON extraction step, use:

```bash
python pdf_to_json.py file/invoice.pdf --use-ai --output invoice.json
```

Windows paths can also be written with forward slashes:

```bash
python pdf_to_json.py "C:/Documents/my-invoice.pdf" --use-ai --output my-invoice.json
```

## Workflow Example

```text
PDF file
  -> pypdf extracts text
  -> clean extraneous lines
  -> send compact text to OpenRouter
  -> model returns structured JSON
```

## Example Output

```json
{
  "success": true,
  "file_path": "file/invoice.pdf",
  "generated_at": "2026-08-22T14:06:01+05:30",
  "invoice": {
    "invoice_number": "INV-2026-001",
    "date": "August 22, 2026",
    "products": [
      {
        "item": "Standard Product A",
        "quantity": 1,
        "price": 60.0
      }
    ],
    "subtotal": 100.0,
    "tax": 0.0,
    "total": 100.0
  },
  "text": "Invoice #INV-2026-001\nDate: August 22, 2026\n...",
  "ai_invoice": {
    "model": "nvidia/nemotron-3.5-lightning:free",
    "json": {
      "invoice_number": "INV-2026-001",
      "date": "August 22, 2026",
      "vendor": null,
      "products": [
        {
          "item": "Standard Product A",
          "quantity": 1,
          "price": 60.0
        }
      ],
      "subtotal": 100.0,
      "tax": 0.0,
      "total": 100.0
    }
  }
}
```

## Error Output

If the file does not exist or cannot be read, the tool returns JSON with
`success` set to `false`:

```json
{
  "success": false,
  "file_path": "file/missing.pdf",
  "error": "PDF file not found: file/missing.pdf"
}
```

## Supported Invoice Format

The parser looks for these labels and table columns:

- Invoice number, such as `INV-2026-001`
- Date, such as `Date: August 22, 2026`
- Product rows containing item name, quantity, and dollar amount
- `Subtotal`, `Tax (0%)`, and `Total Amount`

The AI path also accepts the extracted text and formats it into JSON with the
keys above, which makes the workflow more flexible for different invoice layouts.
