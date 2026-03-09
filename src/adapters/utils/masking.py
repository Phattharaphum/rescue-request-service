def mask_phone(phone: str) -> str:
    if not phone or len(phone) < 4:
        return "***"
    return phone[:3] + "*" * (len(phone) - 6) + phone[-3:]


def mask_tracking_code(code: str) -> str:
    if not code or len(code) < 2:
        return "***"
    return code[:2] + "*" * (len(code) - 2)
