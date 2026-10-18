"""Formatação para exibição (padrão brasileiro)."""

from decimal import ROUND_HALF_UP, Decimal

from utils.converters import to_date, to_decimal


def format_currency(value) -> str:
    """Decimal('1234.5') → 'R$ 1.234,50'. Valor inválido → 'R$ 0,00'."""
    amount = to_decimal(value)
    if amount is None:
        amount = Decimal("0")
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    text = f"{abs(amount):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return f"{sign}R$ {text}"


def format_date(value) -> str:
    """date(2026, 10, 18) ou '2026-10-18' → '18/10/2026'. Inválido → ''."""
    parsed = to_date(value)
    return parsed.strftime("%d/%m/%Y") if parsed else ""


def format_cnpj(cnpj: str | None) -> str:
    """'12345678000190' → '12.345.678/0001-90'. Fora do padrão → valor original."""
    digits = "".join(ch for ch in (cnpj or "") if ch.isdigit())
    if len(digits) != 14:
        return cnpj or ""
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
