from pdf_to_json import build_chat_request, get_default_openrouter_model, parse_invoice


def test_default_model_is_structured_chat_model():
    assert get_default_openrouter_model() == "nvidia/nemotron-3.5-lightning:free"


def test_build_chat_request_uses_model_and_text():
    payload = build_chat_request("Invoice #123", "custom/model")
    assert payload["model"] == "custom/model"
    assert payload["messages"][1]["content"] == "Invoice #123"


def test_parse_invoice_extracts_expected_fields():
    invoice = parse_invoice("""
    Invoice #INV-2026-001
    Date: August 22, 2026
    1 Standard Product A 1 $60.00
    1 Standard Service B 1 $40.00
    Subtotal: $100.00
    Tax (0%): $0.00
    Total Amount: $100.00
    """)

    assert invoice["invoice_number"] == "INV-2026-001"
    assert invoice["date"] == "August 22, 2026"
    assert invoice["subtotal"] == 100.0
    assert invoice["tax"] == 0.0
    assert invoice["total"] == 100.0
