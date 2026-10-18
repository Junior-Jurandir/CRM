"""Agregação de métricas do Dashboard (Req 6). Módulo puro."""

from datetime import date
from decimal import Decimal

from services.alert_service import days_remaining
from utils.converters import to_decimal
from utils.validators import CONTRACT_STATUSES

EXPIRATION_BUCKETS = ("Vencidos", "1-7 dias", "8-15 dias", "16-30 dias", "> 30 dias")


def calculate_mrr(contracts: list[dict]) -> Decimal:
    """Soma de valor_mensal dos contratos com status 'Ativo'."""
    total = Decimal("0")
    for contract in contracts:
        if contract.get("status") == "Ativo":
            total += to_decimal(contract.get("valor_mensal")) or Decimal("0")
    return total


def count_by_status(contracts: list[dict]) -> dict[str, int]:
    """Contagem por status, sempre com as 4 chaves na ordem oficial."""
    counts = dict.fromkeys(CONTRACT_STATUSES, 0)
    for contract in contracts:
        if contract.get("status") in counts:
            counts[contract["status"]] += 1
    return counts


def _bucket(days: int) -> str:
    if days <= 0:
        return "Vencidos"
    if days <= 7:
        return "1-7 dias"
    if days <= 15:
        return "8-15 dias"
    if days <= 30:
        return "16-30 dias"
    return "> 30 dias"


def expiration_distribution(contracts: list[dict], reference_date: date | None = None) -> dict[str, int]:
    """Distribuição por faixa de dias até data_fim, ignorando contratos 'Cancelado' (Req 6.3)."""
    ref = reference_date or date.today()
    distribution = dict.fromkeys(EXPIRATION_BUCKETS, 0)
    for contract in contracts:
        if contract.get("status") == "Cancelado":
            continue
        days = days_remaining(contract, ref)
        if days is not None:
            distribution[_bucket(days)] += 1
    return distribution
