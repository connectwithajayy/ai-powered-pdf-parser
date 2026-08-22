# PDF to JSON Invoice Parser

Extracts readable text and structured invoice data from a PDF file.

## Install

```bash
pip install pypdf
```

## Usage

```bash
python pdf_to_json.py file/invoice.pdf --output invoice.json
```

The output includes the invoice number, date, products, quantities, prices, totals, and extracted text. The `.env` file is ignored because this project does not require API keys.
