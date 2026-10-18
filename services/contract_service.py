"""Contratos: validação, cache de leitura e invalidação após escrita."""

from decimal import Decimal

import streamlit as st

import config
from repositories import client_repo, contract_repo
from services.cache_utils import safe_clear
from services.result import DataLoadError, ServiceResult
from utils.converters import to_decimal
from utils.validators import (
    validate_contract_dates,
    validate_setup_fee,
    validate_status,
    validate_text_length,
    validate_valor_mensal,
)

MSG_SELECT_CLIENT = "Selecione o cliente do contrato."
MSG_CLIENT_INACTIVE = "O cliente selecionado está inativo."


@st.cache_data(ttl=config.CACHE_TTL, show_spinner=False)
def list_contracts(_sb, client_id: str | None = None) -> list[dict]:
    rows, err = contract_repo.list_contracts(_sb, client_id)
    if err:
        raise DataLoadError(err)
    return rows


def _clean(data: dict) -> dict:
    cleaned = dict(data)
    if "titulo_projeto" in cleaned:
        cleaned["titulo_projeto"] = (cleaned["titulo_projeto"] or "").strip()
    for field in ("valor_mensal", "setup_fee"):
        if field in cleaned:
            amount = to_decimal(cleaned[field])
            cleaned[field] = amount if amount is not None else cleaned[field]
    return cleaned


def _validate(data: dict, merged: dict) -> str | None:
    """Valida os campos presentes em `data`; datas são checadas em conjunto com `merged`."""
    checks = []
    if "titulo_projeto" in data:
        checks.append(validate_text_length(data["titulo_projeto"], "Título do projeto", 255))
    if "status" in data:
        checks.append(validate_status(data["status"]))
    if "data_inicio" in data or "data_fim" in data:
        checks.append(validate_contract_dates(merged.get("data_inicio"), merged.get("data_fim")))
    if "valor_mensal" in data:
        checks.append(validate_valor_mensal(data["valor_mensal"]))
    if "setup_fee" in data:
        checks.append(validate_setup_fee(data["setup_fee"]))
    return next((err for ok, err in checks if not ok), None)


def create_contract(sb, data: dict) -> ServiceResult:
    cleaned = _clean({"setup_fee": Decimal("0"), **data})
    if not cleaned.get("cliente_id"):
        return ServiceResult(error=MSG_SELECT_CLIENT)
    required = {f: cleaned.get(f) for f in ("titulo_projeto", "status", "data_inicio", "data_fim", "valor_mensal", "setup_fee")}
    if err := _validate(required, cleaned):
        return ServiceResult(error=err)

    client, err = client_repo.get_client_by_id(sb, cleaned["cliente_id"])
    if err:
        return ServiceResult(error=err)
    if not client.get("ativo"):
        return ServiceResult(error=MSG_CLIENT_INACTIVE)  # Req 2.6, 3.2 (reforçado por trigger)

    created, err = contract_repo.create_contract(sb, cleaned)
    if err:
        return ServiceResult(error=err)
    return ServiceResult(data=created, warning=safe_clear(list_contracts))


def update_contract(sb, contract_id: str, data: dict) -> ServiceResult:
    current, err = contract_repo.get_contract_by_id(sb, contract_id)
    if err:
        return ServiceResult(error=err)
    cleaned = _clean({k: v for k, v in data.items() if k != "cliente_id"})
    if err := _validate(cleaned, {**current, **cleaned}):
        return ServiceResult(error=err)
    ok, err = contract_repo.update_contract(sb, contract_id, cleaned)
    if err:
        return ServiceResult(error=err)
    return ServiceResult(data=ok, warning=safe_clear(list_contracts))


def cancel_contract(sb, contract_id: str) -> ServiceResult:
    ok, err = contract_repo.cancel_contract(sb, contract_id)
    if err:
        return ServiceResult(error=err)
    return ServiceResult(data=ok, warning=safe_clear(list_contracts))
