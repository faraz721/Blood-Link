import re
from typing import Optional, Tuple


def normalize_phone(phone: str) -> Optional[str]:
    """
    Normalize Pakistani phone numbers to 03XXXXXXXXX format.
    Accepts:
      - 03XXXXXXXXX
      - +923XXXXXXXXX
      - 923XXXXXXXXX
      - 03XX-XXXXXXX etc (strips non-digits)
    Returns normalized 03XXXXXXXXX or None if invalid.
    """
    if not phone:
        return None

    # Keep only digits and leading +
    cleaned = re.sub(r"[^\d+]", "", phone.strip())

    if cleaned.startswith("+"):
        cleaned = cleaned[1:]

    # 923XXXXXXXXX -> 03XXXXXXXXX
    if cleaned.startswith("92") and len(cleaned) == 12:
        cleaned = "0" + cleaned[2:]

    # Must be 11 digits starting with 03
    if re.fullmatch(r"03\d{9}", cleaned):
        return cleaned

    return None


def validate_phone(phone: str) -> Tuple[bool, str]:
    """
    Validate and return (is_valid, normalized_or_error_message)
    """
    normalized = normalize_phone(phone)
    if not normalized:
        return False, "Please enter a valid Pakistani mobile number (e.g. 03XXXXXXXXX)."
    return True, normalized


def phones_equal(a: str, b: str) -> bool:
    na = normalize_phone(a)
    nb = normalize_phone(b)
    return na is not None and na == nb