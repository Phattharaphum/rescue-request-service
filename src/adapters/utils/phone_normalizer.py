import re


def normalize_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = re.sub(r"[^\d+]", "", phone)
    if digits.startswith("+66"):
        digits = "0" + digits[3:]
    elif digits.startswith("66") and len(digits) > 9:
        digits = "0" + digits[2:]
    digits = re.sub(r"[^\d]", "", digits)
    return digits
