import re
from typing import Iterable, List, Tuple


PURE_CODE_PATTERN = re.compile(r"^\d{6}$")


def infer_exchange_from_code(code: str) -> str:
    if code.startswith(("5", "6", "9")):
        return "SH"
    if code.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def normalize_stock_symbol(symbol: str) -> str | None:
    raw = (symbol or "").strip().upper()
    if not raw:
        return None

    if PURE_CODE_PATTERN.match(raw):
        return f"{raw}.{infer_exchange_from_code(raw)}"

    return None


def normalize_stock_symbols(symbols: Iterable[str]) -> Tuple[List[str], List[str]]:
    normalized: List[str] = []
    invalid: List[str] = []
    seen = set()

    for symbol in symbols:
        normalized_symbol = normalize_stock_symbol(symbol)
        if not normalized_symbol:
            invalid.append((symbol or "").strip())
            continue

        if normalized_symbol in seen:
            continue

        seen.add(normalized_symbol)
        normalized.append(normalized_symbol)

    return normalized, invalid
