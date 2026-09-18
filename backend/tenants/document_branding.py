"""Shared branding helpers for generated school documents."""

import base64
import io
import json
from decimal import Decimal


def _safe_asset_url(value):
    """Allow only absolute HTTP(S) asset URLs in PDF templates."""
    if isinstance(value, str) and value.startswith(("http://", "https://")):
        return value
    return ""


def school_branding_context(school):
    """Return normalized school identity values for every generated document."""
    theme = school.get_theme() if hasattr(school, "get_theme") else {}
    primary = theme.get("primary_color") or "#173B56"
    secondary = theme.get("secondary_color") or "#256D85"
    accent = theme.get("accent_color") or "#D8A548"

    contact_parts = [
        getattr(school, "address", ""),
        getattr(school, "phone", ""),
        getattr(school, "email", ""),
    ]
    contact_line = " | ".join(str(part).strip() for part in contact_parts if str(part).strip())

    return {
        "school_name": getattr(school, "name", "School"),
        "school_address": getattr(school, "address", ""),
        "school_phone": getattr(school, "phone", ""),
        "school_email": getattr(school, "email", ""),
        "school_motto": getattr(school, "motto", ""),
        "school_registration_number": getattr(school, "registration_number", ""),
        "school_contact_line": contact_line,
        "school_logo": _safe_asset_url(getattr(school, "logo", "")),
        "document_primary_color": primary,
        "document_secondary_color": secondary,
        "document_accent_color": accent,
    }


def secure_document_response(response):
    """Prevent authenticated school documents from being cached or sniffed."""
    response["Cache-Control"] = "private, no-store"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def receipt_barcode_data_uri(payment):
    """Create a scannable QR barcode as a data URI for receipt verification."""
    try:
        import qrcode
        payload = {
            "type": "school-fee-receipt",
            "receipt": payment.receipt_number,
            "school": getattr(payment.school, "slug", ""),
            "student": getattr(payment.student, "admission_number", ""),
            "amount": str(Decimal(payment.amount_paid).quantize(Decimal("0.01"))),
            "date": payment.payment_date.isoformat() if payment.payment_date else "",
            "reference": payment.paystack_reference or "",
        }
        image = qrcode.make(json.dumps(payload, separators=(",", ":")))
        output = io.BytesIO()
        image.save(output, format="PNG")
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception:
        return ""
