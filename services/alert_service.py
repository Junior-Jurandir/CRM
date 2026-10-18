"""Níveis de alerta de vencimento de contratos (Req 5). Módulo puro."""

from datetime import date
from enum import IntEnum

from utils.converters import to_date


class AlertLevel(IntEnum):
    NONE = 0       # > 30 dias, ou status não elegível
    ATTENTION = 1  # 16–30 dias
    URGENT = 2     # 8–15 dias
    CRITICAL = 3   # 1–7 dias
    EXPIRED = 4    # data_fim ≤ hoje


ALERT_ELIGIBLE_STATUSES = frozenset({"Ativo", "Renovação Pendente"})

# Ícone + rótulo textual: o nível não depende só da cor (Req 10.2).
_BADGES = {
    AlertLevel.ATTENTION: ("🟡", "Atenção"),
    AlertLevel.URGENT: ("🟠", "Urgente"),
    AlertLevel.CRITICAL: ("🔴", "Crítico"),
    AlertLevel.EXPIRED: ("⛔", "Vencido"),
}


def days_remaining(contract: dict, reference_date: date | None = None) -> int | None:
    """Dias até data_fim a partir da data de referência (padrão: hoje no servidor)."""
    data_fim = to_date(contract.get("data_fim"))
    if data_fim is None:
        return None
    return (data_fim - (reference_date or date.today())).days


def level_for_days(days: int) -> AlertLevel:
    if days <= 0:
        return AlertLevel.EXPIRED
    if days <= 7:
        return AlertLevel.CRITICAL
    if days <= 15:
        return AlertLevel.URGENT
    if days <= 30:
        return AlertLevel.ATTENTION
    return AlertLevel.NONE


def get_alert_level(contract: dict, reference_date: date | None = None) -> AlertLevel:
    if contract.get("status") not in ALERT_ELIGIBLE_STATUSES:
        return AlertLevel.NONE
    days = days_remaining(contract, reference_date)
    return AlertLevel.NONE if days is None else level_for_days(days)


def get_expiring_contracts(contracts: list[dict], reference_date: date | None = None) -> list[dict]:
    """Contratos elegíveis com alerta, ordenados do mais urgente para o menos urgente.

    Cada item é uma cópia do contrato com as chaves extras `alert_level` e `days_remaining`.
    """
    ref = reference_date or date.today()
    expiring = []
    for contract in contracts:
        level = get_alert_level(contract, ref)
        if level != AlertLevel.NONE:
            expiring.append({**contract, "alert_level": level, "days_remaining": days_remaining(contract, ref)})
    return sorted(expiring, key=lambda c: c["days_remaining"])


def alert_badge(level: AlertLevel, days: int | None) -> str:
    """Texto do indicador visual, ex.: '🟠 Urgente · 12 dias'. NONE → ''."""
    if level not in _BADGES:
        return ""
    icon, label = _BADGES[level]
    if level == AlertLevel.EXPIRED:
        return f"{icon} {label}"
    return f"{icon} {label} · {days} dia{'s' if days != 1 else ''}"
