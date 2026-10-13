def normalize_text(value: str, default: str) -> str:
    return value.strip() if value and value.strip() else default