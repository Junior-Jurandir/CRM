"""Conversões tolerantes de valores vindos do formulário ou do PostgREST."""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def to_decimal(value) -> Decimal | None:
    """Converte para Decimal sem perda de precisão; None se inválido.

    Aceita Decimal, int, float (via str) e strings como "1234.56" ou "1234,56".
    Rejeita bool, NaN e infinito.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, (int, float)):
        result = Decimal(str(value))
    elif isinstance(value, str):
        text = value.strip()
        if "," in text and "." not in text:
            text = text.replace(",", ".")
        try:
            result = Decimal(text)
        except InvalidOperation:
            return None
    else:
        return None
    return result if result.is_finite() else None


def to_date(value) -> date | None:
    """Converte date, datetime ou string ISO ("AAAA-MM-DD...") para date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError:
            return None
    return None
